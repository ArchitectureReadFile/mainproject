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
        """문서 전체를 단일 LLM 호출로 구조화된 요약 dict를 반환합니다."""
        max_text_chars = int(os.environ.get("SUMMARY_MAX_TEXT_CHARS", "15000"))

        non_empty_pages = [p for p in pages if p.strip()]
        if not non_empty_pages:
            raise AppException(ErrorCode.LLM_EMPTY_PAGES)

        input_text = "\n\n".join(non_empty_pages)

        if not input_text.strip():
            raise AppException(ErrorCode.LLM_EMPTY_PAGES)

        final_prompt = SUMMARIZE_PROMPT.replace("{text}", input_text[:max_text_chars])
        return self.client.call_json(final_prompt, num_predict=3072)
