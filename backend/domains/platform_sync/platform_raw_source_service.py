"""
services/platform/platform_raw_source_service.py

공공 API 원본 응답 보관 서비스.

책임:
    - raw source upsert (checksum 기반 변경 감지)
    - 동일 external_id 재수집 시 payload 갱신 여부 결정
    - PlatformRawSource row 반환

비책임:
    - normalize / chunk / index (→ 각 전담 서비스)
    - API 호출 (→ PlatformKnowledgeIngestionService)
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models.platform_knowledge import PlatformRawSource

logger = logging.getLogger(__name__)


def _checksum(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PlatformRawSourceService:
    """
    raw source upsert.

    upsert 정책:
        1. (provider, api_target, external_id) unique key로 조회
        2. 없으면 INSERT
        3. 있으면 checksum 비교 → 변경된 경우만 UPDATE
        4. 변경 없으면 기존 row 그대로 반환 (no-op)

    반환값:
        (PlatformRawSource, changed: bool)
        changed=True  → 새로 INSERT 또는 payload 갱신된 UPDATE
        changed=False → checksum 동일, no-op
    """

    def upsert(
        self,
        db: Session,
        *,
        source_type: str,
        provider: str,
        api_target: str,
        external_id: str,
        raw_format: str,
        raw_payload: str | dict | list,
        extra_meta: dict | None = None,
    ) -> tuple[PlatformRawSource, bool]:
        """
        raw source를 upsert한다.

        raw_payload:
            str 또는 dict/list (자동으로 JSON 직렬화).
        """
        if not isinstance(raw_payload, str):
            raw_payload = json.dumps(raw_payload, ensure_ascii=False)

        new_checksum = _checksum(raw_payload)

        existing: PlatformRawSource | None = (
            db.query(PlatformRawSource)
            .filter_by(
                provider=provider,
                api_target=api_target,
                external_id=external_id,
            )
            .first()
        )

        if existing is None:
            row = PlatformRawSource(
                source_type=source_type,
                provider=provider,
                api_target=api_target,
                external_id=external_id,
                raw_format=raw_format,
                raw_payload=raw_payload,
                fetched_at=_utc_now(),
                checksum=new_checksum,
                status="active",
                extra_meta=json.dumps(extra_meta, ensure_ascii=False)
                if extra_meta
                else None,
            )
            db.add(row)
            db.flush()
            logger.info(
                "[PlatformRawSourceService] INSERT source_type=%s external_id=%s",
                source_type,
                external_id,
            )
            return row, True

        if existing.checksum == new_checksum:
            logger.debug(
                "[PlatformRawSourceService] no-op (checksum 동일) external_id=%s",
                external_id,
            )
            return existing, False

        # payload 변경 — 갱신
        existing.raw_payload = raw_payload
        existing.checksum = new_checksum
        existing.fetched_at = _utc_now()
        if extra_meta is not None:
            existing.extra_meta = json.dumps(extra_meta, ensure_ascii=False)
        db.flush()
        logger.info(
            "[PlatformRawSourceService] UPDATE source_type=%s external_id=%s",
            source_type,
            external_id,
        )
        return existing, True

    def archive(
        self, db: Session, *, provider: str, api_target: str, external_id: str
    ) -> bool:
        """external_id row를 archived 상태로 전환. 없으면 False 반환."""
        row = (
            db.query(PlatformRawSource)
            .filter_by(
                provider=provider, api_target=api_target, external_id=external_id
            )
            .first()
        )
        if row is None:
            return False
        row.status = "archived"
        db.flush()
        return True
