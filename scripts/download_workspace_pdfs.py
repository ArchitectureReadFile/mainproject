#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import os
import re
import time
from pathlib import Path
from typing import Callable
from urllib.parse import quote, unquote, urljoin
from urllib.request import Request, urlopen
from urllib.parse import urlencode


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)


def fetch_text(url: str, *, referer: str | None = None) -> str:
    headers = {"User-Agent": USER_AGENT}
    if referer:
        headers["Referer"] = referer
    req = Request(url, headers=headers)
    with urlopen(req, timeout=30) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def download_file(url: str, dest: Path, *, referer: str | None = None) -> bool:
    headers = {"User-Agent": USER_AGENT}
    if referer:
        headers["Referer"] = referer
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=60) as resp:
            content_type = (resp.headers.get("Content-Type") or "").lower()
            disposition = (resp.headers.get("Content-Disposition") or "").lower()
            if (
                "pdf" not in content_type
                and ".pdf" not in disposition
                and not dest.name.lower().endswith(".pdf")
            ):
                return False
            dest.write_bytes(resp.read())
            return True
    except Exception:
        return False


def post_text(url: str, data: dict[str, str], *, referer: str | None = None) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }
    if referer:
        headers["Referer"] = referer
    payload = urlencode(data).encode("utf-8")
    req = Request(url, data=payload, headers=headers, method="POST")
    with urlopen(req, timeout=30) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def post_download(url: str, data: dict[str, str], dest: Path, *, referer: str | None = None) -> bool:
    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }
    if referer:
        headers["Referer"] = referer
    payload = urlencode(data).encode("utf-8")
    req = Request(url, data=payload, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=60) as resp:
            content_type = (resp.headers.get("Content-Type") or "").lower()
            disposition = (resp.headers.get("Content-Disposition") or "").lower()
            if (
                "pdf" not in content_type
                and ".pdf" not in disposition
                and not dest.name.lower().endswith(".pdf")
            ):
                return False
            dest.write_bytes(resp.read())
            return True
    except Exception:
        return False


def sanitize_filename(name: str) -> str:
    name = html.unescape(name)
    name = name.replace("/", "_").replace("\\", "_")
    name = re.sub(r"\s+", " ", name).strip()
    name = re.sub(r'[<>:"|?*]+', "_", name)
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    return name[:180] or "document.pdf"


def unique_path(dest_dir: Path, filename: str) -> Path:
    candidate = dest_dir / sanitize_filename(filename)
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    counter = 1
    while True:
        attempt = dest_dir / f"{stem}_{counter}{suffix}"
        if not attempt.exists():
            return attempt
        counter += 1


def collect_nars(per_site: int, output_dir: Path, delay: float) -> int:
    count = 0
    seen_doc_ids: set[str] = set()
    page = 1
    while count < per_site:
        list_url = f"https://www.nars.go.kr/report/list.do?page={page}&cmsCode=CM0043"
        text = fetch_text(list_url)
        matches = re.findall(
            r"fileDownLoad\('([^']+)'\s*,\s*'([^']+\.pdf)'\)",
            text,
            flags=re.IGNORECASE,
        )
        if not matches:
            break
        for doc_id, filename in matches:
            if doc_id in seen_doc_ids:
                continue
            seen_doc_ids.add(doc_id)
            dl_url = (
                "https://www.nars.go.kr/fileDownload2.do"
                f"?doc_id={quote(doc_id)}&fileName={quote(html.unescape(filename))}"
                f"&timeStamp={int(time.time() * 1000)}"
            )
            dest = unique_path(output_dir, filename)
            if download_file(dl_url, dest, referer=list_url):
                count += 1
                print(f"[nars] {count}/{per_site} {dest.name}", flush=True)
                if count >= per_site:
                    break
            time.sleep(delay)
        page += 1
    return count


def collect_nts(per_site: int, output_dir: Path, delay: float) -> int:
    count = 0
    seen_ntt: set[str] = set()
    seen_files: set[str] = set()
    page = 1
    while count < per_site and page <= 80:
        list_url = (
            "https://j.nts.go.kr/nts/na/ntt/selectNttList.do"
            f"?bbsId=1143&mi=135770&currPage={page}"
        )
        text = fetch_text(list_url)
        ntt_ids = re.findall(r'class="nttInfoBtn"[^>]+data-id="(\d+)"', text)
        if not ntt_ids:
            break
        for ntt_id in ntt_ids:
            if ntt_id in seen_ntt:
                continue
            seen_ntt.add(ntt_id)
            detail_url = (
                "https://j.nts.go.kr/nts/na/ntt/selectNttInfo.do"
                f"?mi=135770&bbsId=1143&nttSn={ntt_id}"
            )
            detail = fetch_text(detail_url, referer=list_url)
            attachments = re.findall(
                r'href="(/comm/nttFileDownload\.do\?fileKey=[^"]+)"[\s\S]{0,200}?class="fileName"[\s\S]{0,200}?>([^<]+\.pdf)',
                detail,
                flags=re.IGNORECASE,
            )
            for rel_url, filename in attachments:
                file_url = urljoin(detail_url, html.unescape(rel_url))
                if file_url in seen_files:
                    continue
                seen_files.add(file_url)
                dest = unique_path(output_dir, filename)
                if download_file(file_url, dest, referer=detail_url):
                    count += 1
                    print(f"[nts] {count}/{per_site} {dest.name}", flush=True)
                    if count >= per_site:
                        break
                time.sleep(delay)
            if count >= per_site:
                break
        page += 1
    return count


