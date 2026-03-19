"""
현재 활성 precedent seed 배치를 export한다.

precedent_batch_config.ACTIVE_PRECEDENT_BATCH 값만 바꾸면
seed_admin.py 는 자동으로 해당 1000건 배치를 사용한다.
"""

from __future__ import annotations

from importlib import import_module

from seed_data.precedent_batch_config import ACTIVE_PRECEDENT_BATCH

_module = import_module(
    f"seed_data.batches.precedent_sources_batch_{ACTIVE_PRECEDENT_BATCH}"
)

SEED_PRECEDENT_SOURCES = _module.SEED_PRECEDENT_SOURCES
