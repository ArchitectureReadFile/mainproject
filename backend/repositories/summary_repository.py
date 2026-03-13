from datetime import date

from sqlalchemy.orm import Session

from models.model import Summary


class SummaryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, summary_id: int) -> Summary | None:
        return self.db.query(Summary).filter(Summary.id == summary_id).first()

    def create_summary(
        self,
        document_id: int,
        title: str,
        case_number: str | None = None,
        case_name: str | None = None,
        court_name: str | None = None,
        judgment_date: date | None = None,
        summary_main: str | None = None,
        plaintiff: str | None = None,
        defendant: str | None = None,
        facts: str | None = None,
        judgment_order: str | None = None,
        judgment_reason: str | None = None,
        related_laws: str | None = None,
    ) -> Summary:
        """
        정제된 요약 데이터를 DB 모델 스키마에 1:1 매핑하여 삽입합니다.
        트랜잭션(commit)은 호출부인 서비스 레이어에서 통제하므로 여기서는 add만 수행합니다.
        """
        new_summary = Summary(
            document_id=document_id,
            summary_title=title,
            case_number=case_number,
            case_name=case_name,
            court_name=court_name,
            judgment_date=judgment_date,
            summary_main=summary_main,
            plaintiff=plaintiff,
            defendant=defendant,
            facts=facts,
            judgment_order=judgment_order,
            judgment_reason=judgment_reason,
            related_laws=related_laws,
        )
        self.db.add(new_summary)
        return new_summary
