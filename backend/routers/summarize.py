import os
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db
from models.model import User
from routers.auth import get_current_user
from services.pdf_service import PdfService

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "uploads")


def get_pdf_service(db: Session = Depends(get_db)) -> PdfService:
    return PdfService(db)


@router.get("/summaries/{summary_id}/download")
def download_pdf(
    summary_id: int,
    service: PdfService = Depends(get_pdf_service),
    current_user: User = Depends(get_current_user),
):
    buffer, case_number = service.generate_pdf(summary_id)
    filename = f"{case_number or summary_id}_AI요약.pdf"
    encoded_filename = quote(filename)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        },
    )
