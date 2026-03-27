"""
services/ocr/page_ocr_policy.py

페이지 OCR 품질 정책.

흐름:
    1. raw PNG → 1차 OCR  (path_tag="raw")
       → OK: 반환
       → LOW: ↓
    2. gray_contrast → fallback OCR  (path_tag="pre_gray")
       → OK 또는 raw보다 score 높으면: 반환
       → still LOW: ↓
    3. binarized → fallback OCR  (path_tag="pre_bin")
       → OK 또는 pre_gray보다 score 높으면: 반환
       → still LOW: ↓
    4. split retry (분할 + binarized)  (path_tag="retry_split")

raw-first 이유:
    실검증에서 gray_contrast를 1차 경로로 쓸 때 소폭 품질 손실이 확인됨.
    grayscale/binarize는 fallback 전용으로 유지.
"""

from __future__ import annotations

import logging
import os
import unicodedata

logger = logging.getLogger(__name__)

_MIN_TEXT_LEN = 10
_MIN_KOREAN_RATIO = 0.20
_MAX_JUNK_RATIO = 0.40

_DET_LIMIT = 960
_PAGE_TIMEOUT = 120
_HALF_TIMEOUT = 90


def quality_meta(text: str) -> dict:
    """
    텍스트 품질 메타를 반환한다.

    Returns:
        {"low": bool, "reason": str, "chars": int, "korean": int, "junk": int, "score": float}
    """
    stripped = text.strip()
    total = len(stripped)

    if total == 0:
        return {
            "low": True,
            "reason": "empty",
            "chars": 0,
            "korean": 0,
            "junk": 0,
            "score": 0.0,
        }

    korean = sum(1 for c in stripped if "\uac00" <= c <= "\ud7a3")
    junk = sum(
        1
        for c in stripped
        if unicodedata.category(c) in ("Co", "Cs", "Cn")
        or (unicodedata.category(c) == "Cc" and c not in "\n\t\r")
    )
    kr_ratio = korean / total
    junk_ratio = junk / total
    score = kr_ratio * 1.0 + min(total / 1000, 1.0) * 0.3 - junk_ratio * 0.5

    if total < _MIN_TEXT_LEN:
        return {
            "low": True,
            "reason": "too_short",
            "chars": total,
            "korean": korean,
            "junk": junk,
            "score": score,
        }
    if kr_ratio < _MIN_KOREAN_RATIO:
        return {
            "low": True,
            "reason": "low_korean",
            "chars": total,
            "korean": korean,
            "junk": junk,
            "score": score,
        }
    if junk_ratio > _MAX_JUNK_RATIO:
        return {
            "low": True,
            "reason": "high_junk",
            "chars": total,
            "korean": korean,
            "junk": junk,
            "score": score,
        }

    return {
        "low": False,
        "reason": "ok",
        "chars": total,
        "korean": korean,
        "junk": junk,
        "score": score,
    }


