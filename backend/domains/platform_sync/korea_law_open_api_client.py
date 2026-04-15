"""
domains/platform_sync/korea_law_open_api_client.py

국가법령정보 공동활용 Open API 호출 클라이언트.

현재 범위:
    - 목록 검색 (lawSearch.do)
    - 상세 조회 (lawService.do, 목록 응답의 상세 링크 재사용)

정책:
    - OC 값은 환경변수에서만 읽는다.
    - source_type별 고유 external_id는 목록 응답 필드 기준으로 추출한다.
    - 목록은 page 순회로 전체 source를 스캔한다.
    - 상세 응답은 source_type별 wrapper를 벗겨 canonical payload로 반환한다.

unsupported detail 판별:
    is_unsupported_detail_response() 함수로 판별한다.
    판별 기준:
        - {"Law": "일치하는 판례가 없습니다..."} 형태
        - keys == ["Law"] 이고 값이 오류 메시지 문자열
    이 케이스는 list_only 기본 문서 유지 대상이다.
    진짜 fetch failure(timeout/5xx/non-json)와는 다르다.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

from errors import AppException, ErrorCode
from settings.platform import (
    KOREA_LAW_OPEN_API_BASE_URL,
    KOREA_LAW_OPEN_API_OC,
    KOREA_LAW_OPEN_API_SYNC_PAGE_SIZE,
    KOREA_LAW_OPEN_API_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)

_ERROR_SNIPPET_MAX = 300

_SEARCH_TARGET_MAP: dict[str, str] = {
    "law": "law",
    "precedent": "prec",
    "interpretation": "expc",
    "admin_rule": "admrul",
}

_SEARCH_ROOT_MAP: dict[str, tuple[str, str]] = {
    "law": ("LawSearch", "law"),
    "precedent": ("PrecSearch", "prec"),
    "interpretation": ("Expc", "expc"),
    "admin_rule": ("AdmRulSearch", "admrul"),
}

_EXTERNAL_ID_FIELD_MAP: dict[str, str] = {
    "law": "법령일련번호",
    "precedent": "판례일련번호",
    "interpretation": "법령해석례일련번호",
    "admin_rule": "행정규칙일련번호",
}

_DETAIL_LINK_FIELD_MAP: dict[str, str] = {
    "law": "법령상세링크",
    "precedent": "판례상세링크",
    "interpretation": "법령해석례상세링크",
    "admin_rule": "행정규칙상세링크",
}

_DISPLAY_TITLE_FIELD_MAP: dict[str, str] = {
    "law": "법령명한글",
    "precedent": "사건명",
    "interpretation": "안건명",
    "admin_rule": "행정규칙명",
}

_DETAIL_ROOT_MAP: dict[str, str] = {
    "precedent": "PrecService",
    "interpretation": "ExpcService",
    "admin_rule": "AdmRulService",
}

# precedent unsupported detail 판별 상수
_PREC_UNSUPPORTED_KEY = "Law"
_PREC_UNSUPPORTED_PHRASES = (
    "일치하는 판례가 없습니다",
    "판례명을 확인하여 주십시오",
)


def _law_extract_nested_value(node: Any, *keys: str) -> Any:
    if not isinstance(node, dict):
        return None
    for key in keys:
        value = node.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _canonicalize_law_detail_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """
    법령 상세 응답을 law_mapper가 읽는 flat payload로 변환한다.

    실제 law 상세는 {"법령": {"기본정보": ..., "조문": ..., "부칙": ..., "별표": ...}}
    구조로 내려오므로 제목/조문/부칙/별표/제개정이유를 flat key로 펼쳐준다.
    """
    law = payload.get("법령")
    if not isinstance(law, dict):
        return payload

    basic = law.get("기본정보") if isinstance(law.get("기본정보"), dict) else {}
    dept = basic.get("소관부처") if isinstance(basic, dict) else None
    agency = (
        basic.get("소관부처명")
        or _law_extract_nested_value(dept, "소관부처명", "부처명", "기관명")
        or None
    )

    articles = law.get("조문")
    if isinstance(articles, dict):
        articles = articles.get("조문단위") or articles.get("조문내용") or []

    addendum = law.get("부칙")
    if isinstance(addendum, dict):
        addendum = addendum.get("부칙단위") or addendum.get("부칙내용") or addendum

    annex = law.get("별표")
    if isinstance(annex, dict):
        annex = annex.get("별표단위") or annex.get("별표내용") or annex

    revision_reason = law.get("제개정이유")
    if isinstance(revision_reason, dict):
        revision_reason = revision_reason.get("제개정이유내용") or revision_reason

    amendment_text = law.get("개정문")
    if isinstance(amendment_text, dict):
        amendment_text = amendment_text.get("개정문내용") or amendment_text

    return {
        **basic,
        "소관부처명": agency,
        "조문": articles or [],
        "부칙내용": addendum,
        "별표내용": annex,
        "제개정이유내용": revision_reason or amendment_text,
    }


class UnsupportedDetailError(Exception):
    """
    상세 API가 unsupported detail 응답을 반환한 경우.

    진짜 fetch failure(timeout/5xx/non-json)와 구분된다.
    precedent source에서 list_only 기본 문서 유지의 트리거.

    Attributes:
        message:   API 응답의 오류 메시지 문자열
        raw_payload: 원본 응답 dict
    """

    def __init__(self, message: str, raw_payload: dict) -> None:
        super().__init__(message)
        self.message = message
        self.raw_payload = raw_payload


class KoreaLawOpenApiClient:
    """국가법령정보 Open API 검색/상세 호출 클라이언트."""

    def __init__(self) -> None:
        self._base_url = KOREA_LAW_OPEN_API_BASE_URL
        self._oc = KOREA_LAW_OPEN_API_OC
        self._timeout = KOREA_LAW_OPEN_API_TIMEOUT_SECONDS

    def search_page(
        self,
        *,
        source_type: str,
        page: int,
        display: int | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        self._ensure_configured()

        target = _SEARCH_TARGET_MAP[source_type]
        url = f"{self._base_url}/lawSearch.do"
        params = {
            "OC": self._oc,
            "target": target,
            "type": "JSON",
            "display": display or KOREA_LAW_OPEN_API_SYNC_PAGE_SIZE,
            "page": page,
        }

        try:
            response = requests.get(url, params=params, timeout=self._timeout)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.exception(
                "[KoreaLawOpenApiClient] search 실패 source_type=%s page=%s",
                source_type,
                page,
            )
            raise AppException(ErrorCode.PLATFORM_SYNC_REQUEST_FAILED) from exc

        root_key, items_key = _SEARCH_ROOT_MAP[source_type]
        root = payload.get(root_key) or {}
        items = root.get(items_key) or []
        total_count = int(root.get("totalCnt") or 0)

        if isinstance(items, dict):
            items = [items]
        if not isinstance(items, list):
            return [], total_count
        return items, total_count

    def fetch_detail_from_link(
        self, source_type: str, detail_link: str
    ) -> dict[str, Any]:
        """
        상세 링크로부터 canonical payload를 반환한다.

        Raises:
            UnsupportedDetailError: unsupported detail 응답 (예: {"Law": "..."})
            RuntimeError:           진짜 fetch 실패 (timeout/5xx/non-json)
        """
        self._ensure_configured()

        url = self._to_json_detail_url(detail_link)
        try:
            response = requests.get(url, timeout=self._timeout)
            if not response.ok:
                raise RuntimeError(
                    f"detail fetch failed: status={response.status_code} url={url} "
                    f"body={_snippet_text(response.text)}"
                )

            try:
                payload = response.json()
            except ValueError as exc:
                raise RuntimeError(
                    f"detail fetch returned non-json: status={response.status_code} url={url} "
                    f"body={_snippet_text(response.text)}"
                ) from exc

            return canonicalize_detail_payload(source_type, payload, url=url)
        except UnsupportedDetailError:
            raise
        except (requests.RequestException, RuntimeError) as exc:
            logger.exception(
                "[KoreaLawOpenApiClient] detail 조회 실패 url=%s",
                url,
            )
            raise RuntimeError(str(exc)) from exc

    def extract_external_id(self, source_type: str, item: dict[str, Any]) -> str:
        field = _EXTERNAL_ID_FIELD_MAP[source_type]
        value = item.get(field)
        return str(value or "").strip()

    def extract_display_title(
        self, source_type: str, item: dict[str, Any]
    ) -> str | None:
        field = _DISPLAY_TITLE_FIELD_MAP[source_type]
        value = str(item.get(field) or "").strip()
        return value or None

    def extract_detail_link(self, source_type: str, item: dict[str, Any]) -> str:
        field = _DETAIL_LINK_FIELD_MAP[source_type]
        value = str(item.get(field) or "").strip()
        if not value:
            raise AppException(ErrorCode.PLATFORM_SYNC_REQUEST_FAILED)
        return value

    def _ensure_configured(self) -> None:
        if not self._oc:
            raise AppException(ErrorCode.PLATFORM_SYNC_CONFIG_MISSING)

    def _to_json_detail_url(self, detail_link: str) -> str:
        parsed = urlparse(detail_link)
        if not parsed.scheme:
            parsed = urlparse(f"http://www.law.go.kr{detail_link}")

        params = dict(parse_qsl(parsed.query, keep_blank_values=True))
        params["OC"] = self._oc
        params["type"] = "JSON"
        query = urlencode(params, doseq=True)
        return urlunparse(parsed._replace(query=query))


def _snippet_text(value: Any) -> str:
    text = str(value or "").strip().replace("\n", " ").replace("\r", " ")
    return text[:_ERROR_SNIPPET_MAX]


def is_unsupported_detail_response(payload: dict[str, Any]) -> bool:
    """
    상세 API 응답이 unsupported detail 형태인지 판별한다.

    판별 기준:
        1. keys == ["Law"] 형태
        2. "Law" 값이 오류 메시지 문자열

    예:
        {"Law": "일치하는 판례가 없습니다. 판례명을 확인하여 주십시오."}

    Returns:
        True이면 list_only 기본 문서 유지 대상
        False이면 일반 응답 또는 진짜 실패
    """
    if not isinstance(payload, dict):
        return False
    keys = list(payload.keys())
    if keys != [_PREC_UNSUPPORTED_KEY]:
        return False
    message = str(payload.get(_PREC_UNSUPPORTED_KEY) or "")
    return any(phrase in message for phrase in _PREC_UNSUPPORTED_PHRASES)


def canonicalize_detail_payload(
    source_type: str,
    payload: dict[str, Any],
    *,
    url: str | None = None,
) -> dict[str, Any]:
    """
    source_type별 상세 응답 wrapper를 벗겨 mapper가 기대하는 canonical payload로 정리한다.

    - precedent      : {"PrecService": {...}}      -> {...}
    - interpretation : {"ExpcService": {...}}      -> {...}
    - admin_rule     : {"AdmRulService": {...}}    -> {...}
    - law            : {"법령": {...}} 응답을 mapper-friendly flat payload로 반환

    precedent unsupported detail 응답:
        {"Law": "일치하는 판례가 없습니다..."} 형태는
        UnsupportedDetailError를 발생시켜 list_only 유지 경로로 분기한다.

    그 외 상세 조회 실패/오류성 응답은 RuntimeError로 처리한다.
    """
    if not isinstance(payload, dict):
        raise RuntimeError(
            f"unexpected detail payload type: source_type={source_type} "
            f"url={url or '-'} type={type(payload).__name__}"
        )

    # precedent unsupported detail 조기 분기
    if source_type == "precedent" and is_unsupported_detail_response(payload):
        message = str(payload.get(_PREC_UNSUPPORTED_KEY) or "")
        logger.info(
            "[KoreaLawOpenApiClient] unsupported detail detected: source_type=%s url=%s message=%s",
            source_type,
            url or "-",
            _snippet_text(message),
        )
        raise UnsupportedDetailError(message, payload)

    root_key = _DETAIL_ROOT_MAP.get(source_type)
    if root_key:
        wrapped = payload.get(root_key)
        if isinstance(wrapped, dict):
            return wrapped

        # 기대한 wrapper가 없고 문자열 오류 메시지 형태면 조기 실패
        if any(isinstance(v, str) and v.strip() for v in payload.values()):
            message = next(
                (
                    v.strip()
                    for v in payload.values()
                    if isinstance(v, str) and v.strip()
                ),
                "",
            )
            logger.error(
                "[KoreaLawOpenApiClient] 예상한 상세 wrapper 없음: source_type=%s keys=%s url=%s message=%s",
                source_type,
                list(payload.keys()),
                url,
                message,
            )
            raise RuntimeError(
                f"unexpected detail payload: source_type={source_type} url={url or '-'} "
                f"keys={list(payload.keys())} message={_snippet_text(message)}"
            )

    if source_type == "law":
        return _canonicalize_law_detail_payload(payload)

    return payload
