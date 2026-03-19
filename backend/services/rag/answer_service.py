import logging
import os
import re

from prompts.rag_answer_prompt import RAG_ANSWER_PROMPT
from services.summary.llm_client import LLMClient

logger = logging.getLogger(__name__)

_DEFAULT_EMPTY_ANSWER = "관련 판례를 찾지 못했습니다."
_DEFAULT_FAILURE_ANSWER = (
    "검색 결과를 바탕으로 답변을 생성하지 못했습니다. 아래 참고 판례를 확인해주세요."
)
_DEFAULT_LIMITED_ANSWER = (
    "검색 결과를 바탕으로 답변을 생성했지만, 근거 판례 링크를 확정하지 못했습니다."
)


class RagAnswerService:
    def __init__(self):
        self.client = LLMClient()
        self.max_items = int(os.getenv("RAG_ANSWER_MAX_ITEMS", "5"))
        self.max_text_chars = int(os.getenv("RAG_ANSWER_MAX_TEXT_CHARS", "1500"))
        self.num_predict = int(os.getenv("RAG_ANSWER_NUM_PREDICT", "1024"))

    def generate_answer(self, query: str, results: list[dict]) -> dict:
        if not results:
            return {
                "answer": _DEFAULT_EMPTY_ANSWER,
                "citations": [],
            }

        try:
            context = self._build_context(results)
            prompt = RAG_ANSWER_PROMPT.replace("{query}", query).replace(
                "{context}", context
            )
            raw_response = self.client.call_json(prompt, num_predict=self.num_predict)

            answer = self._sanitize_answer(raw_response.get("answer"))
            if not answer:
                answer = _DEFAULT_FAILURE_ANSWER

            citation_ids = self._normalize_citation_ids(
                raw_response.get("citation_ids")
            )
            citations = self._build_citations(citation_ids, results)
            if citation_ids and not citations:
                answer = _DEFAULT_LIMITED_ANSWER

            return {
                "answer": answer,
                "citations": citations,
            }
        except Exception as exc:
            logger.warning("[RAG_ANSWER_FALLBACK] %s", exc)
            return {
                "answer": _DEFAULT_FAILURE_ANSWER,
                "citations": self._fallback_citations(results),
            }

    def _build_context(self, results: list[dict]) -> str:
        lines: list[str] = []
        for item in results[: self.max_items]:
            precedent_id = item.get("precedent_id")
            title = item.get("title") or ""
            source_url = item.get("source_url") or ""
            score = item.get("score") or 0.0
            text = (item.get("text") or "").strip()[: self.max_text_chars]
            lines.append(
                "\n".join(
                    [
                        f"precedent_id: {precedent_id}",
                        f"title: {title}",
                        f"source_url: {source_url}",
                        f"score: {score}",
                        f"text: {text}",
                    ]
                )
            )
        return "\n\n".join(lines)

    def _sanitize_answer(self, answer: object) -> str:
        text = str(answer or "").strip()
        if not text:
            return ""

        # 내부 식별자나 점수 같은 시스템용 표현이 사용자 답변에 노출되지 않게 막는다.
        text = re.sub(r"\bprecedent_id\s*:\s*\d+\b", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\bsource_url\s*:\s*\S+\b", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\bscore\s*:\s*[-+]?\d*\.?\d+\b", "", text, flags=re.IGNORECASE)
        text = re.sub(
            r"관련된 판례는\s*[\d,\s번호와및]+입니다\.?",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"판례는\s*[\d,\s번호와및]+입니다\.?",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"\s{2,}", " ", text)
        text = re.sub(r"\s+([,.])", r"\1", text)
        text = re.sub(r"\.\s*\.", ".", text)
        return text.strip()

    def _normalize_citation_ids(self, citation_ids: object) -> list[int]:
        if not isinstance(citation_ids, list):
            return []

        normalized: list[int] = []
        for item in citation_ids:
            try:
                normalized.append(int(item))
            except (TypeError, ValueError):
                continue
        return normalized

    def _build_citations(
        self, citation_ids: list[int], results: list[dict]
    ) -> list[dict]:
        result_map = {int(item["precedent_id"]): item for item in results}
        citations: list[dict] = []

        for precedent_id in citation_ids:
            item = result_map.get(precedent_id)
            if not item:
                continue
            citations.append(
                {
                    "precedent_id": int(item["precedent_id"]),
                    "title": item.get("title"),
                    "source_url": item.get("source_url"),
                    "score": float(item.get("score") or 0.0),
                }
            )
        return citations

    def _fallback_citations(self, results: list[dict]) -> list[dict]:
        fallback: list[dict] = []
        for item in results[:3]:
            fallback.append(
                {
                    "precedent_id": int(item["precedent_id"]),
                    "title": item.get("title"),
                    "source_url": item.get("source_url"),
                    "score": float(item.get("score") or 0.0),
                }
            )
        return fallback