def run_page(
    pdf_path: str,
    page_index: int,
    pnum: int,
    total_pages: int,
    tmpdir: str,
    worker_script: str,
) -> tuple[str, str]:
    """
    단일 페이지 OCR 흐름.

    Returns:
        (최종 텍스트, path_tag)
        path_tag: "raw" | "pre_gray" | "pre_bin" | "retry_split" | "fail"
    """
    from services.ocr import image_preprocessor, page_renderer, page_worker_runner

    img_raw = os.path.join(tmpdir, f"p{pnum}_raw.png")

    # ── 렌더링 ────────────────────────────────────────────────────────────────
    if not page_renderer.render_page_to_file(pdf_path, page_index, img_raw):
        return "", "fail"

    # ── 1차 OCR: raw PNG ──────────────────────────────────────────────────────
    meta_raw = page_worker_runner.run(
        img_raw,
        _DET_LIMIT,
        _PAGE_TIMEOUT,
        worker_script,
        tag=f"page={pnum}/{total_pages}[raw]",
    )
    qm_raw = quality_meta(meta_raw["text"])

    if not qm_raw["low"]:
        _safe_remove(img_raw)
        return meta_raw["text"], "raw"

    logger.info(
        "[policy] page=%d/%d raw LOW reason=%s chars=%d score=%.3f → pre_gray",
        pnum,
        total_pages,
        qm_raw["reason"],
        qm_raw["chars"],
        qm_raw["score"],
    )

    # ── fallback 1: gray_contrast ─────────────────────────────────────────────
    img_gray = os.path.join(tmpdir, f"p{pnum}_gray.png")
    gray_ok = image_preprocessor.preprocess_gray_contrast(img_raw, img_gray)

    best_text = meta_raw["text"]
    best_tag = "raw"
    best_score = qm_raw["score"]

    if gray_ok:
        meta_gray = page_worker_runner.run(
            img_gray,
            _DET_LIMIT,
            _PAGE_TIMEOUT,
            worker_script,
            tag=f"page={pnum}/{total_pages}[pre_gray]",
        )
        _safe_remove(img_gray)
        qm_gray = quality_meta(meta_gray["text"])

        logger.info(
            "[policy] page=%d/%d pre_gray chars=%d score=%.3f low=%s",
            pnum,
            total_pages,
            qm_gray["chars"],
            qm_gray["score"],
            qm_gray["low"],
        )

        if not qm_gray["low"] or qm_gray["score"] > best_score:
            best_text, best_tag, best_score = (
                meta_gray["text"],
                "pre_gray",
                qm_gray["score"],
            )
    else:
        _safe_remove(img_gray)

    if not quality_meta(best_text)["low"]:
        _safe_remove(img_raw)
        return best_text, best_tag

    # ── fallback 2: binarized ─────────────────────────────────────────────────
    img_bin = os.path.join(tmpdir, f"p{pnum}_bin.png")
    bin_ok = image_preprocessor.preprocess_binarized(img_raw, img_bin)
    _safe_remove(img_raw)

    if bin_ok:
        meta_bin = page_worker_runner.run(
            img_bin,
            _DET_LIMIT,
            _PAGE_TIMEOUT,
            worker_script,
            tag=f"page={pnum}/{total_pages}[pre_bin]",
        )
        _safe_remove(img_bin)
        qm_bin = quality_meta(meta_bin["text"])

        logger.info(
            "[policy] page=%d/%d pre_bin chars=%d score=%.3f low=%s",
            pnum,
            total_pages,
            qm_bin["chars"],
            qm_bin["score"],
            qm_bin["low"],
        )

        if not qm_bin["low"] or qm_bin["score"] > best_score:
            best_text, best_tag, best_score = (
                meta_bin["text"],
                "pre_bin",
                qm_bin["score"],
            )
    else:
        _safe_remove(img_bin)

    if not quality_meta(best_text)["low"]:
        return best_text, best_tag

    # ── split retry ───────────────────────────────────────────────────────────
    logger.info("[policy] page=%d/%d still LOW → split retry", pnum, total_pages)

    img_base2 = os.path.join(tmpdir, f"p{pnum}_base2.png")
    img_top = os.path.join(tmpdir, f"p{pnum}_top.png")
    img_bot = os.path.join(tmpdir, f"p{pnum}_bot.png")
    img_top_bin = os.path.join(tmpdir, f"p{pnum}_top_bin.png")
    img_bot_bin = os.path.join(tmpdir, f"p{pnum}_bot_bin.png")

    if not page_renderer.render_page_to_file(pdf_path, page_index, img_base2):
        return best_text, best_tag

    if not image_preprocessor.split_halves(img_base2, img_top, img_bot):
        _safe_remove(img_base2)
        return best_text, best_tag
    _safe_remove(img_base2)

    top_bin_ok = image_preprocessor.preprocess_binarized(img_top, img_top_bin)
    bot_bin_ok = image_preprocessor.preprocess_binarized(img_bot, img_bot_bin)
    _safe_remove(img_top)
    _safe_remove(img_bot)

    meta_top = page_worker_runner.run(
        img_top_bin if top_bin_ok else img_top,
        _DET_LIMIT,
        _HALF_TIMEOUT,
        worker_script,
        tag=f"page={pnum}/{total_pages}[split_top]",
    )
    _safe_remove(img_top_bin)
    meta_bot = page_worker_runner.run(
        img_bot_bin if bot_bin_ok else img_bot,
        _DET_LIMIT,
        _HALF_TIMEOUT,
        worker_script,
        tag=f"page={pnum}/{total_pages}[split_bot]",
    )
    _safe_remove(img_bot_bin)

    retry_text = "\n".join(t for t in [meta_top["text"], meta_bot["text"]] if t)
    qm_retry = quality_meta(retry_text)

    if not qm_retry["low"] or qm_retry["score"] > best_score:
        logger.info(
            "[policy] page=%d/%d retry_split adopted chars=%d",
            pnum,
            total_pages,
            qm_retry["chars"],
        )
        return retry_text, "retry_split"

    logger.warning(
        "[policy] page=%d/%d retry_split not better → keep %s",
        pnum,
        total_pages,
        best_tag,
    )
    return best_text, best_tag


def _safe_remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
