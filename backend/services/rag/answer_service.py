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

# context header에 포함할 메타 필드 및 레이블.
# precedent_id는 LLM citation 식별용으로만 사용하며 답변에 노출되지 않는다.
# 너무 많은 메타가 context에 실리면 LLM 주의가 분산되므로 핵심만 포함한다.
_CONTEXT_META: list[tuple[str, str]] = [
    ("case_number", "사건번호"),
    ("case_name", "사건명"),
    ("court_name", "법원"),
    ("title", "제목"),
    ("source_url", "출처"),
]

# _sanitize_answer()에서 제거할 context header 레이블 패턴.
# _CONTEXT_META의 레이블과 일치해야 한다.
# "출처: <url>" 은 URL이 답변에 직접 노출되면 부자연스러우므로 제거한다.
# "사건번호/사건명/법원/제목"은 답변 본문에 자연스럽게 쓰일 수 있으므로 제거하지 않는다.
_SANITIZE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bprecedent_id\s*:\s*\d+\b", re.IGNORECASE),
    re.compile(r"\bsource_url\s*:\s*\S+\b", re.IGNORECASE),
    re.compile(r"출처\s*:\s*\S+", re.IGNORECASE),
    re.compile(r"\bscore\s*:\s*[-+]?\d*\.?\d+\b", re.IGNORECASE),
    re.compile(r"chunk_id\s*:\s*\S+", re.IGNORECASE),
]

class RagAnswerService:
    def __init__(self):
        self.client = LLMClient()
        self.max_items = int(os.getenv("RAG_ANSWER_MAX_ITEMS", "5"))
        self.max_text_chars = int(os.getenv("RAG_ANSWER_MAX_TEXT_CHARS", "1500"))
        self.num_predict = int(os.getenv("RAG_ANSWER_NUM_PREDICT", "1024"))

    def generate_answer(self, query: str, results: list[dict]) -> dict:
        if not results:
            return {"answer": _DEFAULT_EMPTY_ANSWER, "citations": []}

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

            return {"answer": answer, "citations": citations}
        except Exception as exc:
            logger.warning("[RAG_ANSWER_FALLBACK] %s", exc)
            return {
                "answer": _DEFAULT_FAILURE_ANSWER,
                "citations": self._fallback_citations(results),
            }

    def _build_context(self, results: list[dict]) -> str:
        """
        grouped result(precedent 단위) 기준으로 LLM context를 구성한다.

        header 형식 (= _sanitize_answer 제거 대상과 대응):
            precedent_id: <id>   ← 내부 식별자, 답변 노출 금지
            사건번호: <case_number>
            사건명:   <case_name>
            법원:     <court_name>
            제목:     <title>
            출처:     <source_url>   ← URL 직접 노출 방지를 위해 sanitize에서 제거

        사건번호/사건명/법원/제목은 답변 본문에 자연스럽게 쓰일 수 있으므로 sanitize 제거 대상이 아님.
        """
        lines: list[str] = []
        for item in results[: self.max_items]:
            precedent_id = item.get("precedent_id")
            chunks = item.get("chunks") or []

            header_lines = [f"precedent_id: {precedent_id}"]
            for field, label in _CONTEXT_META:
                value = item.get(field)
                if value:
                    header_lines.append(f"{label}: {value}")

            header = "\n".join(header_lines)

            chunk_lines: list[str] = []
            total_chars = 0
            for chunk in chunks:
                section = chunk.get("section_title") or "본문"
                text = (chunk.get("text") or "").strip()
                remaining = self.max_text_chars - total_chars
                if remaining <= 0:
                    break
                text = text[:remaining]
                total_chars += len(text)
                chunk_lines.append(f"section: {section}\ntext: {text}")

            lines.append(header + "\n" + "\n\n".join(chunk_lines))

        return "\n\n".join(lines)

    def _sanitize_answer(self, answer: object) -> str:
        """
        LLM 답변에서 내부 식별자 및 노출 불필요한 메타 필드를 제거한다.

        제거 대상 (_SANITIZE_PATTERNS):
            precedent_id: <n>   내부 식별자
            source_url: <url>   영문 키 형태
            출처: <url>          한글 레이블 형태 (context header 형식과 일치)
            score: <n>          내부 점수
            chunk_id: <id>      내부 청크 ID

        유지 대상:
            사건번호 / 사건명 / 법원 / 제목 — 답변 본문에 자연스럽게 사용 가능
        """
        text = str(answer or "").strip()
        if not text:
            return ""
        for pattern in _SANITIZE_PATTERNS:
            text = pattern.sub("", text)
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
                    "case_number": item.get("case_number"),
                    "case_name": item.get("case_name"),
                    "court_name": item.get("court_name"),
                    "source_url": item.get("source_url"),
                    "score": float(item.get("score") or 0.0),
                }
            )
        return citations

    def _fallback_citations(self, results: list[dict]) -> list[dict]:
        return [
            {
                "precedent_id": int(item["precedent_id"]),
                "title": item.get("title"),
                "case_number": item.get("case_number"),
                "case_name": item.get("case_name"),
                "court_name": item.get("court_name"),
                "source_url": item.get("source_url"),
                "score": float(item.get("score") or 0.0),
            }
            for item in results[:3]
        ]
