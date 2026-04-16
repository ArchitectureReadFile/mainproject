# GET /summaries/{summary_id}/download — 프론트 미연결로 제거
# 서비스 레이어(PdfService)는 유지
from fastapi import APIRouter

router = APIRouter()
