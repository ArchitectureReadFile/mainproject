"""
services/ocr/image_preprocessor.py

이미지 전처리 연산 모음.
원본 이미지는 변경하지 않고 항상 새 경로(dst_path)에 저장한다.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_CONTRAST_FACTOR = 1.8
_BINARIZE_OFFSET = 0


def preprocess_gray_contrast(src_path: str, dst_path: str) -> bool:
    """grayscale + contrast 강화. 기본 OCR 입력 경로."""
    try:
        from PIL import Image, ImageEnhance

        img = Image.open(src_path).convert("L")
        img = ImageEnhance.Contrast(img).enhance(_CONTRAST_FACTOR)
        img.save(dst_path)
        return True
    except Exception as exc:
        logger.warning(
            "[preprocessor] gray_contrast 실패: src=%s error=%r", src_path, exc
        )
        return False


def preprocess_binarized(src_path: str, dst_path: str) -> bool:
    """grayscale + contrast + sharpen + binarize. 저품질 fallback 경로."""
    try:
        from PIL import Image, ImageEnhance, ImageFilter

        img = Image.open(src_path).convert("L")
        img = ImageEnhance.Contrast(img).enhance(_CONTRAST_FACTOR)
        img = img.filter(ImageFilter.SHARPEN)
        threshold = int(sum(img.getdata()) / len(img.getdata())) + _BINARIZE_OFFSET
        img = img.point(lambda p: 255 if p > threshold else 0, "L")
        img.save(dst_path)
        return True
    except Exception as exc:
        logger.warning("[preprocessor] binarized 실패: src=%s error=%r", src_path, exc)
        return False


def split_halves(src_path: str, top_path: str, bot_path: str) -> bool:
    """상/하 2분할. split retry용."""
    try:
        from PIL import Image

        img = Image.open(src_path)
        w, h = img.size
        mid = h // 2
        img.crop((0, 0, w, mid)).save(top_path)
        img.crop((0, mid, w, h)).save(bot_path)
        return True
    except Exception as exc:
        logger.warning("[preprocessor] 분할 실패: src=%s error=%r", src_path, exc)
        return False
