import json
from datetime import date, datetime, timezone

from redis_client import redis_client

SESSION_TTL_SECONDS = 60 * 60
ABANDONED_UPLOAD_MESSAGE = "페이지를 벗어나 업로드가 중단되었습니다."


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize_json(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


class UploadSessionService:
    def _key(self, user_id: int) -> str:
        return f"upload_session:{user_id}"

    def _load(self, user_id: int) -> dict | None:
        raw = redis_client.get(self._key(user_id))
        if not raw:
            return None
        return json.loads(raw)

    def _save(self, user_id: int, payload: dict) -> dict:
        redis_client.set(
            self._key(user_id),
            json.dumps(payload, ensure_ascii=False, default=_serialize_json),
            ex=SESSION_TTL_SECONDS,
        )
        return payload

    def create_session(self, user_id: int, file_names: list[str]) -> dict:
        payload = {
            "started_at": _now_iso(),
            "abandoned_at": None,
            "items": [
                {
                    "file_name": file_name,
                    "status": "waiting",
                    "doc_id": None,
                    "summary": None,
                    "error": None,
                    "updated_at": _now_iso(),
                }
                for file_name in file_names
            ],
        }
        return self._save(user_id, payload)

    def get_session(self, user_id: int) -> dict:
        payload = self._load(user_id)
        if not payload:
            return {"started_at": None, "abandoned_at": None, "items": []}
        return payload

    def clear_session(self, user_id: int) -> None:
        redis_client.delete(self._key(user_id))

    def mark_processing(self, user_id: int, file_name: str, doc_id: int) -> dict:
        payload = self._load(user_id)
        if not payload:
            return self.get_session(user_id)

        for item in payload["items"]:
            if item["file_name"] == file_name and item["status"] == "waiting":
                item["status"] = "processing"
                item["doc_id"] = doc_id
                item["error"] = None
                item["updated_at"] = _now_iso()
                break

        return self._save(user_id, payload)

    def mark_document_done(self, user_id: int, doc_id: int, summary: dict) -> dict:
        payload = self._load(user_id)
        if not payload:
            return self.get_session(user_id)

        for item in payload["items"]:
            if item["doc_id"] == doc_id:
                item["status"] = "done"
                item["summary"] = summary
                item["error"] = None
                item["updated_at"] = _now_iso()
                break

        return self._save(user_id, payload)

    def mark_document_failed(self, user_id: int, doc_id: int, error: str) -> dict:
        payload = self._load(user_id)
        if not payload:
            return self.get_session(user_id)

        for item in payload["items"]:
            if item["doc_id"] == doc_id:
                item["status"] = "failed"
                item["error"] = error
                item["updated_at"] = _now_iso()
                break

        return self._save(user_id, payload)

    def abandon_session(
        self, user_id: int, error: str = ABANDONED_UPLOAD_MESSAGE
    ) -> dict:
        payload = self._load(user_id)
        if not payload:
            return self.get_session(user_id)

        processing_kept = False
        for item in payload["items"]:
            if item["status"] == "processing" and not processing_kept:
                processing_kept = True
                continue
            if item["status"] in {"waiting", "processing"}:
                item["status"] = "failed"
                item["error"] = error
                item["updated_at"] = _now_iso()

        payload["abandoned_at"] = _now_iso()
        return self._save(user_id, payload)
