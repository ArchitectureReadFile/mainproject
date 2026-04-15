"""
infra/ocr/run_ocr_document.py

문서 단위 OCR subprocess 진입점.

호출 규약: python run_ocr_document.py <pdf_path>
출력 규약: {"text": "...", "chars": N}  (한 줄 JSON, stdout)

PYTHONPATH=/app 로 실행되므로 sys.path 조작 불필요.
"""

from __future__ import annotations

import json
import os
import sys
import traceback

_WORKER_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "ocr_worker.py"
)


def main() -> None:
    try:
        if len(sys.argv) < 2:
            print(json.dumps({"error": "pdf_path 인자 필요"}), flush=True)
            sys.exit(1)

        pdf_path = sys.argv[1]

        from infra.ocr.ocr_orchestrator import extract_text

        text = extract_text(pdf_path, worker_script=_WORKER_SCRIPT)
        chars = len(text)

        print(
            json.dumps({"text": text, "chars": chars}, ensure_ascii=False), flush=True
        )

    except Exception as exc:
        tb = traceback.format_exc()
        print("=== DOCUMENT WORKER EXCEPTION ===", file=sys.stderr)
        print(tb, file=sys.stderr)
        print("=== END ===", file=sys.stderr)
        print(
            json.dumps({"error": str(exc), "traceback": tb}, ensure_ascii=False),
            flush=True,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
