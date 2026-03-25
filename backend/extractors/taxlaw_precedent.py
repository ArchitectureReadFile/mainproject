"""
extractors/taxlaw_precedent.py

taxlaw.nts.go.kr 판례 상세 페이지에서 제목·요지·판결내용·상세내용을 추출한다.

대상 URL 패턴:
    https://taxlaw.nts.go.kr/pd/USEPDA002P.do?ntstDcmId=<ID>

추출 방식:
    SPA 구조이므로 HTML 파싱 불가.
    POST https://taxlaw.nts.go.kr/action.do 를 직접 호출해 JSON으로 수신.

    actionId : ASIQTB002PR01
    paramData: {"dcmDVO": {"ntstDcmId": "<ID>", "ntstDcmClCd": "<분류코드>"}}

    응답 경로: data.ASIQTB002PR01.dcmDVO
        ntstDcmTtl        → 제목
        ntstDcmGistCntn   → 요지
        ntstDcmCntn       → 판결내용 (짧은 요약 본문)

    응답 경로: data.ASIQTB002PR01.dcmHwpEditorDVOList
        dcmFleTy == "html" 항목의 dcmFleByte → 상세내용 HTML 원문

    ntstDcmClCd(분류코드)는 URL에서 읽거나 없으면 "09"(판례) 기본값 사용.

반환:
    {
        "title":        str,           # 판례 제목
        "gist":         str | None,    # 요지
        "text":         str,           # 하위호환: gist + detail_text 합본
        "detail_table": dict | None,   # 사건·원고·피고·원심판결·판결선고
        "detail_text":  str | None,    # 상세내용 HTML에서 추출한 주문+이유 본문
    }

CLI 실행:
    python extractors/taxlaw_precedent.py <URL>
"""

import json
import re
import sys
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup

ACTION_URL = "https://taxlaw.nts.go.kr/action.do"
ACTION_ID = "ASIQTB002PR01"
DEFAULT_CL_CD = "09"  # 판례

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}

# detail_table 파싱 대상 레이블 (정규화된 셀 텍스트 → dict key)
_TABLE_LABEL_MAP = {
    "사건": "사건",
    "원고": "원고",
    "피고": "피고",
    "원심판결": "원심판결",
    "판결선고": "판결선고",
}


# ── 내부 유틸 ─────────────────────────────────────────────────────────────────


def _clean(text: str) -> str:
    """연속 공백·탭·줄바꿈 정리"""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _normalize_label(text: str) -> str:
    """
    셀 텍스트에서 공백을 모두 제거해 레이블 매칭용 키로 반환한다.

    예: "사 건" → "사건", "원 심 판 결" → "원심판결"
    """
    return re.sub(r"\s+", "", text).strip()


def _parse_url(url: str) -> tuple[str, str]:
    """URL에서 (ntstDcmId, ntstDcmClCd) 추출"""
    qs = parse_qs(urlparse(url).query)
    ntst_dcm_id = (qs.get("ntstDcmId") or [""])[0]
    ntst_dcm_cl_cd = (qs.get("ntstDcmClCd") or [DEFAULT_CL_CD])[0]
    if not ntst_dcm_id:
        raise ValueError(f"URL에 ntstDcmId 파라미터가 없습니다: {url}")
    return ntst_dcm_id, ntst_dcm_cl_cd


def _extract_detail_table(soup: BeautifulSoup) -> dict | None:
    """
    상세내용 HTML에서 사건 정보 테이블을 파싱한다.

    taxlaw HTML은 th/td 혼용이 불규칙하므로 th와 td를 구분하지 않고
    모든 셀을 순서대로 순회하며 label → value 쌍을 찾는다.

    규칙:
      - 현재 셀 텍스트를 normalize했을 때 _TABLE_LABEL_MAP에 있으면
        → pending_label로 기억하고 다음 셀을 기다린다.
      - pending_label이 있는 상태에서 다음 셀이 오면
        → 그 텍스트를 value로 매핑하고 pending_label을 초기화한다.
      - pending_label이 없는데 label이 아닌 셀이 오면 스킵한다.

    이 방식으로 (A) 같은 <tr>에 label/value가 있는 경우,
    (B) 다른 <tr>에 label/value가 나뉜 경우 모두 처리한다.
    """
    result: dict[str, str | None] = {k: None for k in _TABLE_LABEL_MAP.values()}
    found_any = False

    for table in soup.find_all("table"):
        pending_label: str | None = None

        for tag in table.find_all(["th", "td"]):
            cell_text = _clean(tag.get_text())
            normalized = _normalize_label(cell_text)

            if normalized in _TABLE_LABEL_MAP:
                # 이 셀이 label — 다음 셀을 value로 받을 준비
                pending_label = normalized
            elif pending_label is not None:
                # 직전 셀이 label이었으므로 이 셀이 value
                if cell_text:
                    result[_TABLE_LABEL_MAP[pending_label]] = cell_text
                    found_any = True
                pending_label = None
            # label도 아니고 pending도 없으면 스킵

    return result if found_any else None


