import json

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
        summary_text: str | None = None,
        key_points: str | None = None,
        metadata: dict | None = None,
    ) -> Summary:
        new_summary = Summary(
            document_id=document_id,
            summary_text=summary_text,
            key_points=key_points,
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
        )
        self.db.add(new_summary)
        return new_summary
