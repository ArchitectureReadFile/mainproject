"""
RAG 검색 스모크 테스트 스크립트.

실행 예시:
    python scripts/rag_smoke_test.py
    python scripts/rag_smoke_test.py --base-url http://localhost:8000/api
    python scripts/rag_smoke_test.py --query "오피스텔 주거용 건물" --modes dense hybrid answer
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

import requests

DEFAULT_BASE_URL = "http://localhost:8000/api"
DEFAULT_EMAIL = "admin@test.com"
DEFAULT_PASSWORD = "test1234"


@dataclass(frozen=True)
class QueryCase:
    topic: str
    query: str


DEFAULT_CASES: list[QueryCase] = [
    QueryCase(
        topic="소득세/주거용건물개발공급업",
        query="오피스텔이 주거용 건물에 해당하는지 알려줘",
    ),
    QueryCase(
        topic="부가가치세/세무조사",
        query="거래상대방 재조사 협력의무와 중복조사 여부",
    ),
    QueryCase(
        topic="근로소득/주식매수선택권",
        query="주식매수선택권 행사이익 산정 시점과 시가",
    ),
    QueryCase(
        topic="법인세/부당행위·용역수수료",
        query="과다한 용역수수료가 손금으로 인정되는지",
    ),
    QueryCase(
        topic="양도소득세/비상장주식 대주주",
        query="비상장주식 대주주 판단 기준 10억원 초과",
    ),
    QueryCase(
        topic="지방세·법인세/고유목적사업",
        query="고유목적사업 직접 사용과 비과세 예외",
    ),
    QueryCase(
        topic="법인세/대손·회수불능채권",
        query="채권 회수불능 여부 판단 기준",
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RAG 검색 API 스모크 테스트")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="API base URL")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help="로그인 이메일")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="로그인 비밀번호")
    parser.add_argument("--top-k", type=int, default=5, help="검색 결과 개수 (1~10)")
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=["dense", "hybrid", "answer"],
        default=["dense", "hybrid", "answer"],
        help="실행할 테스트 모드",
    )
    parser.add_argument(
        "--query",
        action="append",
        default=[],
        help="직접 실행할 질의. 여러 번 줄 수 있음",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP 요청 타임아웃(초)",
    )
    return parser.parse_args()


def login(
    session: requests.Session, base_url: str, email: str, password: str, timeout: float
) -> None:
    response = session.post(
        f"{base_url.rstrip('/')}/auth/login",
        json={"email": email, "password": password},
        timeout=timeout,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"로그인 실패: status={response.status_code}, body={response.text}"
        )


def get_index_count(session: requests.Session, base_url: str, timeout: float) -> dict:
    response = session.get(f"{base_url.rstrip('/')}/search/count", timeout=timeout)
    if response.status_code != 200:
        raise RuntimeError(
            f"인덱스 개수 조회 실패: status={response.status_code}, body={response.text}"
        )
    return response.json()


def run_search(
    session: requests.Session,
    base_url: str,
    query: str,
    search_mode: str,
    top_k: int,
    timeout: float,
) -> dict:
    response = session.post(
        f"{base_url.rstrip('/')}/search",
        json={
            "query": query,
            "top_k": top_k,
            "search_mode": search_mode,
        },
        timeout=timeout,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"검색 실패({search_mode}): status={response.status_code}, body={response.text}"
        )
    return response.json()


def run_answer(
    session: requests.Session,
    base_url: str,
    query: str,
    top_k: int,
    timeout: float,
) -> dict:
    response = session.post(
        f"{base_url.rstrip('/')}/search/answer",
        json={
            "query": query,
            "top_k": top_k,
            "search_mode": "hybrid",
        },
        timeout=timeout,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"답변 생성 실패: status={response.status_code}, body={response.text}"
        )
    return response.json()


def print_search_result(label: str, payload: dict) -> None:
    print(f"\n[{label}] {payload['query']}")
    results = payload.get("results", [])
    if not results:
        print("  - 결과 없음")
        return

    for idx, item in enumerate(results[:3], start=1):
        title = item.get("title") or "(제목 없음)"
        score = item.get("score")
        source_url = item.get("source_url") or "-"
        print(f"  {idx}. {title}")
        print(f"     score={score:.4f}  url={source_url}")


def print_answer_result(payload: dict) -> None:
    print(f"\n[answer] {payload['query']}")
    print(f"  답변: {payload.get('answer') or '(없음)'}")

    citations = payload.get("citations", [])
    if not citations:
        print("  근거 링크: 없음")
        return

    print("  근거 링크:")
    for idx, item in enumerate(citations[:3], start=1):
        title = item.get("title") or "(제목 없음)"
        source_url = item.get("source_url") or "-"
        score = item.get("score")
        print(f"    {idx}. {title}")
        print(f"       score={score:.4f}  url={source_url}")


def build_cases(custom_queries: list[str]) -> list[QueryCase]:
    if custom_queries:
        return [QueryCase(topic="직접입력", query=query) for query in custom_queries]
    return DEFAULT_CASES


def main() -> int:
    args = parse_args()

    if not 1 <= args.top_k <= 10:
        print("top_k는 1~10 범위여야 합니다.", file=sys.stderr)
        return 2

    session = requests.Session()

    try:
        print(f"로그인 중: {args.email}")
        login(
            session=session,
            base_url=args.base_url,
            email=args.email,
            password=args.password,
            timeout=args.timeout,
        )

        counts = get_index_count(
            session=session,
            base_url=args.base_url,
            timeout=args.timeout,
        )
        print(
            "인덱스 개수:"
            f" dense={counts.get('dense_count', 0)},"
            f" bm25={counts.get('bm25_count', 0)}"
        )

        cases = build_cases(args.query)
        failures = 0

        for case in cases:
            print(f"\n=== {case.topic} ===")

            if "dense" in args.modes:
                try:
                    dense_payload = run_search(
                        session=session,
                        base_url=args.base_url,
                        query=case.query,
                        search_mode="dense",
                        top_k=args.top_k,
                        timeout=args.timeout,
                    )
                    print_search_result("dense", dense_payload)
                except Exception as exc:
                    failures += 1
                    print(f"[FAIL] dense: {exc}")

            if "hybrid" in args.modes:
                try:
                    hybrid_payload = run_search(
                        session=session,
                        base_url=args.base_url,
                        query=case.query,
                        search_mode="hybrid",
                        top_k=args.top_k,
                        timeout=args.timeout,
                    )
                    print_search_result("hybrid", hybrid_payload)
                except Exception as exc:
                    failures += 1
                    print(f"[FAIL] hybrid: {exc}")

            if "answer" in args.modes:
                try:
                    answer_payload = run_answer(
                        session=session,
                        base_url=args.base_url,
                        query=case.query,
                        top_k=args.top_k,
                        timeout=args.timeout,
                    )
                    print_answer_result(answer_payload)
                except Exception as exc:
                    failures += 1
                    print(f"[FAIL] answer: {exc}")

        if failures:
            print(f"\n완료: 일부 실패 있음 ({failures}건)")
            return 1

        print("\n완료: 모든 질의 테스트 성공")
        return 0
    except Exception as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
