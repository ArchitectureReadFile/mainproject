import re

# 행정 메타 헤더 라벨 단독 줄 — MetadataParser가 이미 추출하므로 LLM 입력에서 제거
# 주의: '요지' 는 제외 — 심리불속행 판결에서 사실관계 추출에 필요
_META_LABEL_PATTERN = re.compile(
    r"^(문서번호|결정유형|생산일자|세목|귀속연도|제목|내용|관련법령|상세내용"
    r"|국세법령정보시스템|National Tax Law Information System)\b"
)

_TABLE_COLUMN_KEYWORDS = (
    "세목",
    "구분",
    "내역",
    "고지세액",
    "체납액",
    "납세의무",
    "귀속년월",
    "납부기한",
    "평가액",
    "평가방법",
)


class TextSplitter:
    """판결문 텍스트에서 이유 섹션 추출 및 노이즈 정리를 담당합니다."""

    def clean_noise(self, text: str) -> str:
        """LLM 입력 전 불필요한 줄을 제거하고 공백을 정리합니다."""
        lines = text.split("\n")
        cleaned = [line for line in lines if not self._is_noise_line(line)]
        # 연속된 빈 줄을 하나로 압축
        result = re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned))
        return result.strip()

    def _is_noise_line(self, line: str) -> bool:
        s = line.strip()
        if not s:
            return False
        # 행정 메타 헤더 라벨 줄
        if _META_LABEL_PATTERN.match(s):
            return True
        # 금액 단위 표기
        if re.match(r"^금액\s*단위", s):
            return True
        if re.match(r"^단위\s*원?[\s:\(（]", s):
            return True
        # 숫자만 있는 각주 줄
        if re.match(r"^\d+\)\s*[\d,\.\s]+$", s):
            return True
        # 표 헤더 키워드 2개 이상 포함
        if len(s) <= 100 and sum(1 for kw in _TABLE_COLUMN_KEYWORDS if kw in s) >= 2:
            return True
        return False

    def extract_reason_section(self, full_text: str) -> str:
        """판결문 본문에서 '이유' 섹션을 추출합니다."""
        start_match = re.search(r"(?m)^\s*이\s*유\s*$", full_text) or re.search(
            r"(?m)^\s*이유\s*$", full_text
        )
        if not start_match:
            return ""

        tail = full_text[start_match.end() :]
        end_match = re.search(r"(?m)^\s*(판사|재판장|주문|결론)\s*$", tail)
        return tail[: end_match.start()].strip() if end_match else tail.strip()
