import json
from datetime import date

SUMMARY_METADATA_FIELDS = (
    "document_type",
    "case_number",
    "case_name",
    "court_name",
    "judgment_date",
    "plaintiff",
    "defendant",
)


def parse_summary_metadata(summary) -> dict:
    if not summary or not getattr(summary, "metadata_json", None):
        return {}
    try:
        parsed = json.loads(summary.metadata_json)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def get_summary_field(summary, field: str):
    metadata = parse_summary_metadata(summary)
    if field == "summary_text":
        return getattr(summary, "summary_text", None)
    if field == "key_points":
        return get_key_points(summary)

    value = metadata.get(field)
    if field == "judgment_date" and isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return value
    return value


def build_document_title(summary, fallback_title: str) -> str:
    case_number = get_summary_field(summary, "case_number")
    case_name = get_summary_field(summary, "case_name")

    if case_number and case_name:
        return f"{case_number} {case_name}"
    if case_name:
        return case_name
    if case_number:
        return case_number
    return fallback_title


def build_summary_preview(summary, limit: int = 200) -> str:
    main_text = get_summary_field(summary, "summary_text") or ""
    if not main_text:
        return ""
    return (main_text[:limit] + "...") if len(main_text) > limit else main_text


def get_key_points(summary) -> list[str]:
    if not summary:
        return []

    raw = getattr(summary, "key_points", None)
    if not raw:
        return []

    lines = []
    for line in str(raw).splitlines():
        cleaned = line.strip().lstrip("-").lstrip("•").strip()
        if cleaned:
            lines.append(cleaned)
    return lines


def build_upload_session_summary(parsed_meta: dict) -> dict:
    return {
        "content": parsed_meta.get("summary_text") or "요약 내용이 없습니다.",
        "key_points": parsed_meta.get("key_points") or [],
    }
