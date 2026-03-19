"""
raw 판례 JSON을 seed용 precedent_sources.py로 변환한다.

실행 예시:
    python scripts/generate_precedent_sources.py
    python scripts/generate_precedent_sources.py \
        --input seed_data/law_go_latest_150_raw.json \
        --output seed_data/precedent_sources.py
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DEFAULT_INPUT = "seed_data/law_go_latest_150_raw.json"
DEFAULT_OUTPUT = "seed_data/precedent_sources.py"

# 품질 기준
# 1. topic은 세목/절차/민사집행 등 검색에 유의미한 수준까지만 보수적으로 붙인다.
# 2. notes는 gist 우선, 없거나 지나치게 절차적이면 title을 축약해 쓴다.
# 3. 자주 쓰는 핵심 사건은 URL override로 우선 보정한다.

URL_TOPIC_OVERRIDES: dict[str, str] = {
    "https://taxlaw.nts.go.kr/pd/USEPDA002P.do?ntstDcmId=200000000000018971": "소득세/주거용건물개발공급업",
    "https://taxlaw.nts.go.kr/pd/USEPDA002P.do?ntstDcmId=200000000000019026": "조세소송/기판력",
    "https://taxlaw.nts.go.kr/pd/USEPDA002P.do?ntstDcmId=200000000000018968": "부가가치세/세무조사",
    "https://taxlaw.nts.go.kr/pd/USEPDA002P.do?ntstDcmId=200000000000018996": "소득세/주거용건물개발공급업",
    "https://taxlaw.nts.go.kr/pd/USEPDA002P.do?ntstDcmId=200000000000018980": "근로소득/주식매수선택권",
    "https://taxlaw.nts.go.kr/pd/USEPDA002P.do?ntstDcmId=200000000000019043": "민사집행/사해행위취소",
    "https://taxlaw.nts.go.kr/pd/USEPDA002P.do?ntstDcmId=200000000000019084": "행정소송/고유번호증",
    "https://taxlaw.nts.go.kr/pd/USEPDA002P.do?ntstDcmId=200000000000018840": "법인세/부당행위·용역수수료",
    "https://taxlaw.nts.go.kr/pd/USEPDA002P.do?ntstDcmId=200000000000018969": "양도소득세/비상장주식 대주주",
    "https://taxlaw.nts.go.kr/pd/USEPDA002P.do?ntstDcmId=200000000000019024": "지방세·법인세/고유목적사업",
    "https://taxlaw.nts.go.kr/pd/USEPDA002P.do?ntstDcmId=200000000000018930": "법인세/대손·회수불능채권",
    "https://taxlaw.nts.go.kr/pd/USEPDA002P.do?ntstDcmId=200000000000018812": "민사소송/재심",
    "https://taxlaw.nts.go.kr/pd/USEPDA002P.do?ntstDcmId=000000000000543699": "민사집행/채권자대위·가등기말소",
}


TOPIC_RULES: list[tuple[str, str]] = [
    ("소득세/주거용건물개발공급업", r"오피스텔|주거용 건물개발공급업|주거용 건물"),
    ("근로소득/주식매수선택권", r"주식매수선택권|스톡옵션"),
    ("근로소득/복지포인트", r"복지포인트"),
    ("양도소득세/비상장주식 대주주", r"비상장주식.*대주주|대주주.*비상장주식"),
    ("양도소득세/주택", r"양도소득세.*주택|주택.*양도소득세"),
    ("양도소득세/명의신탁", r"양도소득세.*명의신탁|명의신탁.*양도소득세"),
    ("양도소득세/실지거래가액", r"실지거래가액"),
    ("양도소득세/양도시기", r"양도시기|양도일"),
    ("양도소득세/일반", r"양도소득세"),
    ("법인세/의제배당", r"의제배당"),
    ("법인세/부당행위·용역수수료", r"용역수수료|컨설팅계약|부당행위계산부인|특허권"),
    ("법인세/대손·회수불능채권", r"회수불능|대손|매출채권"),
    ("법인세/원천징수", r"원천징수|법인\(원천\)세|원천\)세"),
    ("법인세/국제조세", r"국제조세|특정외국법인"),
    ("법인세/법인세", r"법인세"),
    ("부가가치세/세금계산서", r"세금계산서"),
    ("부가가치세/면세·환급", r"부가가치세.*면세|면세.*부가가치세|환급창구운영사업자"),
    ("부가가치세/영세율", r"영세율"),
    ("부가가치세/세무조사", r"세무조사|중복조사|재조사"),
    ("부가가치세/용역공급", r"부가가치세|용역의 공급|보조금"),
    ("상속세·증여세/명의신탁", r"증여세.*명의신탁|명의신탁.*증여세"),
    ("상속세·증여세/평가", r"상증세|증여세|상속세|유사매매사례가액|공동주택가격"),
    ("지방세/취득세", r"취득세"),
    ("지방세/담배소비세", r"담배소비세"),
    ("지방세·법인세/고유목적사업", r"고유목적사업"),
    ("조세절차/경정청구", r"경정청구"),
    ("조세절차/과세예고통지", r"과세예고통지"),
    ("조세절차/제척기간", r"제척기간|부과제척기간"),
    ("조세절차/제2차납세의무", r"제2차 납세의무"),
    ("조세절차/전심절차", r"전심절차|전치요건|과세전적부심사"),
    ("조세절차/공시송달", r"공시송달"),
    ("조세소송/기판력", r"기판력"),
    ("행정소송/고유번호증", r"고유번호증"),
    ("행정소송/처분성", r"처분성|항고소송|사업자등록직권말소"),
    ("행정소송/집행정지", r"집행정지|회복하기 어려운 손해"),
    ("행정소송/정보공개", r"정보공개"),
    ("행정소송/조치명령", r"조치명령"),
    (
        "민사집행/채권자대위·가등기말소",
        r"채권자대위|대위 행사|가등기 말소|가등기에 기한 소유권이전등기청구권|소유권이전청구권가등기",
    ),
    ("민사집행/사해행위취소", r"사해행위|채권자취소|채무초과"),
    ("민사집행/배당", r"배당"),
    ("민사집행/추심금", r"추심금|압류"),
    ("민사/근저당권말소", r"근저당권|근저당권말소"),
    ("민사/부당이득", r"부당이득"),
    ("민사/손해배상", r"손해배상"),
    ("민사/구상금", r"구상금"),
    ("민사/재산분할", r"재산분할"),
    ("민사소송/재심", r"재심"),
    ("지식재산/권리범위확인", r"권리범위확인"),
    ("지식재산/등록무효", r"등록무효"),
    ("형사/조세범", r"조세범|허위세금계산서|특정범죄가중처벌등에관한법률위반\(조세\)"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="seed precedent source 생성기")
    parser.add_argument("--input", default=DEFAULT_INPUT, help="raw JSON 경로")
    parser.add_argument(
        "--output", default=DEFAULT_OUTPUT, help="출력 Python 파일 경로"
    )
    return parser.parse_args()


def normalize_text(value: str | None) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def build_search_text(item: dict) -> str:
    return " ".join(normalize_text(item.get(key)) for key in ("title", "gist", "meta"))


def infer_topic(item: dict) -> str:
    url = normalize_text(item.get("url"))
    if url in URL_TOPIC_OVERRIDES:
        return URL_TOPIC_OVERRIDES[url]

    text = build_search_text(item)

    for topic, pattern in TOPIC_RULES:
        if re.search(pattern, text):
            return topic

    if any(token in text for token in ("세", "과세", "세액", "납세", "세무서장")):
        return "조세일반/기타"
    if "법원" in normalize_text(item.get("meta")):
        return "일반판례/기타"
    return "미분류"


def shorten_sentence(text: str, max_length: int = 88) -> str:
    text = normalize_text(text)
    if not text:
        return ""

    parts = re.split(r"(?<=[.!?])\s+|(?<=함)\s+|(?<=음)\s+|(?<=됨)\s+", text)
    first = normalize_text(parts[0]) if parts else text
    if len(first) <= max_length:
        return first
    return first[: max_length - 1].rstrip() + "…"


def clean_title(title: str) -> str:
    title = normalize_text(title)
    title = re.sub(r"^\(\s*심리불속행(?:기각)?\s*\)\s*", "", title)
    title = re.sub(r"^\d{4}\S+\s+", "", title)
    title = re.sub(r"^(원심 요지|원심요지)\)?\s*", "", title)
    return title


def build_notes(item: dict) -> str:
    gist = normalize_text(item.get("gist"))
    title = clean_title(normalize_text(item.get("title")))
    generic_starts = (
        "상고를 모두 기각한다",
        "상고를 기각한다",
        "재심의 소는 부적법하다",
        "【심급】",
    )

    if gist:
        note = shorten_sentence(gist)
        if note and not any(note.startswith(prefix) for prefix in generic_starts):
            return note

    if title:
        return shorten_sentence(title)

    return "판례 요지 확인 필요"


def load_items(input_path: Path) -> list[dict]:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("raw JSON 최상위 구조는 list 여야 합니다.")
    return data


def transform_items(items: list[dict]) -> list[dict]:
    transformed: list[dict] = []
    seen_urls: set[str] = set()

    for item in items:
        url = normalize_text(item.get("url"))
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        transformed.append(
            {
                "topic": infer_topic(item),
                "url": url,
                "notes": build_notes(item),
            }
        )

    return transformed


def render_python(items: list[dict], source_name: str) -> str:
    lines = [
        '"""',
        f"Generated from {source_name}.",
        "원본 raw JSON을 바탕으로 규칙 기반 topic/notes 초안을 생성한 파일이다.",
        "필요하면 일부 항목을 수동 보정해 사용한다.",
        '"""',
        "",
        "SEED_PRECEDENT_SOURCES = [",
    ]

    for item in items:
        lines.extend(
            [
                "    {",
                f'        "topic": {item["topic"]!r},',
                f'        "url": {item["url"]!r},',
                f'        "notes": {item["notes"]!r},',
                "    },",
            ]
        )

    lines.extend(["]", ""])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    items = load_items(input_path)
    transformed = transform_items(items)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_python(transformed, input_path.name),
        encoding="utf-8",
    )

    print(f"입력 건수: {len(items)}")
    print(f"출력 건수: {len(transformed)}")
    print(f"생성 완료: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
