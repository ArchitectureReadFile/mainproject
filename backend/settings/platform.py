"""
settings/platform.py

Platform Knowledge 운영 파라미터 및 migration flag.

━━━ Migration 단계 정책 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
현재 단계 (ENABLE_PLATFORM_PRECEDENT_CORPUS=false):
    - 판례는 기존 precedent corpus(bm25:p:* / Qdrant precedent_id 기반)만 사용
    - platform corpus(bm25:pl:*) 검색 대상에서 source_type="precedent" 제외
    - precedent_mapper를 통한 PlatformDocument 적재는 가능하나 검색에는 미반영

migration 완료 단계 (ENABLE_PLATFORM_PRECEDENT_CORPUS=true):
    - 기존 precedent corpus 검색 OFF
    - platform corpus에서 source_type="precedent" 포함
    - 기존 Precedent 모델 / precedent corpus는 read-only deprecated 상태

"둘 다 검색 후 dedupe" 방식은 사용하지 않는다.
    - source_id 체계가 달라 dedupe 키가 충돌 없이 통과해 중복 반환 위험이 있다.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━━ Source 지원 범위 (현재) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    law:            지원 (공식 API 필드 확인 완료)
    precedent:      지원 (공식 API 필드 확인 완료, migration flag로 corpus 전환 관리)
    interpretation: 구조 검증 전 fail-closed (상세 필드명 미확정 placeholder 상태)
    admin_rule:     구조 검증 전 fail-closed (실제 응답 수신 전 placeholder 상태)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import os


def _bool_env(name: str, default: bool) -> bool:
    val = os.getenv(name, "").lower()
    if val in ("1", "true", "yes"):
        return True
    if val in ("0", "false", "no"):
        return False
    return default


# ── Precedent migration flag ───────────────────────────────────────────────────
# false(기본): 기존 precedent corpus 유지, platform corpus에서 precedent 제외
# true:        기존 precedent corpus OFF, platform corpus에서 precedent 포함
ENABLE_PLATFORM_PRECEDENT_CORPUS: bool = _bool_env(
    "ENABLE_PLATFORM_PRECEDENT_CORPUS", False
)

# ── Source별 ingestion 활성화 플래그 ─────────────────────────────────────────
# interpretation / admin_rule은 실제 API 필드 구조 확인 전까지 기본 비활성
ENABLE_INGESTION_LAW: bool = _bool_env("ENABLE_INGESTION_LAW", True)
ENABLE_INGESTION_PRECEDENT: bool = _bool_env("ENABLE_INGESTION_PRECEDENT", True)
ENABLE_INGESTION_INTERPRETATION: bool = _bool_env(
    "ENABLE_INGESTION_INTERPRETATION", False
)
ENABLE_INGESTION_ADMIN_RULE: bool = _bool_env("ENABLE_INGESTION_ADMIN_RULE", False)

_INGESTION_FLAG_MAP: dict[str, bool] = {
    "law": ENABLE_INGESTION_LAW,
    "precedent": ENABLE_INGESTION_PRECEDENT,
    "interpretation": ENABLE_INGESTION_INTERPRETATION,
    "admin_rule": ENABLE_INGESTION_ADMIN_RULE,
}


def is_ingestion_enabled(source_type: str) -> bool:
    """source_type ingestion 활성화 여부를 반환한다."""
    return _INGESTION_FLAG_MAP.get(source_type, False)


# platform corpus 검색 대상 source_type 목록 (migration flag 기반)
def get_platform_corpus_source_types() -> list[str]:
    """
    현재 migration 단계에서 platform corpus 검색 대상 source_type 목록을 반환한다.

    ENABLE_PLATFORM_PRECEDENT_CORPUS=false:
        ["law", "interpretation", "admin_rule"]
        precedent는 기존 corpus에서 처리하므로 제외

    ENABLE_PLATFORM_PRECEDENT_CORPUS=true:
        ["law", "precedent", "interpretation", "admin_rule"]
        기존 corpus 비활성화, platform corpus에서 모두 처리
    """
    types = ["law", "interpretation", "admin_rule"]
    if ENABLE_PLATFORM_PRECEDENT_CORPUS:
        types.insert(0, "precedent")
    return types
