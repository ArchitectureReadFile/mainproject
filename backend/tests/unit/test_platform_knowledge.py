"""
tests/unit/test_platform_knowledge.py

Platform Knowledge 보정 단계 테스트.

커버 범위:
    1. PlatformKnowledgeRetriever — migration flag 기반 중복 방지
    2. interpretation mapper — placeholder fail-closed validation
    3. admin_rule mapper — placeholder fail-closed validation
    4. PlatformKnowledgeIngestionService — 실패 정책
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ══════════════════════════════════════════════════════════════════════════════
# 1. PlatformKnowledgeRetriever — migration flag 중복 방지
# ══════════════════════════════════════════════════════════════════════════════


class TestPlatformKnowledgeRetrieverMigrationFlag:
    """
    ENABLE_PLATFORM_PRECEDENT_CORPUS flag 기반 corpus 라우팅 테스트.

    flag=false: 기존 precedent corpus ON, platform corpus에서 precedent 제외
    flag=true:  기존 precedent corpus OFF, platform corpus에서 precedent 포함
    """

    def _make_retriever(self):
        from services.knowledge.platform_knowledge_retriever import (
            PlatformKnowledgeRetriever,
        )

        return PlatformKnowledgeRetriever()

    def _make_request(self):
        from schemas.knowledge import KnowledgeRetrievalRequest

        return KnowledgeRetrievalRequest(
            query="판례 검색", include_platform=True, top_k=3
        )

    def test_flag_false_legacy_precedent_called(self):
        """flag=false이면 기존 precedent corpus(_retrieve_precedents)가 호출된다."""
        retriever = self._make_retriever()
        req = self._make_request()

        with (
            patch("settings.platform.ENABLE_PLATFORM_PRECEDENT_CORPUS", False),
            patch.object(
                retriever, "_retrieve_precedents", return_value=[]
            ) as mock_legacy,
            patch.object(retriever, "_retrieve_platform_chunks", return_value=[]),
        ):
            retriever.retrieve(req)

        mock_legacy.assert_called_once()

    def test_flag_true_legacy_precedent_not_called(self):
        """flag=true이면 기존 precedent corpus(_retrieve_precedents)가 호출되지 않는다."""
        retriever = self._make_retriever()
        req = self._make_request()

        with (
            patch(
                "services.knowledge.platform_knowledge_retriever.ENABLE_PLATFORM_PRECEDENT_CORPUS",
                True,
            ),
            patch.object(
                retriever, "_retrieve_precedents", return_value=[]
            ) as mock_legacy,
            patch.object(retriever, "_retrieve_platform_chunks", return_value=[]),
        ):
            retriever.retrieve(req)

        mock_legacy.assert_not_called()

    def test_flag_false_platform_corpus_excludes_precedent(self):
        """
        flag=false이면 platform corpus 검색 시 source_type 목록에 "precedent"가 없다.
        get_platform_corpus_source_types()가 ["law", "interpretation", "admin_rule"]를 반환해야 한다.
        """
        with patch("settings.platform.ENABLE_PLATFORM_PRECEDENT_CORPUS", False):
            from settings.platform import get_platform_corpus_source_types

            types = get_platform_corpus_source_types()

        assert "precedent" not in types
        assert "law" in types

    def test_flag_true_platform_corpus_includes_precedent(self):
        """flag=true이면 platform corpus 검색 source_type 목록에 "precedent"가 포함된다."""
        with patch("settings.platform.ENABLE_PLATFORM_PRECEDENT_CORPUS", True):
            # 모듈 재로드 없이 함수를 직접 호출해 확인
            import settings.platform as sp

            original = sp.ENABLE_PLATFORM_PRECEDENT_CORPUS
            sp.ENABLE_PLATFORM_PRECEDENT_CORPUS = True
            types = sp.get_platform_corpus_source_types()
            sp.ENABLE_PLATFORM_PRECEDENT_CORPUS = original

        assert "precedent" in types

    def test_include_platform_false_returns_empty(self):
        """include_platform=False이면 두 corpus 모두 검색하지 않는다."""
        from schemas.knowledge import KnowledgeRetrievalRequest

        retriever = self._make_retriever()
        req = KnowledgeRetrievalRequest(query="질문", include_platform=False)

        with (
            patch.object(
                retriever, "_retrieve_precedents", return_value=[]
            ) as mock_legacy,
            patch.object(
                retriever, "_retrieve_platform_chunks", return_value=[]
            ) as mock_platform,
        ):
            result = retriever.retrieve(req)

        assert result == []
        mock_legacy.assert_not_called()
        mock_platform.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# 2. interpretation mapper — fail-closed validation
# ══════════════════════════════════════════════════════════════════════════════


class TestInterpretationMapperValidation:
    """
    interpretation mapper는 placeholder 상태이므로
    required field 누락 시 ValueError가 발생해야 한다.
    """

    def _normalize(self, payload: dict):
        from services.platform.mappers.interpretation_mapper import normalize

        return normalize(payload)

    def _valid_payload(self) -> dict:
        return {
            "법령해석례일련번호": "12345",
            "안건명": "국세기본법 제XX조 해석",
            "안건번호": "법제처 2024-0001",
            "질의기관명": "기획재정부",
            "회신기관명": "법제처",
            "회신일자": "20240101",
            "법령해석례상세링크": "https://example.com",
            "질의내용": "이 조항의 해석은 무엇인가?",
            "회신내용": "해당 조항은 다음과 같이 해석됩니다.",
            "이유내용": "관련 법령에 따르면 ...",
        }

    def test_valid_payload_succeeds(self):
        result = self._normalize(self._valid_payload())
        assert result.external_id == "12345"
        assert result.body_text != ""

    def test_missing_external_id_raises(self):
        payload = self._valid_payload()
        payload["법령해석례일련번호"] = ""
        with pytest.raises(ValueError, match="external_id"):
            self._normalize(payload)

    def test_missing_title_raises(self):
        payload = self._valid_payload()
        payload["안건명"] = ""
        with pytest.raises(ValueError, match="title"):
            self._normalize(payload)

    def test_all_body_fields_empty_raises(self):
        """질의내용/회신내용/이유내용 모두 없으면 placeholder mapper 컨텍스트와 함께 실패."""
        payload = self._valid_payload()
        payload["질의내용"] = ""
        payload["회신내용"] = ""
        payload["이유내용"] = ""
        with pytest.raises(ValueError, match="placeholder mapper"):
            self._normalize(payload)

    def test_partial_body_field_succeeds(self):
        """body 필드 중 하나라도 있으면 성공."""
        payload = self._valid_payload()
        payload["회신내용"] = ""
        payload["이유내용"] = ""
        # 질의내용만 있음
        result = self._normalize(payload)
        assert "이 조항의 해석은" in result.body_text

    def test_error_message_contains_placeholder_context(self):
        """오류 메시지에 'placeholder mapper' 컨텍스트가 있어야 한다."""
        payload = self._valid_payload()
        payload["질의내용"] = ""
        payload["회신내용"] = ""
        payload["이유내용"] = ""
        with pytest.raises(ValueError) as exc_info:
            self._normalize(payload)
        assert "placeholder mapper" in str(exc_info.value)

    def test_wrong_field_names_raises(self):
        """실제 응답 구조가 달라 placeholder 필드명이 안 맞으면 실패."""
        payload = {
            "법령해석례일련번호": "12345",
            "안건명": "해석례 제목",
            # 실제 필드명이 다른 경우 시뮬레이션
            "question_text": "질의 내용",
            "answer_text": "회신 내용",
        }
        with pytest.raises(ValueError):
            self._normalize(payload)


# ══════════════════════════════════════════════════════════════════════════════
# 3. admin_rule mapper — fail-closed validation
# ══════════════════════════════════════════════════════════════════════════════


class TestAdminRuleMapperValidation:
    def _normalize(self, payload: dict):
        from services.platform.mappers.admin_rule_mapper import normalize

        return normalize(payload)

    def _valid_payload(self) -> dict:
        return {
            "행정규칙ID": "AR-001",
            "행정규칙명": "국세청 훈령 제1호",
            "소관기관명": "국세청",
            "발령일자": "20240101",
            "시행일자": "20240101",
            "행정규칙번호": "훈령 제1호",
            "조문": [
                {
                    "조문번호": "1",
                    "조문내용": "이 훈령은 국세청 업무에 관한 기준을 정한다.",
                },
            ],
        }

    def test_valid_payload_succeeds(self):
        result = self._normalize(self._valid_payload())
        assert result.external_id == "AR-001"
        assert result.body_text != ""

    def test_missing_external_id_raises(self):
        payload = self._valid_payload()
        payload["행정규칙ID"] = ""
        with pytest.raises(ValueError, match="external_id"):
            self._normalize(payload)

    def test_missing_title_raises(self):
        payload = self._valid_payload()
        payload["행정규칙명"] = ""
        with pytest.raises(ValueError, match="title"):
            self._normalize(payload)

    def test_no_body_content_raises(self):
        """조문 없고 부칙/별표도 없으면 placeholder mapper 컨텍스트와 함께 실패."""
        payload = self._valid_payload()
        payload["조문"] = []
        payload.pop("부칙내용", None)
        payload.pop("별표내용", None)
        with pytest.raises(ValueError, match="placeholder mapper"):
            self._normalize(payload)

    def test_body_field_without_articles_succeeds(self):
        """조문 없어도 부칙내용이 있으면 성공."""
        payload = self._valid_payload()
        payload["조문"] = []
        payload["부칙내용"] = "이 훈령은 공포한 날부터 시행한다."
        result = self._normalize(payload)
        assert "이 훈령은 공포한 날부터" in result.body_text

    def test_error_message_contains_placeholder_context(self):
        payload = self._valid_payload()
        payload["조문"] = []
        with pytest.raises(ValueError) as exc_info:
            self._normalize(payload)
        assert "placeholder mapper" in str(exc_info.value)

    def test_wrong_field_names_raises(self):
        """실제 응답 구조가 달라 ID / 이름 필드가 없으면 실패."""
        payload = {
            "rule_id": "AR-001",  # 실제 필드명이 다른 경우
            "rule_name": "훈령 제1호",
        }
        with pytest.raises(ValueError):
            self._normalize(payload)


# ══════════════════════════════════════════════════════════════════════════════
# 4. PlatformKnowledgeIngestionService — 실패 정책
# ══════════════════════════════════════════════════════════════════════════════


class TestPlatformIngestionFailurePolicy:
    """
    ingestion service 실패 정책 테스트.

    - 비활성 source_type → PlatformIngestionDisabledError (raw 저장 없음)
    - normalize 실패 → PlatformNormalizeError (raw는 저장됨)
    - chunk 0개 → PlatformNormalizeError (raw는 저장됨)
    """

    def _make_service(self):
        from services.platform.platform_knowledge_ingestion_service import (
            PlatformKnowledgeIngestionService,
        )

        svc = PlatformKnowledgeIngestionService()
        svc._raw_service = MagicMock()
        svc._normalize_service = MagicMock()
        svc._indexing_service = MagicMock()
        return svc

    def _mock_db(self):
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        return db

    def test_disabled_source_type_raises_before_raw_save(self):
        """비활성 source_type은 raw 저장 전에 차단된다."""
        from services.platform.platform_knowledge_ingestion_service import (
            PlatformIngestionDisabledError,
        )

        svc = self._make_service()
        db = self._mock_db()

        with pytest.raises(PlatformIngestionDisabledError, match="비활성"):
            svc.ingest_from_payload(
                db,
                source_type="interpretation",  # 기본 비활성
                external_id="X-001",
                raw_payload={"법령해석례일련번호": "X-001"},
            )

        svc._raw_service.upsert.assert_not_called()

    def test_disabled_admin_rule_raises(self):
        from services.platform.platform_knowledge_ingestion_service import (
            PlatformIngestionDisabledError,
        )

        svc = self._make_service()
        db = self._mock_db()

        with pytest.raises(PlatformIngestionDisabledError):
            svc.ingest_from_payload(
                db,
                source_type="admin_rule",
                external_id="AR-001",
                raw_payload={"행정규칙ID": "AR-001"},
            )

    def test_normalize_failure_raises_after_raw_saved(self):
        """normalize 실패 시 raw는 저장됐지만 document/index는 진행되지 않는다."""
        from services.platform.platform_knowledge_ingestion_service import (
            PlatformNormalizeError,
        )

        svc = self._make_service()
        db = self._mock_db()

        # raw upsert는 성공
        mock_raw_row = MagicMock()
        mock_raw_row.id = 1
        svc._raw_service.upsert.return_value = (mock_raw_row, True)

        # normalize가 실패
        svc._normalize_service.normalize_and_chunk.side_effect = ValueError(
            "external_id 누락"
        )

        with pytest.raises(PlatformNormalizeError):
            svc.ingest_from_payload(
                db,
                source_type="law",
                external_id="LAW-001",
                raw_payload={"법령ID": ""},
            )

        # raw는 저장됨
        svc._raw_service.upsert.assert_called_once()
        # index는 진행되지 않음
        svc._indexing_service.index.assert_not_called()

    def test_empty_chunks_raises_not_succeeds(self):
        """chunk 0개는 성공으로 취급하지 않는다."""
        from services.platform.platform_knowledge_ingestion_service import (
            PlatformNormalizeError,
        )

        svc = self._make_service()
        db = self._mock_db()

        mock_raw_row = MagicMock()
        mock_raw_row.id = 1
        svc._raw_service.upsert.return_value = (mock_raw_row, True)

        # normalize는 성공하지만 chunk가 빈 리스트
        mock_doc = MagicMock()
        svc._normalize_service.normalize_and_chunk.return_value = (mock_doc, [])

        with pytest.raises(PlatformNormalizeError, match="chunk 0개"):
            svc.ingest_from_payload(
                db,
                source_type="law",
                external_id="LAW-001",
                raw_payload={"법령ID": "LAW-001"},
            )

        # index는 진행되지 않음
        svc._indexing_service.index.assert_not_called()

    def test_successful_ingestion_returns_document_and_chunk_count(self):
        """정상 ingestion은 (PlatformDocument, chunk 수)를 반환한다."""
        svc = self._make_service()
        db = self._mock_db()

        mock_raw_row = MagicMock()
        mock_raw_row.id = 1
        svc._raw_service.upsert.return_value = (mock_raw_row, True)

        mock_doc = MagicMock()
        mock_chunk = MagicMock()
        svc._normalize_service.normalize_and_chunk.return_value = (
            mock_doc,
            [mock_chunk, mock_chunk],
        )

        mock_pd = MagicMock()
        svc._indexing_service.index.return_value = (mock_pd, 2)

        pd, n = svc.ingest_from_payload(
            db,
            source_type="law",
            external_id="LAW-001",
            raw_payload={"법령ID": "LAW-001"},
        )

        assert n == 2
        assert pd is mock_pd
        svc._indexing_service.index.assert_called_once()

    def test_noop_checksum_same_returns_existing_document(self):
        """checksum 동일(no-op)이면 기존 document를 반환하고 index를 호출하지 않는다."""
        svc = self._make_service()
        db = self._mock_db()

        mock_raw_row = MagicMock()
        mock_raw_row.id = 1
        svc._raw_service.upsert.return_value = (mock_raw_row, False)  # changed=False

        existing_pd = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = existing_pd

        pd, n = svc.ingest_from_payload(
            db,
            source_type="law",
            external_id="LAW-001",
            raw_payload={"법령ID": "LAW-001"},
        )

        assert pd is existing_pd
        assert n == 0
        svc._indexing_service.index.assert_not_called()