def collect_moleg(per_site: int, output_dir: Path, delay: float) -> int:
    count = 0
    seen_detail: set[str] = set()
    seen_files: set[str] = set()
    page = 1
    while count < per_site and page <= 60:
        list_url = (
            "https://www.moleg.go.kr/board.es"
            f"?mid=a10111010000&bid=0049&act=list&nPage={page}"
        )
        text = fetch_text(list_url)
        detail_urls = re.findall(
            r'href="(/board\.es\?[^"]*act=view[^"]*list_no=\d+[^"]*)"',
            text,
            flags=re.IGNORECASE,
        )
        if not detail_urls:
            break
        for rel_detail_url in detail_urls:
            detail_url = urljoin(list_url, html.unescape(rel_detail_url))
            if detail_url in seen_detail:
                continue
            seen_detail.add(detail_url)
            detail = fetch_text(detail_url, referer=list_url)
            attachments = re.findall(
                r'href="(/boardDownload\.es\?[^"]+)"[^>]*title="([^"]+\.pdf)"',
                detail,
                flags=re.IGNORECASE,
            )
            for rel_file_url, filename in attachments:
                file_url = urljoin(detail_url, html.unescape(rel_file_url))
                if file_url in seen_files:
                    continue
                seen_files.add(file_url)
                dest = unique_path(output_dir, filename)
                if download_file(file_url, dest, referer=detail_url):
                    count += 1
                    print(f"[moleg] {count}/{per_site} {dest.name}", flush=True)
                    if count >= per_site:
                        break
                time.sleep(delay)
            if count >= per_site:
                break
        page += 1
    return count


def collect_lawclerk(per_site: int, output_dir: Path, delay: float) -> int:
    count = 0
    seen_detail: set[str] = set()
    seen_files: set[str] = set()
    page = 1
    while count < per_site and page <= 40:
        list_url = (
            "https://lawclerk.scourt.go.kr/portal/news/NewsListAction.work"
            f"?gubun=4&pageIndex={page}"
        )
        text = fetch_text(list_url)
        detail_urls = re.findall(
            r"href='(/portal/news/NewsViewAction\.work\?[^']+seqnum=\d+[^']*)'",
            text,
            flags=re.IGNORECASE,
        )
        if not detail_urls:
            break
        for rel_detail_url in detail_urls:
            detail_url = urljoin(list_url, html.unescape(rel_detail_url))
            if detail_url in seen_detail:
                continue
            seen_detail.add(detail_url)
            detail = fetch_text(detail_url, referer=list_url)
            attachments = re.findall(
                r'href="(https://www\.scourt\.go\.kr/sjudge/[^"]+\.pdf)"[^>]*>\s*([^<]+\.pdf)',
                detail,
                flags=re.IGNORECASE,
            )
            for file_url, filename in attachments:
                if file_url in seen_files:
                    continue
                seen_files.add(file_url)
                dest = unique_path(output_dir, filename)
                if download_file(file_url, dest, referer=detail_url):
                    count += 1
                    print(f"[lawclerk] {count}/{per_site} {dest.name}", flush=True)
                    if count >= per_site:
                        break
                time.sleep(delay)
            if count >= per_site:
                break
        page += 1
    return count


def collect_seoul_court(per_site: int, output_dir: Path, delay: float) -> int:
    count = 0
    seen_detail: set[str] = set()
    seen_files: set[str] = set()
    page = 1
    while count < per_site and page <= 80:
        list_url = (
            "https://seoul.scourt.go.kr/dcboard/new/DcNewsListAction.work"
            f"?gubun=44&pageSize=10&currentPage={page}"
        )
        text = fetch_text(list_url)
        detail_urls = re.findall(
            r'href="(/dcboard/new/DcNewsViewAction\.work\?[^"]+seqnum=\d+[^"]*)"',
            text,
            flags=re.IGNORECASE,
        )
        if not detail_urls:
            break
        for rel_detail_url in detail_urls:
            detail_url = urljoin(list_url, html.unescape(rel_detail_url))
            if detail_url in seen_detail:
                continue
            seen_detail.add(detail_url)
            detail = fetch_text(detail_url, referer=list_url)
            attachments = re.findall(
                r"javascript:download\('([^']+\.pdf)','([^']+\.pdf)'\)",
                detail,
                flags=re.IGNORECASE,
            )
            for file_key, filename in attachments:
                if file_key in seen_files:
                    continue
                seen_files.add(file_key)
                dest = unique_path(output_dir, filename)
                if post_download(
                    "https://file.scourt.go.kr/AttachDownload",
                    {
                        "file": file_key,
                        "path": "003",
                        "downFile": unquote(filename),
                    },
                    dest,
                    referer=detail_url,
                ):
                    count += 1
                    print(f"[seoul_court] {count}/{per_site} {dest.name}", flush=True)
                    if count >= per_site:
                        break
                time.sleep(delay)
            if count >= per_site:
                break
        page += 1
    return count


COLLECTORS: list[tuple[str, Callable[[int, Path, float], int]]] = [
    ("nars", collect_nars),
    ("nts", collect_nts),
    ("moleg", collect_moleg),
    ("lawclerk", collect_lawclerk),
    ("seoul_court", collect_seoul_court),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", default="output")
    parser.add_argument("--per-site", type=int, default=50)
    parser.add_argument("--delay", type=float, default=0.15)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    for name, collector in COLLECTORS:
        site_dir = output_root / name
        site_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n== {name} ==", flush=True)
        downloaded = collector(args.per_site, site_dir, args.delay)
        print(f"[{name}] downloaded={downloaded}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
