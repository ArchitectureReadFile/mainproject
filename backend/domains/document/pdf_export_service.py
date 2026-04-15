import logging
import os
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from domains.document.repository import DocumentRepository
from domains.document.summary_mapper import get_key_points, get_summary_field
from domains.document.summary_repository import SummaryRepository
from errors import AppException, ErrorCode

logger = logging.getLogger(__name__)

FONT_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "fonts", "NanumMyeongjo.ttf")
)
pdfmetrics.registerFont(TTFont("NanumMyeongjo", FONT_PATH))


class PdfService:
    """요약 데이터를 기반으로 PDF 파일을 생성합니다."""

    def __init__(self, db: Session):
        self.db = db

    def generate_pdf(self, summary_id: int) -> tuple[BytesIO, str]:
        summary = SummaryRepository(self.db).get_by_id(summary_id)
        if not summary:
            raise AppException(ErrorCode.SUM_NOT_FOUND)

        # document_type source of truth: Document 모델
        # summary metadata의 document_type는 보조 기록이므로 표시에 사용하지 않는다
        document = DocumentRepository(self.db).get_by_id(summary.document_id)
        document_type = (document.document_type if document else None) or "-"

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=25 * mm,
            bottomMargin=25 * mm,
        )

        font = "NanumMyeongjo"
        title_style = ParagraphStyle(
            "title", fontName=font, fontSize=16, leading=24, alignment=1, spaceAfter=10
        )
        section_style = ParagraphStyle(
            "section",
            fontName=font,
            fontSize=11,
            leading=18,
            spaceBefore=12,
            spaceAfter=4,
        )
        body_style = ParagraphStyle(
            "body", fontName=font, fontSize=10, leading=16, spaceAfter=6
        )

        story = []
        story.append(Paragraph("문서 요약", title_style))
        story.append(Spacer(1, 6 * mm))

        meta_data = [
            [
                "문서 유형",
                document_type,
                "생성일",
                str(summary.created_at.date()),
            ],
        ]
        meta_table = Table(meta_data, colWidths=[25 * mm, 65 * mm, 25 * mm, 55 * mm])
        meta_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), font),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
                    ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f0f0f0")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(meta_table)
        story.append(Spacer(1, 6 * mm))

        sections = [
            (
                "■ 요약",
                get_summary_field(summary, "summary_text") or summary.summary_text,
            )
        ]
        for section_title, content in sections:
            story.append(Paragraph(section_title, section_style))
            story.append(Paragraph(content or "-", body_style))
            story.append(Spacer(1, 3 * mm))

        story.append(Paragraph("■ 핵심 포인트", section_style))
        key_points = get_key_points(summary)
        if key_points:
            for point in key_points:
                story.append(Paragraph(f"• {point}", body_style))
        else:
            story.append(Paragraph("-", body_style))
        story.append(Spacer(1, 3 * mm))

        doc.build(story)
        buffer.seek(0)

        return buffer, str(summary_id)
