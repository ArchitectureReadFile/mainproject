"""
services/ocr/ocr_worker.py

단일 페이지 이미지 OCR worker.

호출 규약: python ocr_worker.py <image_path> [det_limit]
출력 규약: {"text": "...", "chars": N, "korean": N}

모델 조합:
    det: PP-OCRv5_mobile_det   (server_det 대비 메모리 절감, 반복 안정성 향상)
    rec: korean_PP-OCRv5_mobile_rec

버전: paddleocr==3.3.2 / paddlepaddle==3.2.0
"""

from __future__ import annotations

import json
import sys
import traceback

_DET_LIMIT = 960
_DET_MODEL = "PP-OCRv5_mobile_det"
_REC_MODEL = "korean_PP-OCRv5_mobile_rec"


def main() -> None:
    try:
        image_path = sys.argv[1]
        det_limit = int(sys.argv[2]) if len(sys.argv) > 2 else _DET_LIMIT

        # ── STEP 1: 진입 ───────────────────────────────────────────────────
        import paddleocr as _poc

        poc_version = getattr(_poc, "__version__", "unknown")
        try:
            import paddle as _paddle

            paddle_version = getattr(_paddle, "__version__", "unknown")
        except Exception:
            paddle_version = "unknown"

        print(
            json.dumps(
                {
                    "step": 1,
                    "msg": "worker entered",
                    "paddleocr_version": poc_version,
                    "paddlepaddle_version": paddle_version,
                    "det_model": _DET_MODEL,
                    "rec_model": _REC_MODEL,
                }
            ),
            file=sys.stderr,
        )

        # ── STEP 2: import ─────────────────────────────────────────────────
        from paddleocr import PaddleOCR

        print(json.dumps({"step": 2, "msg": "PaddleOCR imported"}), file=sys.stderr)

        # ── STEP 3: 인스턴스 생성 ──────────────────────────────────────────
        ocr = PaddleOCR(
            text_detection_model_name=_DET_MODEL,
            text_recognition_model_name=_REC_MODEL,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            text_det_limit_side_len=det_limit,
            device="cpu",
        )
        print(
            json.dumps(
                {
                    "step": 3,
                    "msg": "PaddleOCR instance created",
                    "det_model": _DET_MODEL,
                    "rec_model": _REC_MODEL,
                }
            ),
            file=sys.stderr,
        )

        # ── STEP 4: OCR 실행 ───────────────────────────────────────────────
        result = ocr.predict(image_path)
        print(
            json.dumps(
                {
                    "step": 4,
                    "msg": "predict() done",
                    "result_len": len(result) if result else 0,
                }
            ),
            file=sys.stderr,
        )

        # ── 결과 파싱 ──────────────────────────────────────────────────────
        lines: list[str] = []
        if result:
            for res in result:
                rec_texts = None
                try:
                    rec_texts = res["rec_texts"]
                except (KeyError, TypeError):
                    pass
                if rec_texts is None and hasattr(res, "get"):
                    rec_texts = res.get("rec_texts")
                if rec_texts:
                    for t in rec_texts:
                        if t and str(t).strip():
                            lines.append(str(t).strip())

        text = "\n".join(lines)
        chars = len(text)
        korean = sum(1 for c in text if "\uac00" <= c <= "\ud7a3")

        print(
            json.dumps(
                {"text": text, "chars": chars, "korean": korean}, ensure_ascii=False
            )
        )

    except Exception as exc:
        tb = traceback.format_exc()
        print("=== WORKER EXCEPTION ===", file=sys.stderr)
        print(tb, file=sys.stderr)
        print("=== END ===", file=sys.stderr)
        print(json.dumps({"error": str(exc), "traceback": tb}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