def _extract_detail_text(soup: BeautifulSoup) -> str | None:
    """
    상세내용 HTML에서 주문·이유 본문 텍스트를 추출한다.

    테이블 태그를 제거한 뒤 텍스트를 추출하고 _clean() 처리한다.
    """
    # 테이블은 detail_table로 별도 처리 — 본문에서 제외
    for tag in soup.find_all("table"):
        tag.decompose()

    text = soup.get_text(separator="\n")
    cleaned = _clean(text)
    return cleaned if cleaned else None


def _parse_html_detail(html: str) -> tuple[dict | None, str | None]:
    """상세내용 HTML을 파싱해 (detail_table, detail_text) 반환한다."""
    soup = BeautifulSoup(html, "html.parser")
    detail_table = _extract_detail_table(soup)
    detail_text = _extract_detail_text(soup)
    return detail_table, detail_text


# ── 핵심 함수 ─────────────────────────────────────────────────────────────────


def fetch_taxlaw_precedent(url: str) -> dict:
    """
    판례 상세 API를 호출해 제목·요지·상세내용을 추출한다.

    Returns:
        {
            "title":        str,
            "gist":         str | None,
            "text":         str,           # 하위호환: gist + detail_text 합본
            "detail_table": dict | None,
            "detail_text":  str | None,
        }

    Raises:
        ValueError:          URL에 ntstDcmId 없음
        requests.HTTPError:  4xx / 5xx 응답
        requests.Timeout:    20초 초과
        RuntimeError:        API status != SUCCESS 또는 응답이 JSON이 아님
    """
    ntst_dcm_id, ntst_dcm_cl_cd = _parse_url(url)

    param_data = json.dumps(
        {"dcmDVO": {"ntstDcmId": ntst_dcm_id, "ntstDcmClCd": ntst_dcm_cl_cd}},
        ensure_ascii=False,
    )

    resp = requests.post(
        ACTION_URL,
        headers=_HEADERS,
        data={"actionId": ACTION_ID, "paramData": param_data},
        timeout=20,
    )
    resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")
    if "json" not in content_type:
        raise RuntimeError(
            f"JSON 응답이 아닙니다. content-type={content_type}, body={resp.text[:200]}"
        )

    body = resp.json()
    if body.get("status") != "SUCCESS":
        raise RuntimeError(
            f"API 오류: status={body.get('status')}, message={body.get('message')}"
        )

    action_data = body["data"][ACTION_ID]
    dcm_dvo = action_data["dcmDVO"]

    title = _clean(dcm_dvo.get("ntstDcmTtl") or "")
    gist = _clean(dcm_dvo.get("ntstDcmGistCntn") or "") or None
    judgment = _clean(dcm_dvo.get("ntstDcmCntn") or "")

    # 상세내용 HTML 추출
    detail_table: dict | None = None
    detail_text: str | None = None

    hwp_list = action_data.get("dcmHwpEditorDVOList") or []
    for item in hwp_list:
        if item.get("dcmFleTy") == "html":
            raw_html = item.get("dcmFleByte") or ""
            if raw_html:
                detail_table, detail_text = _parse_html_detail(raw_html)
            break

    # 하위호환 text: gist → detail_text → judgment 우선순위로 합본
    parts = [p for p in [gist, detail_text or judgment] if p]
    text = "\n\n".join(parts)

    return {
        "title": title,
        "gist": gist,
        "text": text,
        "detail_table": detail_table,
        "detail_text": detail_text,
    }


# ── CLI 검증 ──────────────────────────────────────────────────────────────────


def main():
    if len(sys.argv) < 2:
        print("사용법: python extractors/taxlaw_precedent.py <URL>")
        print(
            "예시:   python extractors/taxlaw_precedent.py "
            "'https://taxlaw.nts.go.kr/pd/USEPDA002P.do?ntstDcmId=200000000000016870'"
        )
        sys.exit(1)

    url = sys.argv[1]
    print(f"[→] {url}\n")

    result = fetch_taxlaw_precedent(url)

    print("=" * 60)
    print("[TITLE]")
    print(result["title"] or "⚠ 없음")

    print("\n[GIST]")
    print(result["gist"] or "⚠ 없음")

    print("\n[DETAIL TABLE]")
    if result["detail_table"]:
        for k, v in result["detail_table"].items():
            print(f"  {k}: {v or '-'}")
    else:
        print("⚠ 없음")

    print("\n[DETAIL TEXT 미리보기 (최대 800자)]")
    dt = result["detail_text"]
    if dt:
        print(dt[:800])
        if len(dt) > 800:
            print(f"\n... (총 {len(dt)}자)")
    else:
        print("⚠ 없음")

    print("=" * 60)

    empty = [k for k, v in result.items() if not v]
    if empty:
        print(f"\n⚠  빈 필드: {empty}")
    else:
        print("\n✅ 모든 필드 추출 성공")


if __name__ == "__main__":
    main()
