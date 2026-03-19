"""
1만건 raw precedent URL을 1000건 단위 seed 배치 파일로 분할 생성한다.

실행 예시:
    python scripts/generate_precedent_source_batches.py
    python scripts/generate_precedent_source_batches.py \
        --input seed_data/taxlaw_precedent_urls_10000.json \
        --output-dir seed_data/batches \
        --batch-size 1000
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from generate_precedent_sources import load_items, render_python, transform_items

DEFAULT_INPUT = "seed_data/taxlaw_precedent_urls_10000.json"
DEFAULT_OUTPUT_DIR = "seed_data/batches"
DEFAULT_BATCH_SIZE = 1000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="precedent seed 배치 생성기")
    parser.add_argument("--input", default=DEFAULT_INPUT, help="raw JSON 경로")
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="배치 Python 파일 저장 디렉토리",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="배치당 건수",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.batch_size <= 0:
        raise SystemExit("--batch-size 는 1 이상의 정수여야 합니다.")

    input_path = Path(args.input).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_items = load_items(input_path)
    transformed = transform_items(raw_items)

    total_batches = math.ceil(len(transformed) / args.batch_size)
    for batch_index in range(total_batches):
        start = batch_index * args.batch_size
        end = min(start + args.batch_size, len(transformed))
        batch_items = transformed[start:end]
        output_path = output_dir / f"precedent_sources_batch_{batch_index}.py"
        output_path.write_text(
            render_python(
                batch_items,
                f"{input_path.name} [{start + 1}..{end}]",
            ),
            encoding="utf-8",
        )

    init_path = output_dir / "__init__.py"
    if not init_path.exists():
        init_path.write_text(
            '"""Generated precedent source batches."""\n', encoding="utf-8"
        )

    print(f"입력 건수: {len(raw_items)}")
    print(f"변환 건수: {len(transformed)}")
    print(f"배치 크기: {args.batch_size}")
    print(f"생성 배치 수: {total_batches}")
    print(f"저장 디렉토리: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
