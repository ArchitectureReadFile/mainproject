import logging
import os

from errors import AppException, ErrorCode
from infra.llm.client import LLMClient
from prompts.summarize_prompt import SUMMARIZE_PROMPT

logger = logging.getLogger(__name__)


class LLMService:
    """문서 전체를 기반으로 검토용 브리프 요약을 생성합니다."""

    def __init__(self):
        self.client = LLMClient()

    def release_resources(self) -> None:
        """요약 실패 시 LLM 리소스 정리를 위임합니다."""
        self.client.unload_model()

    def summarize(self, pages: list[str]) -> dict:
        """문서 전체를 chunk map-reduce 방식으로 구조화된 요약 dict를 반환합니다."""
        max_text_chars = int(os.environ.get("SUMMARY_MAX_TEXT_CHARS", "15000"))
        map_input_chars = int(os.environ.get("SUMMARY_MAP_INPUT_CHARS", "5500"))

        non_empty_pages = [p for p in pages if p.strip()]
        if not non_empty_pages:
            raise AppException(ErrorCode.LLM_EMPTY_PAGES)

        input_text = "\n\n".join(non_empty_pages)

        if not input_text.strip():
            raise AppException(ErrorCode.LLM_EMPTY_PAGES)

        chunks = _build_summary_chunks(input_text, map_input_chars)
        if len(chunks) == 1:
            return self._summarize_text(chunks[0][:max_text_chars], num_predict=3072)

        logger.info("[SUMMARY_MAP_REDUCE] chunks=%s", len(chunks))
        partial_summaries = [
            self._summarize_text(chunk, num_predict=1536) for chunk in chunks
        ]
        reduce_input = _build_reduce_input(partial_summaries)[:max_text_chars]
        return self._summarize_text(reduce_input, num_predict=3072)

    def _summarize_text(self, text: str, *, num_predict: int) -> dict:
        final_prompt = SUMMARIZE_PROMPT.replace("{text}", text)
        return self.client.call_json(final_prompt, num_predict=num_predict)


def _build_summary_chunks(text: str, max_chars: int) -> list[str]:
    """문단 경계를 우선 보존하며 요약 입력을 청크로 분할한다."""
    stripped = text.strip()
    if not stripped:
        return []

    paragraphs = [part.strip() for part in stripped.split("\n\n") if part.strip()]
    if not paragraphs:
        return [stripped[:max_chars]]

    chunks: list[str] = []
    current_parts: list[str] = []
    current_len = 0

    for paragraph in paragraphs:
        paragraph_len = len(paragraph)

        if paragraph_len > max_chars:
            if current_parts:
                chunks.append("\n\n".join(current_parts))
                current_parts = []
                current_len = 0
            chunks.extend(_split_long_text(paragraph, max_chars))
            continue

        next_len = current_len + paragraph_len + (2 if current_parts else 0)
        if current_parts and next_len > max_chars:
            chunks.append("\n\n".join(current_parts))
            current_parts = [paragraph]
            current_len = paragraph_len
            continue

        current_parts.append(paragraph)
        current_len = next_len if current_parts[:-1] else paragraph_len

    if current_parts:
        chunks.append("\n\n".join(current_parts))

    return chunks


def _split_long_text(text: str, max_chars: int) -> list[str]:
    """매우 긴 단락은 max_chars 단위로 강제 분할한다."""
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]


def _build_reduce_input(partial_summaries: list[dict]) -> str:
    sections: list[str] = []
    for idx, summary in enumerate(partial_summaries, 1):
        summary_text = str(summary.get("summary_text") or "").strip()
        key_points = summary.get("key_points") or []
        lines = [f"[청크 {idx} 요약]"]
        if summary_text:
            lines.append(summary_text)
        if key_points:
            lines.append("[핵심 포인트]")
            lines.extend(
                f"- {str(point).strip()}" for point in key_points if str(point).strip()
            )
        sections.append("\n".join(lines))
    return "\n\n".join(sections)
