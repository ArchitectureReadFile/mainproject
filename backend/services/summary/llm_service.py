import logging
import os

from errors import AppException, ErrorCode
from prompts.summarize_prompt import SUMMARIZE_PROMPT
from services.summary.llm_client import LLMClient
from services.summary.text_splitter import TextSplitter

logger = logging.getLogger(__name__)

# 이유 섹션이 이 길이보다 짧으면 전체 텍스트를 사용
_REASON_MIN_CHARS = 200


class LLMService:
    """이유 섹션 단일 호출 요약을 담당합니다."""

    def __init__(self):
        self.client = LLMClient()
        self.splitter = TextSplitter()

    def release_resources(self) -> None:
        """요약 실패 시 LLM 리소스 정리를 위임합니다."""
        self.client.unload_model()

    def summarize(self, pages: list[str]) -> dict:
        """이유 섹션을 정제해 단일 LLM 호출로 구조화된 요약 dict를 반환합니다."""
        max_text_chars = int(os.environ.get("SUMMARY_MAX_TEXT_CHARS", "15000"))

        non_empty_pages = [p for p in pages if p.strip()]
        if not non_empty_pages:
            raise AppException(ErrorCode.LLM_EMPTY_PAGES)

        full_text = "\n\n".join(non_empty_pages)

        reason_text_raw = self.splitter.extract_reason_section(full_text)
        reason_text = (
            self.splitter.clean_noise(reason_text_raw) if reason_text_raw else ""
        )

        # 이유 섹션이 너무 짧으면(심리불속행 등) 전체 텍스트를 사용해 사실관계 추출 보완
        if len(reason_text.strip()) < _REASON_MIN_CHARS:
            logger.info("[LLM] 이유 섹션이 짧아 전체 텍스트로 대체합니다.")
            input_text = self.splitter.clean_noise(full_text)
        else:
            input_text = reason_text

        if not input_text.strip():
            raise AppException(ErrorCode.LLM_EMPTY_PAGES)

        final_prompt = SUMMARIZE_PROMPT.replace("{text}", input_text[:max_text_chars])
        return self.client.call_json(final_prompt, num_predict=3072)
