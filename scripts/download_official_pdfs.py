#!/usr/bin/env python3
"""
Download up to N PDFs per configured official-source site into output/<site>/.

The crawler stays within each source domain, starts from a few curated seed pages,
walks HTML pages breadth-first, and downloads links that are either direct PDF URLs
or attachment/download endpoints whose response content-type resolves to PDF.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from collections import deque
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, quote, unquote, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)

PDF_HINT_RE = re.compile(
    r"(\.pdf(?:$|[?#])|download|down|attach|file|viewer|bitstream|viewer\.do)",
    re.IGNORECASE,
)

SKIP_SCHEMES = {"mailto", "javascript", "tel", ""}


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.links.append(value.strip())


@dataclass(frozen=True)
class Source:
    name: str
    allowed_hosts: tuple[str, ...]
    seeds: tuple[str, ...]


SOURCES: tuple[Source, ...] = (
    Source(
        name="nars",
        allowed_hosts=("www.nars.go.kr", "nars.go.kr", "m.nars.go.kr"),
        seeds=(
            "https://www.nars.go.kr/brdList.do?cmsCd=CM0155",
            "https://www.nars.go.kr/news/list.do?cmsCode=CM0026",
            "https://m.nars.go.kr/report/list.do?cmsCode=CM0018",
        ),
    ),
    Source(
        name="nts",
        allowed_hosts=("www.nts.go.kr", "nts.go.kr", "j.nts.go.kr"),
        seeds=(
            "https://www.nts.go.kr/nts/na/ntt/selectNttList.do?mi=7134&bbsId=2209",
            "https://j.nts.go.kr/nts/na/ntt/selectNttList.do?bbsId=1143&mi=135770",
            "https://j.nts.go.kr/nts/na/ntt/selectNttList.do?adit1Column=%EB%B2%95%EC%9D%B8%EC%84%B8&bbsId=1143&mi=135773",
        ),
    ),
    Source(
        name="moleg",
        allowed_hosts=("www.moleg.go.kr", "moleg.go.kr"),
        seeds=(
            "https://www.moleg.go.kr/board.es?mid=a10111010000&bid=0049",
            "https://www.moleg.go.kr/board.es?mid=a10111020000&bid=0049",
        ),
    ),
    Source(
        name="kipf",
        allowed_hosts=("repository.kipf.re.kr", "www.kipf.re.kr", "kipf.re.kr"),
        seeds=(
            "https://repository.kipf.re.kr/",
            "https://repository.kipf.re.kr/handle/201201/3402",
            "https://repository.kipf.re.kr/handle/201201/3401",
        ),
    ),
    Source(
        name="moef",
        allowed_hosts=("www.moef.go.kr", "moef.go.kr"),
        seeds=(
            "https://www.moef.go.kr/nw/nwel/nesl/nesl.jsp",
            "https://www.moef.go.kr/nw/nes/detailNesDtaView.do?searchBbsId1=MOSFBBS_000000000028",
            "https://www.moef.go.kr/nw/nes/detailNesDtaView.do?searchBbsId1=MOSFBBS_000000000029",
        ),
    ),
)


def normalize_url(base_url: str, raw_url: str) -> str | None:
    joined = urljoin(base_url, raw_url)
    parsed = urlparse(joined)
    if parsed.scheme.lower() in SKIP_SCHEMES:
        return None
    if parsed.scheme.lower() not in {"http", "https"}:
        return None

    cleaned_query = "&".join(
        f"{quote(k, safe='[]')}={quote(v, safe='/:[]')}"
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
    )
    normalized = parsed._replace(fragment="", query=cleaned_query)
    return urlunparse(normalized)


def is_allowed_host(url: str, allowed_hosts: Iterable[str]) -> bool:
    host = urlparse(url).netloc.lower()
    return any(host == allowed or host.endswith(f".{allowed}") for allowed in allowed_hosts)


def request_url(url: str, *, referer: str | None = None, timeout: int = 20):
    headers = {"User-Agent": USER_AGENT}
    if referer:
        headers["Referer"] = referer
    req = Request(url, headers=headers)
    return urlopen(req, timeout=timeout)


def fetch_html(url: str) -> tuple[str | None, str | None]:
    try:
        with request_url(url) as resp:
            content_type = (resp.headers.get("Content-Type") or "").lower()
            if "html" not in content_type:
                return None, None
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace"), str(resp.geturl())
    except Exception:
        return None, None


def extract_links(base_url: str, html: str, allowed_hosts: Iterable[str]) -> list[str]:
    parser = LinkParser()
    parser.feed(html)

    result: list[str] = []
    seen: set[str] = set()
    for raw_link in parser.links:
        normalized = normalize_url(base_url, raw_link)
        if not normalized:
            continue
        if not is_allowed_host(normalized, allowed_hosts):
            continue
        if normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def sanitize_filename(name: str) -> str:
    name = re.sub(r"[^\w.\-]+", "_", name.strip(), flags=re.UNICODE)
    name = re.sub(r"_+", "_", name)
    name = name.strip("._")
    return name or "document"


def infer_filename(url: str, headers) -> str:
    disposition = headers.get("Content-Disposition") or ""
    filename_match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', disposition)
    if filename_match:
        filename = unquote(filename_match.group(1).strip())
    else:
        path = urlparse(url).path
        filename = Path(path).name or "document.pdf"

    if not filename.lower().endswith(".pdf"):
        filename = f"{filename}.pdf"
    return sanitize_filename(filename)


def looks_like_pdf_candidate(url: str) -> bool:
    return bool(PDF_HINT_RE.search(url))


def download_pdf(url: str, dest_dir: Path, *, referer: str | None = None) -> Path | None:
    try:
        with request_url(url, referer=referer, timeout=30) as resp:
            content_type = (resp.headers.get("Content-Type") or "").lower()
            if "pdf" not in content_type:
                return None

            final_url = str(resp.geturl())
            filename = infer_filename(final_url, resp.headers)
            candidate = dest_dir / filename
            stem = candidate.stem
            suffix = candidate.suffix
            counter = 1
            while candidate.exists():
                candidate = dest_dir / f"{stem}_{counter}{suffix}"
                counter += 1

            with candidate.open("wb") as fp:
                fp.write(resp.read())
            return candidate
    except Exception:
        return None


def crawl_source(
    source: Source,
    output_root: Path,
    *,
    max_pdfs: int,
    max_pages: int,
    delay: float,
) -> dict[str, int]:
    dest_dir = output_root / source.name
    dest_dir.mkdir(parents=True, exist_ok=True)

    queue: deque[str] = deque(source.seeds)
    visited_pages: set[str] = set()
    attempted_downloads: set[str] = set()

    pages_seen = 0
    downloaded = 0

    while queue and downloaded < max_pdfs and pages_seen < max_pages:
        current = queue.popleft()
        if current in visited_pages:
            continue
        visited_pages.add(current)

        if looks_like_pdf_candidate(current):
            attempted_downloads.add(current)
            saved = download_pdf(current, dest_dir)
            if saved:
                downloaded += 1
                print(f"[{source.name}] downloaded {downloaded}/{max_pdfs}: {saved.name}")
                time.sleep(delay)
                continue

        html, final_url = fetch_html(current)
        pages_seen += 1
        if not html or not final_url:
            time.sleep(delay)
            continue

        for link in extract_links(final_url, html, source.allowed_hosts):
            if link in visited_pages:
                continue

            if looks_like_pdf_candidate(link) and link not in attempted_downloads:
                attempted_downloads.add(link)
                saved = download_pdf(link, dest_dir, referer=final_url)
                if saved:
                    downloaded += 1
                    print(f"[{source.name}] downloaded {downloaded}/{max_pdfs}: {saved.name}")
                    if downloaded >= max_pdfs:
                        break

            if link not in visited_pages:
                queue.append(link)

        time.sleep(delay)

    return {
        "downloaded": downloaded,
        "pages_seen": pages_seen,
        "queue_remaining": len(queue),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        default="output",
        help="Directory where site-separated folders will be created.",
    )
    parser.add_argument(
        "--per-site",
        type=int,
        default=50,
        help="Maximum number of PDFs to download for each source site.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=600,
        help="Maximum number of HTML pages to crawl per source site.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.2,
        help="Delay between requests in seconds.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    print(f"Saving PDFs under: {output_root}")
    for source in SOURCES:
        print(f"\n== Crawling {source.name} ==")
        stats = crawl_source(
            source,
            output_root,
            max_pdfs=args.per_site,
            max_pages=args.max_pages,
            delay=args.delay,
        )
        print(
            f"[{source.name}] finished: "
            f"downloaded={stats['downloaded']}, "
            f"pages_seen={stats['pages_seen']}, "
            f"queue_remaining={stats['queue_remaining']}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
