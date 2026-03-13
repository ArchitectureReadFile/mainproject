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

from errors import AppException, ErrorCode
from repositories.summary_repository import SummaryRepository

logger = logging.getLogger(__name__)

FONT_PATH = os.path.join(os.path.dirname(__file__), "..", "fonts", "NanumMyeongjo.ttf")
pdfmetrics.registerFont(TTFont("NanumMyeongjo", FONT_PATH))


class PdfService:
    """요약 데이터를 기반으로 PDF 파일을 생성합니다."""

    def __init__(self, db: Session):
        self.db = db

    def generate_pdf(self, summary_id: int) -> tuple[BytesIO, str]:
        summary = SummaryRepository(self.db).get_by_id(summary_id)
        if not summary:
            raise AppException(ErrorCode.SUM_NOT_FOUND)

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
        story.append(Paragraph(summary.summary_title or "판례 요약", title_style))
        story.append(Spacer(1, 6 * mm))

        meta_data = [
            [
                "사건번호",
                summary.case_number or "-",
                "법원명",
                summary.court_name or "-",
            ],
            [
                "사건명",
                summary.case_name or "-",
                "판결일자",
                str(summary.judgment_date) if summary.judgment_date else "-",
            ],
            ["원고", summary.plaintiff or "-", "피고", summary.defendant or "-"],
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
            ("■ 요약", summary.summary_main),
            ("■ 사실관계", summary.facts),
            ("■ 판결주문", summary.judgment_order),
            ("■ 판결이유", summary.judgment_reason),
            ("■ 관련법령", summary.related_laws),
        ]
        for section_title, content in sections:
            story.append(Paragraph(section_title, section_style))
            story.append(Paragraph(content or "-", body_style))
            story.append(Spacer(1, 3 * mm))

        doc.build(story)
        buffer.seek(0)

        return buffer, summary.case_number or str(summary_id)
