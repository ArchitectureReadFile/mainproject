import re
from datetime import date

_HEADER_END_PATTERN = re.compile(r"(?m)^\s*(주\s*문|이\s*유|청\s*구\s*취\s*지)\s*$")
_CASE_NUMBER_PATTERN = re.compile(
    r"(20\d{2})\s*[-–—]\s*([가-힣]{1,4})\s*[-–—]\s*(\d{1,7})"
    r"|"
    r"(20\d{2})\s*([가-힣]{1,4})\s*(\d{1,7})"
)
_COURT_PATTERN = re.compile(
    r"(대법원|[가-힣]{2,}(?:고등법원|지방법원|행정법원|가정법원|특허법원))"
)
_DATE_PATTERN = re.compile(r"(20\d{2})\.\s*(\d{1,2})\.\s*(\d{1,2})\.")
# \b로 '피고인', '피고소인' 등 중간 매칭 차단, [^\n]{2,}으로 줄바꿈 안 넘고 최소 2글자 이상만 캡처
_PLAINTIFF_PATTERN = re.compile(r"원\s*고\b\s+([^\n]{2,})")
_DEFENDANT_PATTERN = re.compile(r"피\s*고\b\s+([^\n]{2,})")

_HEADER_LABELS = (
    "문서번호",
    "결정유형",
    "생산일자",
    "세목",
    "귀속연도",
    "제목",
    "요지",
    "내용",
    "관련법령",
    "상세내용",
)


class MetadataParser:
    """판결문 메타데이터를 단순 규칙으로 추출합니다."""

    def extract_header(self, pages: list[str], max_chars: int = 8000) -> str:
        full_text = "\n".join(pages)
        match = _HEADER_END_PATTERN.search(full_text)
        return (full_text[: match.start()].strip() if match else full_text.strip())[
            :max_chars
        ]

    def _clean_value(self, value: str | None) -> str | None:
        if not value:
            return None
        cleaned = re.sub(r"\s+", " ", value).strip(" \t:：-")
        return cleaned or None

    def _extract_case_number(self, header: str) -> str | None:
        match = _CASE_NUMBER_PATTERN.search(header)
        if not match:
            return None
        y, code, serial = (
            (match.group(1), match.group(2), match.group(3))
            if match.group(1)
            else (match.group(4), match.group(5), match.group(6))
        )
        return f"{y}{code}{serial}"

    def _extract_case_name(self, header: str, case_number: str | None) -> str | None:
        if not case_number:
            return None
        for line in header.splitlines():
            compact = re.sub(r"\s+", "", line)
            if compact.startswith(case_number):
                return self._clean_value(compact[len(case_number) :])
        return None

    def _extract_court_name(self, header: str) -> str | None:
        cleaned = re.sub(r"\s+", " ", header)
        for label in _HEADER_LABELS:
            cleaned = cleaned.replace(label, " ")
        match = _COURT_PATTERN.search(cleaned)
        if not match:
            return None
        court = match.group(1)
        for prefix in _HEADER_LABELS:
            if court.startswith(prefix):
                court = court[len(prefix) :]
        return self._clean_value(court)

    def _extract_judgment_date(self, header: str) -> date | None:
        dates = []
        for y, m, d in _DATE_PATTERN.findall(header):
            try:
                dates.append(date(int(y), int(m), int(d)))
            except ValueError:
                continue
        return max(dates) if dates else None

    def _extract_parties(self, header: str) -> tuple[str | None, str | None]:
        """'원 고 XXX', '피 고 XXX' 패턴으로 직접 추출합니다."""
        p_match = _PLAINTIFF_PATTERN.search(header)
        d_match = _DEFENDANT_PATTERN.search(header)
        plaintiff = self._clean_value(p_match.group(1)) if p_match else None
        defendant = self._clean_value(d_match.group(1)) if d_match else None
        return plaintiff, defendant

    def parse(self, pages: list[str]) -> dict:
        header = self.extract_header(pages)
        case_number = self._extract_case_number(header)
        plaintiff, defendant = self._extract_parties(header)
        return {
            "case_number": case_number,
            "case_name": self._extract_case_name(header, case_number),
            "court_name": self._extract_court_name(header),
            "judgment_date": self._extract_judgment_date(header),
            "plaintiff": plaintiff,
            "defendant": defendant,
        }
