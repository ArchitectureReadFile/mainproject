"""
settings/platform.py

Platform Knowledge 운영 파라미터.

━━━ Corpus 정책 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
platform corpus가 유일한 platform knowledge source of truth다.

    - law / precedent / interpretation / admin_rule 모두
      platform corpus(source_type 기반)에서 검색한다.
    - legacy precedent corpus는 더 이상 platform read path에서 사용하지 않는다.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━━ Source 지원 범위 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4개 source 모두 공식 API 필드 확인 완료, platform public corpus 대상으로 확정.

    law:            지원 (현행법령 — 조문 단위 article chunk)
    precedent:      지원 (판례 — 목록 기준 기본 문서 + 상세 enrich, holding/summary/body/meta chunk)
    interpretation: 지원 (법령해석례 — question/answer/reason chunk)
    admin_rule:     지원 (행정규칙 — rule/addendum/annex chunk, 중첩 응답 자동 flatten)
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


# ── Source별 ingestion 활성화 플래그 ─────────────────────────────────────────
# 4개 source 모두 API 필드 구조 확인 완료 — 기본 활성
ENABLE_INGESTION_LAW: bool = _bool_env("ENABLE_INGESTION_LAW", True)
ENABLE_INGESTION_PRECEDENT: bool = _bool_env("ENABLE_INGESTION_PRECEDENT", True)
ENABLE_INGESTION_INTERPRETATION: bool = _bool_env(
    "ENABLE_INGESTION_INTERPRETATION", True
)
ENABLE_INGESTION_ADMIN_RULE: bool = _bool_env("ENABLE_INGESTION_ADMIN_RULE", True)

# ── Korea Law Open API client 설정 ───────────────────────────────────────────
KOREA_LAW_OPEN_API_OC: str = os.getenv("KOREA_LAW_OPEN_API_OC", "").strip()
KOREA_LAW_OPEN_API_BASE_URL: str = os.getenv(
    "KOREA_LAW_OPEN_API_BASE_URL", "http://www.law.go.kr/DRF"
).rstrip("/")
KOREA_LAW_OPEN_API_TIMEOUT_SECONDS: int = int(
    os.getenv("KOREA_LAW_OPEN_API_TIMEOUT_SECONDS", "20")
)
KOREA_LAW_OPEN_API_SYNC_PAGE_SIZE: int = int(
    os.getenv("KOREA_LAW_OPEN_API_SYNC_PAGE_SIZE", "100")
)

_INGESTION_FLAG_MAP: dict[str, bool] = {
    "law": ENABLE_INGESTION_LAW,
    "precedent": ENABLE_INGESTION_PRECEDENT,
    "interpretation": ENABLE_INGESTION_INTERPRETATION,
    "admin_rule": ENABLE_INGESTION_ADMIN_RULE,
}


def is_ingestion_enabled(source_type: str) -> bool:
    """source_type ingestion 활성화 여부를 반환한다."""
    return _INGESTION_FLAG_MAP.get(source_type, False)


def get_platform_corpus_source_types() -> list[str]:
    """
    platform corpus 검색 대상 source_type 목록을 반환한다.

    platform corpus가 유일 read path이므로 4개 source 모두 포함한다.
    """
    return ["precedent", "law", "interpretation", "admin_rule"]
