"""
extractors/taxlaw_precedent.py

taxlaw.nts.go.kr 판례 상세 페이지에서 제목·요지·판결내용을 추출한다.

대상 URL 패턴:
    https://taxlaw.nts.go.kr/pd/USEPDA002P.do?ntstDcmId=<ID>

추출 방식:
    SPA 구조이므로 HTML 파싱 불가.
    POST https://taxlaw.nts.go.kr/action.do 를 직접 호출해 JSON으로 수신.

    actionId : ASIQTB002PR01
    paramData: {"dcmDVO": {"ntstDcmId": "<ID>", "ntstDcmClCd": "<분류코드>"}}

    응답 경로: data.ASIQTB002PR01.dcmDVO
        ntstDcmTtl      → 제목
        ntstDcmGistCntn → 요지
        ntstDcmCntn     → 판결내용

    ntstDcmClCd(분류코드)는 URL에서 읽거나 없으면 "09"(판례) 기본값 사용.

반환:
    {"title": str, "text": str}
    text = 요지 + 판결내용 을 "\\n\\n" 으로 합친 문자열.
    title 또는 text 가 빈 문자열일 수 있음 — 호출 측에서 검증 필요.

CLI 실행:
    python extractors/taxlaw_precedent.py <URL>
"""

import json
import re
import sys
from urllib.parse import parse_qs, urlparse

import requests

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


# ── 내부 유틸 ─────────────────────────────────────────────────────────────────
def _clean(text: str) -> str:
    """연속 공백·탭·줄바꿈 정리"""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _parse_url(url: str) -> tuple[str, str]:
    """URL에서 (ntstDcmId, ntstDcmClCd) 추출"""
    qs = parse_qs(urlparse(url).query)
    ntst_dcm_id = (qs.get("ntstDcmId") or [""])[0]
    ntst_dcm_cl_cd = (qs.get("ntstDcmClCd") or [DEFAULT_CL_CD])[0]
    if not ntst_dcm_id:
        raise ValueError(f"URL에 ntstDcmId 파라미터가 없습니다: {url}")
    return ntst_dcm_id, ntst_dcm_cl_cd


# ── 핵심 함수 ─────────────────────────────────────────────────────────────────
def fetch_taxlaw_precedent(url: str) -> dict:
    """
    판례 상세 API를 호출해 제목과 본문을 추출한다.

    Args:
        url: 판례 상세 페이지 URL
             예) https://taxlaw.nts.go.kr/pd/USEPDA002P.do?ntstDcmId=200000000000016870

    Returns:
        {
            "title": str,  # 판례 제목. 추출 실패 시 빈 문자열.
            "text":  str,  # 요지 + 판결내용을 "\\n\\n" 으로 합친 문자열.
                           # 추출 실패 시 빈 문자열.
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

    # 세션 재사용 없이 매 호출마다 새 요청 — 세션 상태 오염 방지
    resp = requests.post(
        ACTION_URL,
        headers=_HEADERS,
        data={"actionId": ACTION_ID, "paramData": param_data},
        timeout=20,
    )
    resp.raise_for_status()

    # JSON이 아닌 응답(HTML 등) 방어
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

    dcm_dvo = body["data"][ACTION_ID]["dcmDVO"]

    title = _clean(dcm_dvo.get("ntstDcmTtl") or "")
    summary = _clean(dcm_dvo.get("ntstDcmGistCntn") or "")
    judgment = _clean(dcm_dvo.get("ntstDcmCntn") or "")

    parts = [p for p in [summary, judgment] if p]
    text = "\n\n".join(parts)

    return {"title": title, "text": text}


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
    print("\n[TEXT 미리보기 (최대 800자)]")
    print(result["text"][:800] or "⚠ 없음")
    if len(result["text"]) > 800:
        print(f"\n... (총 {len(result['text'])}자)")
    print("=" * 60)

    empty = [k for k, v in result.items() if not v]
    if empty:
        print(f"\n⚠  빈 필드: {empty}")
    else:
        print("\n✅ 모든 필드 추출 성공")


if __name__ == "__main__":
    main()
