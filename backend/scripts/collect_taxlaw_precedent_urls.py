"""
국가법령정보센터 최신 판례 목록에서 taxlaw.nts.go.kr 상세 URL만 대량 수집한다.

현재 precedent seed는 taxlaw 도메인만 허용하므로,
law.go.kr 내부 상세 URL은 제외하고 외부 taxlaw 링크만 모은다.

실행 예시:
    python scripts/collect_taxlaw_precedent_urls.py --limit 10000
    python scripts/collect_taxlaw_precedent_urls.py --limit 10000 --per-page 150
"""

from __future__ import annotations

import argparse
import json
import re
from html import unescape
from pathlib import Path

import requests

LIST_URL = "https://www.law.go.kr/precScListR.do?menuId=7&subMenuId=47&tabMenuId=213"
DEFAULT_OUTPUT = "seed_data/taxlaw_precedent_urls_10000.json"

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.law.go.kr/precSc.do?menuId=7&subMenuId=47&tabMenuId=213&query=",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="taxlaw precedent URL 대량 수집")
    parser.add_argument(
        "--limit", type=int, default=10000, help="수집할 taxlaw URL 개수"
    )
    parser.add_argument("--page", type=int, default=1, help="시작 페이지")
    parser.add_argument("--per-page", type=int, default=150, help="페이지당 요청 개수")
    parser.add_argument(
        "--max-pages", type=int, default=200, help="최대 조회 페이지 수"
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help="저장할 JSON 경로",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP 타임아웃")
    return parser.parse_args()


def normalize_text(text: str | None) -> str:
    raw = unescape(text or "")
    no_tags = re.sub(r"<[^>]+>", " ", raw)
    compact = re.sub(r"\s+", " ", no_tags)
    return compact.strip()


def build_payload(per_page: int, page: int) -> dict[str, str]:
    return {
        "q": "*",
        "section": "bdyText",
        "outmax": str(per_page),
        "pg": str(page),
        "fsort": "21,10,30",
        "precSeq": "0",
        "dtlYn": "N",
    }


def fetch_list_html(per_page: int, page: int, timeout: float) -> str:
    response = requests.post(
        LIST_URL,
        headers=REQUEST_HEADERS,
        data=build_payload(per_page, page),
        timeout=timeout,
    )
    response.raise_for_status()
    return response.text


def parse_total_count(html: str) -> int | None:
    match = re.search(r"<div id=\"readNumDiv\".*?<strong>([\d,]+)</strong>", html, re.S)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def resolve_taxlaw_url(onclick: str) -> str:
    external_match = re.search(
        r"showExternalLink\('[^']*',\s*'[^']*',\s*'([^']+)'\)",
        onclick,
    )
    if not external_match:
        return ""
    url = external_match.group(1)
    if "taxlaw.nts.go.kr" not in url:
        return ""
    return url


def parse_taxlaw_items(html: str) -> list[dict[str, str]]:
    pattern = re.compile(
        r"<td class=\"s_tit\">\s*"
        r"<a [^>]*onclick=\"(?P<onclick>[^\"]+)\"[^>]*>"
        r"\s*(?P<title>.*?)\s*<span>\s*(?P<meta>.*?)\s*</span>\s*</a>\s*</td>"
        r".*?"
        r"<td class=\"tl\">\s*<a [^>]*>(?P<gist>.*?)</a>\s*</td>",
        re.S,
    )

    items: list[dict[str, str]] = []
    for match in pattern.finditer(html):
        url = resolve_taxlaw_url(match.group("onclick"))
        if not url:
            continue

        items.append(
            {
                "title": normalize_text(match.group("title")),
                "url": url,
                "gist": normalize_text(match.group("gist")),
                "meta": normalize_text(match.group("meta")),
            }
        )
    return items


def collect_taxlaw_urls(
    limit: int,
    start_page: int,
    per_page: int,
    max_pages: int,
    timeout: float,
) -> tuple[int | None, list[dict[str, str]]]:
    all_items: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    total_count: int | None = None

    for offset in range(max_pages):
        page = start_page + offset
        html = fetch_list_html(per_page=per_page, page=page, timeout=timeout)
        if total_count is None:
            total_count = parse_total_count(html)

        page_items = parse_taxlaw_items(html)
        if not page_items:
            break

        new_count = 0
        for item in page_items:
            url = item["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            all_items.append(item)
            new_count += 1
            if len(all_items) >= limit:
                return total_count, all_items

        if new_count == 0:
            break

    return total_count, all_items


def save_items(output: str, items: list[dict[str, str]]) -> Path:
    output_path = Path(output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(items, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def main() -> int:
    args = parse_args()
    if args.limit <= 0:
        raise SystemExit("--limit 는 1 이상의 정수여야 합니다.")
    if args.page <= 0:
        raise SystemExit("--page 는 1 이상의 정수여야 합니다.")
    if args.per_page <= 0:
        raise SystemExit("--per-page 는 1 이상의 정수여야 합니다.")
    if args.max_pages <= 0:
        raise SystemExit("--max-pages 는 1 이상의 정수여야 합니다.")

    total_count, items = collect_taxlaw_urls(
        limit=args.limit,
        start_page=args.page,
        per_page=args.per_page,
        max_pages=args.max_pages,
        timeout=args.timeout,
    )
    saved_path = save_items(args.output, items)

    print(f"총 검색 건수: {total_count if total_count is not None else '알 수 없음'}")
    print(f"수집 건수(taxlaw only): {len(items)}")
    print(f"저장 완료: {saved_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
