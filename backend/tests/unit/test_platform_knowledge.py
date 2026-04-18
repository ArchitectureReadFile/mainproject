"""
tests/unit/test_platform_knowledge.py

Platform Knowledge 보정 단계 테스트.

커버 범위:
    1. PlatformKnowledgeRetriever — platform corpus 단일 read path
    2. interpretation mapper — required-field validation (실제 필드명 기준)
    3. admin_rule mapper — required-field validation + 중첩 구조 flatten
    4. PlatformKnowledgeIngestionService — 실패 정책
    5. law external_id canonical 계약 — 법령일련번호 기준으로 강제
    6. admin_rule list/str 혼합 payload — str/list/dict 안전 처리
    7. admin_rule annex formatter — 유형 판별 + 요약 텍스트 + chunk 수 제한
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ══════════════════════════════════════════════════════════════════════════════
# 1. PlatformKnowledgeRetriever — platform corpus 단일 read path
# ══════════════════════════════════════════════════════════════════════════════


class TestPlatformKnowledgeRetriever:
    """
    Platform retriever는 platform corpus만 read path로 사용한다.
    """

    def _make_retriever(self):
        from domains.knowledge.platform_knowledge_retriever import (
            PlatformKnowledgeRetriever,
        )

        return PlatformKnowledgeRetriever()

    def _make_request(self):
        from domains.knowledge.schemas import KnowledgeRetrievalRequest

        return KnowledgeRetrievalRequest(
            query="판례 검색", include_platform=True, top_k=3
        )

    def test_platform_corpus_includes_precedent(self):
        """platform corpus 검색 대상에는 precedent가 항상 포함된다."""
        from settings.platform import get_platform_corpus_source_types

        types = get_platform_corpus_source_types()

        assert types == ["precedent", "law", "interpretation", "admin_rule"]

    def test_retrieve_uses_platform_corpus_only(self):
        """retriever는 platform corpus 경로만 호출한다."""
        retriever = self._make_retriever()
        req = self._make_request()

        with patch.object(
            retriever, "_retrieve_platform_chunks", return_value=[]
        ) as mock_platform:
            retriever.retrieve(req)

        mock_platform.assert_called_once()

    def test_include_platform_false_returns_empty(self):
        """include_platform=False이면 platform corpus 검색을 하지 않는다."""
        from domains.knowledge.schemas import KnowledgeRetrievalRequest

        retriever = self._make_retriever()
        req = KnowledgeRetrievalRequest(query="질문", include_platform=False)

        with patch.object(
            retriever, "_retrieve_platform_chunks", return_value=[]
        ) as mock_platform:
            result = retriever.retrieve(req)

        assert result == []
        mock_platform.assert_not_called()

    def test_vector_hit_keeps_platform_payload_fields(self):
        from domains.rag.vector_store import _hit_to_dict

        hit = _hit_to_dict(
            {
                "chunk_id": "platform:precedent:pd:1:chunk:0",
                "platform_document_id": 1,
                "source_type": "precedent",
                "chunk_type": "holding",
                "section_title": "판시사항",
                "chunk_order": 0,
                "text": "판시사항 본문",
                "source_url": "https://example.com",
            },
            0.91,
        )

        assert hit["platform_document_id"] == 1
        assert hit["source_type"] == "precedent"
        assert hit["chunk_type"] == "holding"
        assert hit["text"] == "판시사항 본문"


# ══════════════════════════════════════════════════════════════════════════════
# 2. interpretation mapper — required-field validation (실제 필드명 기준)
# ══════════════════════════════════════════════════════════════════════════════


class TestInterpretationMapperValidation:
    """
    interpretation mapper required-field validation.
    실제 API 필드명: 질의요지 / 회답 / 이유
    """

    def _normalize(self, payload: dict):
        from domains.platform_sync.mappers.interpretation_mapper import normalize

        return normalize(payload)

    def _build_chunks(self, doc, payload: dict):
        from domains.platform_sync.mappers.interpretation_mapper import build_chunks

        return build_chunks(doc, payload)

    def _valid_payload(self) -> dict:
        return {
            "법령해석례일련번호": "12345",
            "안건명": "국세기본법 제XX조 해석",
            "안건번호": "21-0913",
            "질의기관명": "기획재정부",
            "회신기관명": "법제처",
            "회신일자": "20240101",
            "법령해석례상세링크": "https://example.com",
            "질의요지": "이 조항의 해석은 무엇인가?",
            "회답": "해당 조항은 다음과 같이 해석됩니다.",
            "이유": "관련 법령에 따르면 ...",
        }

    def test_valid_payload_succeeds(self):
        result = self._normalize(self._valid_payload())
        assert result.external_id == "12345"
        assert result.body_text != ""

    def test_display_title_includes_responder_and_agenda_no(self):
        """display_title이 '회신기관명 안건번호 안건명' 형식이다."""
        result = self._normalize(self._valid_payload())
        assert "법제처" in result.display_title
        assert "21-0913" in result.display_title

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
        """질의요지/회답/이유 모두 없으면 실패."""
        payload = self._valid_payload()
        payload["질의요지"] = ""
        payload["회답"] = ""
        payload["이유"] = ""
        with pytest.raises(ValueError, match="body 필드"):
            self._normalize(payload)

    def test_partial_body_field_succeeds(self):
        """body 필드 중 하나라도 있으면 성공."""
        payload = self._valid_payload()
        payload["회답"] = ""
        payload["이유"] = ""
        result = self._normalize(payload)
        assert "이 조항의 해석은" in result.body_text

    def test_chunks_use_correct_section_titles(self):
        """chunk section_title이 질의요지/회답/이유로 생성된다."""
        payload = self._valid_payload()
        doc = self._normalize(payload)
        chunks = self._build_chunks(doc, payload)
        section_titles = {c.section_title for c in chunks}
        assert "질의요지" in section_titles
        assert "회답" in section_titles
        assert "이유" in section_titles

    def test_chunks_have_correct_types(self):
        """chunk_type이 question/answer/reason이다."""
        payload = self._valid_payload()
        doc = self._normalize(payload)
        chunks = self._build_chunks(doc, payload)
        chunk_types = {c.chunk_type for c in chunks}
        assert chunk_types == {"question", "answer", "reason"}

    def test_metadata_includes_responder_name(self):
        """metadata에 responder_name이 포함된다."""
        result = self._normalize(self._valid_payload())
        assert result.metadata.get("responder_name") == "법제처"

    def test_wrong_field_names_raises(self):
        """실제 API 필드명이 아닌 경우 실패."""
        payload = {
            "법령해석례일련번호": "12345",
            "안건명": "해석례 제목",
            "질의내용": "질의 내용",
            "회신내용": "회신 내용",
        }
        with pytest.raises(ValueError):
            self._normalize(payload)


# ══════════════════════════════════════════════════════════════════════════════
# 2-1. detail payload canonicalization — wrapper 해제
# ══════════════════════════════════════════════════════════════════════════════


class TestPlatformDetailPayloadCanonicalization:
    """상세 API wrapper를 mapper 입력용 flat payload로 정리한다."""

    def test_precedent_detail_wrapper_is_unwrapped(self):
        from domains.platform_sync.korea_law_open_api_client import (
            canonicalize_detail_payload,
        )

        payload = {
            "PrecService": {
                "판례정보일련번호": "240951",
                "사건명": "근로기준법위반",
                "판시사항": "판시사항 본문",
                "판결요지": "판결요지 본문",
                "판례내용": "판례내용 본문",
            }
        }

        result = canonicalize_detail_payload("precedent", payload)
        assert result["판례정보일련번호"] == "240951"
        assert result["판시사항"] == "판시사항 본문"

    def test_interpretation_detail_wrapper_is_unwrapped(self):
        from domains.platform_sync.korea_law_open_api_client import (
            canonicalize_detail_payload,
        )

        payload = {
            "ExpcService": {
                "법령해석례일련번호": "333401",
                "안건명": "근로기준법 관련",
                "질의요지": "질의",
                "회답": "회답",
                "이유": "이유",
            }
        }

        result = canonicalize_detail_payload("interpretation", payload)
        assert result["법령해석례일련번호"] == "333401"
        assert result["회답"] == "회답"

    def test_admin_rule_detail_wrapper_is_unwrapped(self):
        from domains.platform_sync.korea_law_open_api_client import (
            canonicalize_detail_payload,
        )

        payload = {
            "AdmRulService": {
                "행정규칙기본정보": {
                    "행정규칙ID": "86745",
                    "행정규칙명": "세부 지침",
                },
                "조문내용": ["제1조 내용"],
            }
        }

        result = canonicalize_detail_payload("admin_rule", payload)
        assert "행정규칙기본정보" in result
        assert result["조문내용"] == ["제1조 내용"]

    def test_law_detail_nested_payload_is_flattened(self):
        from domains.platform_sync.korea_law_open_api_client import (
            canonicalize_detail_payload,
        )

        payload = {
            "법령": {
                "기본정보": {
                    "법령ID": "LAW-001",
                    "법령명_한글": "테스트법",
                    "법령명약칭": "테스트",
                    "공포일자": "20240101",
                    "시행일자": "20240201",
                    "소관부처": {"소관부처명": "법제처"},
                },
                "조문": {
                    "조문단위": [{"조문번호": "1", "조문내용": "제1조(목적) ..."}]
                },
                "부칙": {
                    "부칙단위": [{"부칙내용": "이 규칙은 공포한 날부터 시행한다."}]
                },
                "별표": {
                    "별표단위": [{"별표제목": "별표 1", "별표내용": [["표 내용"]]}]
                },
                "제개정이유": {"제개정이유내용": ["제정이유"]},
            }
        }

        result = canonicalize_detail_payload("law", payload)
        assert result["법령ID"] == "LAW-001"
        assert result["법령명_한글"] == "테스트법"
        assert result["소관부처명"] == "법제처"
        assert isinstance(result["조문"], list)
        assert isinstance(result["부칙내용"], list)
        assert isinstance(result["별표내용"], list)
        assert result["제개정이유내용"] == ["제정이유"]


# ══════════════════════════════════════════════════════════════════════════════
# 2-2. normalize service — wrapped detail payload 지원
# ══════════════════════════════════════════════════════════════════════════════


class TestPlatformNormalizeServiceWrappedDetails:
    def test_precedent_wrapped_detail_still_builds_chunks(self):
        from domains.platform_sync.korea_law_open_api_client import (
            canonicalize_detail_payload,
        )
        from domains.platform_sync.platform_document_normalize_service import (
            PlatformDocumentNormalizeService,
        )

        payload = {
            "PrecService": {
                "판례정보일련번호": "240951",
                "사건명": "근로기준법위반",
                "사건번호": "2020도16541",
                "선고일자": "20240627",
                "법원명": "대법원",
                "사건종류명": "형사",
                "판결유형": "판결",
                "판시사항": "판시사항 본문",
                "판결요지": "판결요지 본문",
                "판례내용": "판례내용 본문",
            }
        }

        flat = canonicalize_detail_payload("precedent", payload)
        service = PlatformDocumentNormalizeService()
        doc, chunks = service.normalize_and_chunk("precedent", flat)

        assert doc.external_id == "240951"
        assert len(chunks) == 3

    def test_interpretation_wrapped_detail_still_builds_chunks(self):
        from domains.platform_sync.korea_law_open_api_client import (
            canonicalize_detail_payload,
        )
        from domains.platform_sync.platform_document_normalize_service import (
            PlatformDocumentNormalizeService,
        )

        payload = {
            "ExpcService": {
                "법령해석례일련번호": "333401",
                "안건명": "근로기준법 관련",
                "안건번호": "21-0913",
                "질의기관명": "고용노동부",
                "회신기관명": "법제처",
                "회신일자": "20220426",
                "질의요지": "질의",
                "회답": "회답",
                "이유": "이유",
            }
        }

        flat = canonicalize_detail_payload("interpretation", payload)
        service = PlatformDocumentNormalizeService()
        doc, chunks = service.normalize_and_chunk("interpretation", flat)

        assert doc.external_id == "333401"
        assert {c.chunk_type for c in chunks} == {"question", "answer", "reason"}


# ══════════════════════════════════════════════════════════════════════════════
# 3. admin_rule mapper — required-field validation + 중첩 구조 flatten
# ══════════════════════════════════════════════════════════════════════════════


class TestAdminRuleMapperValidation:
    """admin_rule mapper validation 및 flatten 테스트."""

    def _normalize(self, payload: dict):
        from domains.platform_sync.mappers.admin_rule_mapper import normalize

        return normalize(payload)

    def _build_chunks(self, doc, payload: dict):
        from domains.platform_sync.mappers.admin_rule_mapper import build_chunks

        return build_chunks(doc, payload)

    def _flat_payload(self) -> dict:
        return {
            "행정규칙ID": "AR-001",
            "행정규칙명": "국세청 훈령 제1호",
            "소관부처명": "국세청",
            "발령일자": "20240101",
            "시행일자": "20240101",
            "발령번호": "훈령 제1호",
            "조문": [
                {
                    "조문번호": "1",
                    "조문내용": "이 훈령은 국세청 업무에 관한 기준을 정한다.",
                },
            ],
        }

    def _nested_payload(self) -> dict:
        return {
            "행정규칙기본정보": {
                "행정규칙ID": "AR-002",
                "행정규칙명": "국세청 훈령 제2호",
                "소관부처명": "국세청",
                "발령일자": "20240601",
                "시행일자": "20240601",
                "발령번호": "훈령 제2호",
            },
            "조문내용": [
                {
                    "조문번호": "1",
                    "조문내용": "이 훈령은 세무조사 절차에 관한 사항을 규정한다.",
                },
                {"조문번호": "2", "조문내용": "세무조사는 관할 세무서장이 실시한다."},
            ],
            "부칙": {"부칙내용": "이 훈령은 공포한 날부터 시행한다."},
            "별표": {
                "별표단위": [
                    {"별표내용": "별표 1. 세무조사 대상 선정 기준표"},
                    {"별표내용": "별표 2. 조사결과 통보서 양식"},
                ],
            },
        }

    def test_flat_payload_succeeds(self):
        result = self._normalize(self._flat_payload())
        assert result.external_id == "AR-001"
        assert result.body_text != ""

    def test_missing_external_id_raises(self):
        payload = self._flat_payload()
        payload["행정규칙ID"] = ""
        with pytest.raises(ValueError, match="external_id"):
            self._normalize(payload)

    def test_missing_title_raises(self):
        payload = self._flat_payload()
        payload["행정규칙명"] = ""
        with pytest.raises(ValueError, match="title"):
            self._normalize(payload)

    def test_no_body_content_raises(self):
        payload = self._flat_payload()
        payload["조문"] = []
        with pytest.raises(ValueError, match="모두 없음"):
            self._normalize(payload)

    def test_body_field_without_articles_succeeds(self):
        payload = self._flat_payload()
        payload["조문"] = []
        payload["부칙내용"] = "이 훈령은 공포한 날부터 시행한다."
        result = self._normalize(payload)
        assert "이 훈령은 공포한 날부터" in result.body_text

    def test_nested_payload_normalizes(self):
        result = self._normalize(self._nested_payload())
        assert result.external_id == "AR-002"
        assert result.title == "국세청 훈령 제2호"
        assert result.agency == "국세청"
        assert "세무조사 절차" in result.body_text

    def test_nested_payload_extracts_rule_no(self):
        result = self._normalize(self._nested_payload())
        assert result.metadata.get("rule_no") == "훈령 제2호"

    def test_nested_payload_chunks_include_addendum_and_annex(self):
        payload = self._nested_payload()
        doc = self._normalize(payload)
        chunks = self._build_chunks(doc, payload)
        chunk_types = {c.chunk_type for c in chunks}
        assert "rule" in chunk_types
        assert "addendum" in chunk_types
        assert "annex" in chunk_types

    def test_nested_payload_annex_combined(self):
        payload = self._nested_payload()
        doc = self._normalize(payload)
        chunks = self._build_chunks(doc, payload)
        annex_chunks = [c for c in chunks if c.chunk_type == "annex"]
        assert len(annex_chunks) >= 1
        annex_text = " ".join(c.chunk_text for c in annex_chunks)
        assert "별표 1" in annex_text
        assert "별표 2" in annex_text

    def test_nested_payload_addendum_text(self):
        payload = self._nested_payload()
        doc = self._normalize(payload)
        chunks = self._build_chunks(doc, payload)
        addendum_chunks = [c for c in chunks if c.chunk_type == "addendum"]
        assert len(addendum_chunks) == 1
        assert "공포한 날부터 시행" in addendum_chunks[0].chunk_text

    def test_nested_articles_become_rule_chunks(self):
        payload = self._nested_payload()
        doc = self._normalize(payload)
        chunks = self._build_chunks(doc, payload)
        rule_chunks = [c for c in chunks if c.chunk_type == "rule"]
        assert len(rule_chunks) == 2

    def test_string_article_list_becomes_rule_chunks(self):
        payload = {
            "행정규칙기본정보": {
                "행정규칙ID": "AR-003",
                "행정규칙명": "국세청 훈령 제3호",
                "소관부처명": "국세청",
                "발령일자": "20240701",
                "시행일자": "20240701",
                "발령번호": "훈령 제3호",
            },
            "조문내용": [
                "제1조 이 훈령은 국세청 업무 기준을 정한다.",
                "제2조 세무조사는 관할 세무서장이 실시한다.",
            ],
        }
        doc = self._normalize(payload)
        chunks = self._build_chunks(doc, payload)
        rule_chunks = [c for c in chunks if c.chunk_type == "rule"]
        assert len(rule_chunks) == 2
        assert "제1조" in rule_chunks[0].chunk_text
        assert "제2조" in rule_chunks[1].chunk_text

    def test_single_string_article_becomes_single_rule_chunk(self):
        payload = {
            "행정규칙기본정보": {
                "행정규칙ID": "AR-004",
                "행정규칙명": "국세청 훈령 제4호",
                "소관부처명": "국세청",
                "발령일자": "20240801",
                "시행일자": "20240801",
                "발령번호": "훈령 제4호",
            },
            "조문내용": "제1조 이 훈령은 국세청 업무 기준을 정한다.",
        }
        doc = self._normalize(payload)
        chunks = self._build_chunks(doc, payload)
        rule_chunks = [c for c in chunks if c.chunk_type == "rule"]
        assert len(rule_chunks) == 1
        assert "제1조" in rule_chunks[0].chunk_text

    def test_flat_id_with_raw_nested_fields_still_canonicalizes(self):
        payload = {
            "행정규칙ID": "AR-005",
            "행정규칙명": "국세청 훈령 제5호",
            "소관부처명": "국세청",
            "발령일자": "20240901",
            "시행일자": "20240901",
            "발령번호": "훈령 제5호",
            "조문내용": ["제1조 이 훈령은 mixed payload를 검증한다."],
            "부칙": {"부칙내용": "이 훈령은 공포한 날부터 시행한다."},
            "별표": {"별표단위": [{"별표내용": "별표 1. mixed annex"}]},
        }
        doc = self._normalize(payload)
        chunks = self._build_chunks(doc, payload)
        chunk_types = {c.chunk_type for c in chunks}
        assert doc.external_id == "AR-005"
        assert "mixed payload" in doc.body_text
        assert "addendum" in chunk_types
        assert "annex" in chunk_types
        assert "rule" in chunk_types

    def test_wrong_field_names_raises(self):
        payload = {"rule_id": "AR-001", "rule_name": "훈령 제1호"}
        with pytest.raises(ValueError):
            self._normalize(payload)


# ══════════════════════════════════════════════════════════════════════════════
# 4. PlatformKnowledgeIngestionService — 실패 정책
# ══════════════════════════════════════════════════════════════════════════════


class TestPlatformIngestionFailurePolicy:
    def _make_service(self):
        from domains.platform_sync.platform_knowledge_ingestion_service import (
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
        from domains.platform_sync.platform_knowledge_ingestion_service import (
            PlatformIngestionDisabledError,
        )

        svc = self._make_service()
        db = self._mock_db()
        with patch(
            "domains.platform_sync.platform_knowledge_ingestion_service.is_ingestion_enabled",
            return_value=False,
        ):
            with pytest.raises(PlatformIngestionDisabledError, match="비활성"):
                svc.ingest_from_payload(
                    db,
                    source_type="interpretation",
                    external_id="X-001",
                    raw_payload={"법령해석례일련번호": "X-001"},
                )
        svc._raw_service.upsert.assert_not_called()

    def test_disabled_admin_rule_raises(self):
        from domains.platform_sync.platform_knowledge_ingestion_service import (
            PlatformIngestionDisabledError,
        )

        svc = self._make_service()
        db = self._mock_db()
        with patch(
            "domains.platform_sync.platform_knowledge_ingestion_service.is_ingestion_enabled",
            return_value=False,
        ):
            with pytest.raises(PlatformIngestionDisabledError):
                svc.ingest_from_payload(
                    db,
                    source_type="admin_rule",
                    external_id="AR-001",
                    raw_payload={"행정규칙ID": "AR-001"},
                )

    def test_normalize_failure_raises_after_raw_saved(self):
        from domains.platform_sync.platform_knowledge_ingestion_service import (
            PlatformNormalizeError,
        )

        svc = self._make_service()
        db = self._mock_db()
        mock_raw_row = MagicMock()
        mock_raw_row.id = 1
        svc._raw_service.upsert.return_value = (mock_raw_row, True)
        svc._normalize_service.normalize_and_chunk.side_effect = ValueError(
            "external_id 누락"
        )
        with pytest.raises(PlatformNormalizeError):
            svc.ingest_from_payload(
                db, source_type="law", external_id="LAW-001", raw_payload={"법령ID": ""}
            )
        svc._raw_service.upsert.assert_called_once()
        svc._indexing_service.index.assert_not_called()

    def test_empty_chunks_raises_not_succeeds(self):
        from domains.platform_sync.platform_knowledge_ingestion_service import (
            PlatformNormalizeError,
        )

        svc = self._make_service()
        db = self._mock_db()
        mock_raw_row = MagicMock()
        mock_raw_row.id = 1
        svc._raw_service.upsert.return_value = (mock_raw_row, True)
        mock_doc = MagicMock()
        svc._normalize_service.normalize_and_chunk.return_value = (mock_doc, [])
        with pytest.raises(PlatformNormalizeError, match="chunk 0개"):
            svc.ingest_from_payload(
                db,
                source_type="law",
                external_id="LAW-001",
                raw_payload={"법령ID": "LAW-001"},
            )
        svc._indexing_service.index.assert_not_called()

    def test_successful_ingestion_returns_document_and_chunk_count(self):
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
        svc = self._make_service()
        db = self._mock_db()
        mock_raw_row = MagicMock()
        mock_raw_row.id = 1
        svc._raw_service.upsert.return_value = (mock_raw_row, False)
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


# ══════════════════════════════════════════════════════════════════════════════
# 5. law external_id canonical 계약
# ══════════════════════════════════════════════════════════════════════════════


class TestLawExternalIdCanonical:
    def _make_law_payload(self, law_id: str = "LAW-DETAIL-001") -> dict:
        return {
            "법령ID": law_id,
            "법령명_한글": "테스트법",
            "법령명약칭": "",
            "소관부처명": "법제처",
            "공포일자": "20240101",
            "시행일자": "20240101",
            "조문": [{"조문번호": "1", "조문내용": "이 법은 테스트를 위한 법이다."}],
        }

    def test_law_mapper_external_id_is_law_id(self):
        from domains.platform_sync.mappers.law_mapper import normalize

        doc = normalize(self._make_law_payload("INTERNAL-LAW-ID"))
        assert doc.external_id == "INTERNAL-LAW-ID"

    def test_ingestion_forces_canonical_external_id(self):
        from domains.platform_sync.platform_knowledge_ingestion_service import (
            PlatformKnowledgeIngestionService,
        )

        svc = PlatformKnowledgeIngestionService()
        svc._raw_service = MagicMock()
        svc._indexing_service = MagicMock()
        mock_raw_row = MagicMock()
        mock_raw_row.id = 1
        svc._raw_service.upsert.return_value = (mock_raw_row, True)
        mock_pd = MagicMock()
        svc._indexing_service.index.return_value = (mock_pd, 3)
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        canonical_id = "SERIAL-12345"
        payload = self._make_law_payload(law_id="INTERNAL-DETAIL-ID")
        svc.ingest_from_payload(
            db, source_type="law", external_id=canonical_id, raw_payload=payload
        )
        call_args = svc._indexing_service.index.call_args
        doc_arg = call_args[0][1]
        assert doc_arg.external_id == canonical_id

    def test_ingestion_preserves_law_id_in_metadata(self):
        from domains.platform_sync.platform_knowledge_ingestion_service import (
            PlatformKnowledgeIngestionService,
        )

        svc = PlatformKnowledgeIngestionService()
        svc._raw_service = MagicMock()
        svc._indexing_service = MagicMock()
        mock_raw_row = MagicMock()
        mock_raw_row.id = 1
        svc._raw_service.upsert.return_value = (mock_raw_row, True)
        mock_pd = MagicMock()
        svc._indexing_service.index.return_value = (mock_pd, 3)
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        canonical_id = "SERIAL-99999"
        original_law_id = "INTERNAL-LAW-ID-XYZ"
        payload = self._make_law_payload(law_id=original_law_id)
        svc.ingest_from_payload(
            db, source_type="law", external_id=canonical_id, raw_payload=payload
        )
        call_args = svc._indexing_service.index.call_args
        doc_arg = call_args[0][1]
        assert doc_arg.metadata.get("law_id") == original_law_id

    def test_ingestion_same_id_no_override_needed(self):
        from domains.platform_sync.platform_knowledge_ingestion_service import (
            PlatformKnowledgeIngestionService,
        )

        svc = PlatformKnowledgeIngestionService()
        svc._raw_service = MagicMock()
        svc._indexing_service = MagicMock()
        mock_raw_row = MagicMock()
        mock_raw_row.id = 1
        svc._raw_service.upsert.return_value = (mock_raw_row, True)
        mock_pd = MagicMock()
        svc._indexing_service.index.return_value = (mock_pd, 3)
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        same_id = "SAME-ID-001"
        payload = self._make_law_payload(law_id=same_id)
        svc.ingest_from_payload(
            db, source_type="law", external_id=same_id, raw_payload=payload
        )
        call_args = svc._indexing_service.index.call_args
        doc_arg = call_args[0][1]
        assert doc_arg.external_id == same_id
        assert doc_arg.metadata.get("law_id") in (None, same_id)

    def test_chunk_external_ids_match_canonical(self):
        from domains.platform_sync.platform_knowledge_ingestion_service import (
            PlatformKnowledgeIngestionService,
        )

        svc = PlatformKnowledgeIngestionService()
        svc._raw_service = MagicMock()
        svc._indexing_service = MagicMock()
        mock_raw_row = MagicMock()
        mock_raw_row.id = 1
        svc._raw_service.upsert.return_value = (mock_raw_row, True)
        mock_pd = MagicMock()
        svc._indexing_service.index.return_value = (mock_pd, 1)
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        canonical_id = "SERIAL-77777"
        payload = self._make_law_payload(law_id="DIFFERENT-DETAIL-ID")
        svc.ingest_from_payload(
            db, source_type="law", external_id=canonical_id, raw_payload=payload
        )
        call_args = svc._indexing_service.index.call_args
        chunks_arg = call_args[0][2]
        for chunk in chunks_arg:
            assert chunk.external_id == canonical_id

    def test_law_mapper_uses_flattened_basic_info_for_titles(self):
        from domains.platform_sync.korea_law_open_api_client import (
            canonicalize_detail_payload,
        )
        from domains.platform_sync.mappers.law_mapper import normalize

        payload = {
            "법령": {
                "기본정보": {
                    "법령ID": "LAW-DETAIL-001",
                    "법령명_한글": "테스트법",
                    "법령명약칭": "테스트",
                    "시행일자": "20240101",
                    "소관부처": {"소관부처명": "법제처"},
                },
                "조문": {
                    "조문단위": [{"조문번호": "1", "조문내용": "제1조(목적) 테스트"}]
                },
            }
        }

        canonical = canonicalize_detail_payload("law", payload)
        doc = normalize(canonical)
        assert doc.title == "테스트법"
        assert doc.display_title == "테스트법(테스트)"
        assert doc.agency == "법제처"


# ══════════════════════════════════════════════════════════════════════════════
# 6. admin_rule list/str 혼합 payload 안전 처리
# ══════════════════════════════════════════════════════════════════════════════


class TestAdminRuleListStrMixedPayload:
    def _normalize(self, payload: dict):
        from domains.platform_sync.mappers.admin_rule_mapper import normalize

        return normalize(payload)

    def _build_chunks(self, doc, payload: dict):
        from domains.platform_sync.mappers.admin_rule_mapper import build_chunks

        return build_chunks(doc, payload)

    def _base_info(self, rule_id: str = "AR-MIXED-001") -> dict:
        return {
            "행정규칙기본정보": {
                "행정규칙ID": rule_id,
                "행정규칙명": "혼합 payload 테스트 훈령",
                "소관부처명": "국세청",
                "발령일자": "20240101",
                "시행일자": "20240101",
                "발령번호": "훈령 제1호",
            }
        }

    def test_article_content_as_list_succeeds(self):
        payload = {
            **self._base_info(),
            "조문내용": [{"조문번호": "1", "조문내용": ["이 조항은 가호.", "나호."]}],
        }
        doc = self._normalize(payload)
        chunks = self._build_chunks(doc, payload)
        rule_chunks = [c for c in chunks if c.chunk_type == "rule"]
        assert len(rule_chunks) >= 1
        assert (
            "이 조항은 가호." in rule_chunks[0].chunk_text
            or "나호." in rule_chunks[0].chunk_text
        )

    def test_addendum_as_list_creates_addendum_chunk(self):
        payload = {
            **self._base_info("AR-MIXED-002"),
            "조문내용": [{"조문번호": "1", "조문내용": "조문 내용"}],
            "부칙": {
                "부칙내용": ["이 훈령은 공포한 날부터 시행한다.", "단, 부칙 추가사항."]
            },
        }
        doc = self._normalize(payload)
        chunks = self._build_chunks(doc, payload)
        addendum_chunks = [c for c in chunks if c.chunk_type == "addendum"]
        assert len(addendum_chunks) >= 1
        assert "공포한 날부터" in " ".join(c.chunk_text for c in addendum_chunks)

    def test_annex_content_as_list_creates_annex_chunk(self):
        payload = {
            **self._base_info("AR-MIXED-003"),
            "조문내용": [{"조문번호": "1", "조문내용": "조문 내용"}],
            "별표": {"별표단위": [{"별표내용": ["별표 항목 1", "별표 항목 2"]}]},
        }
        doc = self._normalize(payload)
        chunks = self._build_chunks(doc, payload)
        assert any(c.chunk_type == "annex" for c in chunks)

    def test_article_content_as_str_still_works(self):
        payload = {
            **self._base_info("AR-MIXED-004"),
            "조문내용": [{"조문번호": "1", "조문내용": "이 훈령은 기존 str 형식이다."}],
        }
        doc = self._normalize(payload)
        chunks = self._build_chunks(doc, payload)
        rule_chunks = [c for c in chunks if c.chunk_type == "rule"]
        assert len(rule_chunks) == 1
        assert "기존 str 형식" in rule_chunks[0].chunk_text

    def test_addendum_as_str_still_works(self):
        payload = {
            **self._base_info("AR-MIXED-005"),
            "조문내용": [{"조문번호": "1", "조문내용": "조문"}],
            "부칙": {"부칙내용": "이 훈령은 공포한 날부터 시행한다."},
        }
        doc = self._normalize(payload)
        chunks = self._build_chunks(doc, payload)
        addendum_chunks = [c for c in chunks if c.chunk_type == "addendum"]
        assert len(addendum_chunks) == 1
        assert "공포한 날부터" in addendum_chunks[0].chunk_text

    def test_annex_as_str_still_works(self):
        payload = {
            **self._base_info("AR-MIXED-006"),
            "조문내용": [{"조문번호": "1", "조문내용": "조문"}],
            "별표": {"별표단위": [{"별표내용": "별표 1. 기준표"}]},
        }
        doc = self._normalize(payload)
        chunks = self._build_chunks(doc, payload)
        annex_chunks = [c for c in chunks if c.chunk_type == "annex"]
        assert len(annex_chunks) == 1
        assert "기준표" in annex_chunks[0].chunk_text

    def test_no_strip_error_on_list_content(self):
        payload = {
            **self._base_info("AR-MIXED-007"),
            "조문내용": [
                {
                    "조문번호": "1",
                    "조문내용": ["항목1 내용", "항목2 내용", "항목3 내용"],
                },
                {"조문번호": "2", "조문내용": "일반 문자열 조문"},
            ],
            "부칙": {"부칙내용": ["부칙1", "부칙2"]},
            "별표": {"별표단위": [{"별표내용": ["별표내용1", "별표내용2"]}]},
        }
        doc = self._normalize(payload)
        chunks = self._build_chunks(doc, payload)
        assert len(chunks) > 0
        chunk_types = {c.chunk_type for c in chunks}
        assert "rule" in chunk_types
        assert "addendum" in chunk_types
        assert "annex" in chunk_types

    def test_heading_lines_do_not_create_standalone_rule_chunks(self):
        payload = {
            **self._base_info("AR-MIXED-008"),
            "조문내용": [
                "제1장 총칙",
                {"조문번호": "1", "조문내용": "이 훈령은 업무 기준을 정한다."},
                "제2장 인사관리",
                "제1절 채용",
                {"조문번호": "2", "조문내용": "채용은 공개모집을 원칙으로 한다."},
            ],
        }
        doc = self._normalize(payload)
        chunks = self._build_chunks(doc, payload)
        rule_chunks = [c for c in chunks if c.chunk_type == "rule"]

        assert len(rule_chunks) == 2
        assert all("제1장 총칙" not in c.chunk_text for c in rule_chunks)
        assert all("제2장 인사관리" not in c.chunk_text for c in rule_chunks)
        assert all("제1절 채용" not in c.chunk_text for c in rule_chunks)
        assert "제1장 총칙" in doc.body_text
        assert "제2장 인사관리" in doc.body_text

    def test_heading_lines_are_preserved_as_section_context(self):
        payload = {
            **self._base_info("AR-MIXED-009"),
            "조문내용": [
                "제2장 정원관리",
                "제1절 채용 등 인사관리",
                {
                    "조문번호": "5",
                    "조문내용": "사용부서의 장은 인력을 효율적으로 관리하여야 한다.",
                },
            ],
        }
        doc = self._normalize(payload)
        chunks = self._build_chunks(doc, payload)
        rule_chunks = [c for c in chunks if c.chunk_type == "rule"]

        assert len(rule_chunks) == 1
        assert (
            rule_chunks[0].section_title
            == "제2장 정원관리 / 제1절 채용 등 인사관리 / 제5조"
        )
        assert rule_chunks[0].metadata.get("heading_context") == [
            "제2장 정원관리",
            "제1절 채용 등 인사관리",
        ]


# ══════════════════════════════════════════════════════════════════════════════
# 7. admin_rule annex formatter — 유형 판별 + 요약 텍스트 + chunk 수 제한
# ══════════════════════════════════════════════════════════════════════════════


class TestAdminRuleAnnexFormatter:
    """
    admin_rule annex 처리 전략:
        - plain_text: 자연어 → 거의 그대로 1 chunk
        - table: box-drawing 문자 포함 → 레이아웃 노이즈 제거, annex_type="table"
        - flowchart: 흐름도 키워드 + 단계 패턴 → 단계형 텍스트, annex_type="flowchart"
        - chunk 수 제한: 매우 긴 annex도 최대 2개 chunk
        - raw payload 저장 로직 영향 없음
    """

    # ── classify_annex_text ──────────────────────────────────────────────────

    def test_plain_text_classified_as_plain(self):
        """자연어 annex는 plain_text로 분류된다."""
        from domains.platform_sync.mappers.admin_rule_annex_formatter import (
            classify_annex_text,
        )

        text = "별표 1. 세무조사 대상 선정 기준\n\n1. 매출액 기준 이상인 사업자\n2. 불성실 신고 이력이 있는 자"
        assert classify_annex_text(text) == "plain_text"

    def test_box_drawing_chars_classified_as_table(self):
        """box-drawing 문자가 많은 annex는 table 또는 diagram_like로 분류된다."""
        from domains.platform_sync.mappers.admin_rule_annex_formatter import (
            classify_annex_text,
        )

        text = (
            "┌────────────┬────────────┐\n"
            "│  구분       │  내용       │\n"
            "├────────────┼────────────┤\n"
            "│  1종        │  일반       │\n"
            "│  2종        │  특수       │\n"
            "└────────────┴────────────┘"
        )
        result = classify_annex_text(text)
        assert result in ("table", "diagram_like")

    def test_flowchart_keyword_with_steps_classified_as_flowchart(self):
        """흐름도 키워드 + 단계 패턴이 있으면 flowchart로 분류된다."""
        from domains.platform_sync.mappers.admin_rule_annex_formatter import (
            classify_annex_text,
        )

        text = "흐름도\n1. 신청서 접수\n2. 검토 및 심사\n3. 승인 결재\n4. 통보"
        assert classify_annex_text(text) == "flowchart"

    def test_separator_lines_classified_as_table(self):
        """구분선 반복이 많으면 table로 분류된다."""
        from domains.platform_sync.mappers.admin_rule_annex_formatter import (
            classify_annex_text,
        )

        text = "항목 A\n--------\n내용 A\n--------\n항목 B\n--------\n내용 B"
        assert classify_annex_text(text) == "table"

    # ── normalize_annex_for_rag ──────────────────────────────────────────────

    def test_plain_text_normalized_preserves_content(self):
        """plain_text annex는 내용이 유지되고 연속 공백/개행만 정리된다."""
        from domains.platform_sync.mappers.admin_rule_annex_formatter import (
            normalize_annex_for_rag,
        )

        text = "별표 1. 기준\n\n\n세부 내용입니다.\n  항목 A  \n항목 B"
        result = normalize_annex_for_rag(text, "plain_text")
        assert "기준" in result
        assert "세부 내용" in result
        assert "\n\n\n" not in result

    def test_table_normalized_removes_box_chars(self):
        """table annex 정규화 결과에는 box-drawing 문자 비율이 현저히 줄어든다."""
        from domains.platform_sync.mappers.admin_rule_annex_formatter import (
            _BOX_CHARS,
            classify_annex_text,
            normalize_annex_for_rag,
        )

        text = (
            "┌────────────┬────────────┐\n"
            "│  구분       │  내용       │\n"
            "├────────────┼────────────┤\n"
            "│  1종        │  일반 업무  │\n"
            "│  2종        │  특수 업무  │\n"
            "└────────────┴────────────┘"
        )
        annex_type = classify_annex_text(text)
        result = normalize_annex_for_rag(text, annex_type)

        box_count = sum(1 for c in result if c in _BOX_CHARS)
        box_ratio = box_count / len(result) if result else 0
        assert box_ratio < 0.01
        assert "구분" in result or "내용" in result or "일반" in result

    def test_flowchart_normalized_has_step_structure(self):
        """flowchart annex 정규화 결과는 단계형 구조를 갖는다."""
        from domains.platform_sync.mappers.admin_rule_annex_formatter import (
            normalize_annex_for_rag,
        )

        text = "흐름도\n1. 신청서 접수\n2. 검토 및 심사\n3. 승인 결재\n4. 통보"
        result = normalize_annex_for_rag(text, "flowchart")
        assert "흐름도" in result or "절차" in result
        assert "접수" in result or "심사" in result

    def test_empty_annex_returns_empty(self):
        """빈 annex는 빈 문자열을 반환한다."""
        from domains.platform_sync.mappers.admin_rule_annex_formatter import (
            normalize_annex_for_rag,
        )

        assert normalize_annex_for_rag("", "plain_text") == ""
        assert normalize_annex_for_rag("   ", "table") == ""

    # ── build_annex_chunks_text ──────────────────────────────────────────────

    def test_short_annex_creates_single_chunk(self):
        """짧은 annex는 1개 chunk로 생성된다."""
        from domains.platform_sync.mappers.admin_rule_annex_formatter import (
            build_annex_chunks_text,
        )

        text = "별표 1. 기준표\n\n항목 A: 값 A\n항목 B: 값 B"
        chunks, annex_type = build_annex_chunks_text(text)
        assert len(chunks) == 1

    def test_very_long_annex_capped_at_max_chunks(self):
        """매우 긴 annex도 최대 2개 chunk로 제한된다."""
        from domains.platform_sync.mappers.admin_rule_annex_formatter import (
            _MAX_ANNEX_CHUNKS,
            build_annex_chunks_text,
        )

        text = "별표 내용입니다. " * 800
        chunks, _ = build_annex_chunks_text(text)
        assert len(chunks) <= _MAX_ANNEX_CHUNKS
        assert len(chunks) >= 1

    def test_annex_type_returned_correctly(self):
        """build_annex_chunks_text는 (chunks, annex_type) 튜플을 반환한다."""
        from domains.platform_sync.mappers.admin_rule_annex_formatter import (
            build_annex_chunks_text,
        )

        table_text = (
            "┌──────┬──────┐\n│ 항목  │ 값   │\n"
            "├──────┼──────┤\n│ A    │ 1    │\n└──────┴──────┘"
        )
        chunks, annex_type = build_annex_chunks_text(table_text)
        assert annex_type in ("table", "diagram_like")
        assert len(chunks) >= 1

    # ── mapper 통합: annex chunk metadata ────────────────────────────────────

    def test_annex_chunk_has_annex_type_in_metadata(self):
        """build_chunks()로 생성된 annex chunk는 metadata에 annex_type을 갖는다."""
        from domains.platform_sync.mappers.admin_rule_mapper import (
            build_chunks,
            normalize,
        )

        payload = {
            "행정규칙기본정보": {
                "행정규칙ID": "AR-ANNEX-001",
                "행정규칙명": "별표 테스트 훈령",
                "소관부처명": "국세청",
                "발령일자": "20240101",
                "시행일자": "20240101",
                "발령번호": "훈령 제1호",
            },
            "조문내용": [{"조문번호": "1", "조문내용": "조문 내용"}],
            "별표": {
                "별표단위": [{"별표내용": "별표 1. 기준\n항목 A: 값 A\n항목 B: 값 B"}]
            },
        }
        doc = normalize(payload)
        chunks = build_chunks(doc, payload)
        annex_chunks = [c for c in chunks if c.chunk_type == "annex"]
        assert len(annex_chunks) >= 1
        assert "annex_type" in annex_chunks[0].metadata
        assert annex_chunks[0].metadata.get("normalized_from") == "raw_annex"

    def test_table_annex_chunk_has_reduced_box_chars(self):
        """표형 별표가 mapper를 통과하면 chunk_text에 box 문자가 거의 없다."""
        from domains.platform_sync.mappers.admin_rule_annex_formatter import _BOX_CHARS
        from domains.platform_sync.mappers.admin_rule_mapper import (
            build_chunks,
            normalize,
        )

        table_annex = (
            "┌────────────┬────────────┐\n│  구분       │  내용       │\n"
            "├────────────┼────────────┤\n│  1종        │  일반 업무  │\n"
            "│  2종        │  특수 업무  │\n└────────────┴────────────┘"
        )
        payload = {
            "행정규칙기본정보": {
                "행정규칙ID": "AR-TABLE-001",
                "행정규칙명": "표 별표 훈령",
                "소관부처명": "국세청",
                "발령일자": "20240101",
                "시행일자": "20240101",
                "발령번호": "훈령 제2호",
            },
            "조문내용": [{"조문번호": "1", "조문내용": "조문"}],
            "별표": {"별표단위": [{"별표내용": table_annex}]},
        }
        doc = normalize(payload)
        chunks = build_chunks(doc, payload)
        annex_chunks = [c for c in chunks if c.chunk_type == "annex"]
        assert len(annex_chunks) >= 1
        for chunk in annex_chunks:
            box_count = sum(1 for c in chunk.chunk_text if c in _BOX_CHARS)
            box_ratio = box_count / len(chunk.chunk_text) if chunk.chunk_text else 0
            assert box_ratio < 0.01

    def test_plain_annex_chunk_count_is_one(self):
        """짧은 plain_text 별표는 annex chunk 1개로 생성된다."""
        from domains.platform_sync.mappers.admin_rule_mapper import (
            build_chunks,
            normalize,
        )

        payload = {
            "행정규칙기본정보": {
                "행정규칙ID": "AR-PLAIN-001",
                "행정규칙명": "평문 별표 훈령",
                "소관부처명": "국세청",
                "발령일자": "20240101",
                "시행일자": "20240101",
                "발령번호": "훈령 제3호",
            },
            "조문내용": [{"조문번호": "1", "조문내용": "조문"}],
            "별표": {
                "별표단위": [
                    {
                        "별표내용": "별표 1. 세무조사 대상 기준\n\n매출액 10억 이상인 사업자"
                    }
                ]
            },
        }
        doc = normalize(payload)
        chunks = build_chunks(doc, payload)
        annex_chunks = [c for c in chunks if c.chunk_type == "annex"]
        assert len(annex_chunks) == 1

    def test_very_long_annex_via_mapper_capped(self):
        """mapper를 통해도 매우 긴 별표는 최대 2개 annex chunk로 제한된다."""
        from domains.platform_sync.mappers.admin_rule_annex_formatter import (
            _MAX_ANNEX_CHUNKS,
        )
        from domains.platform_sync.mappers.admin_rule_mapper import (
            build_chunks,
            normalize,
        )

        long_annex = "별표 항목 내용입니다. " * 800
        payload = {
            "행정규칙기본정보": {
                "행정규칙ID": "AR-LONG-001",
                "행정규칙명": "긴 별표 훈령",
                "소관부처명": "국세청",
                "발령일자": "20240101",
                "시행일자": "20240101",
                "발령번호": "훈령 제4호",
            },
            "조문내용": [{"조문번호": "1", "조문내용": "조문"}],
            "별표": {"별표단위": [{"별표내용": long_annex}]},
        }
        doc = normalize(payload)
        chunks = build_chunks(doc, payload)
        annex_chunks = [c for c in chunks if c.chunk_type == "annex"]
        assert len(annex_chunks) <= _MAX_ANNEX_CHUNKS

    def test_body_text_does_not_contain_raw_box_chars(self):
        """표형 별표의 box 문자가 body_text에 그대로 섞이지 않는다."""
        from domains.platform_sync.mappers.admin_rule_annex_formatter import _BOX_CHARS
        from domains.platform_sync.mappers.admin_rule_mapper import normalize

        table_annex = (
            "┌────────────┬────────────┐\n│  구분       │  내용       │\n"
            "└────────────┴────────────┘"
        )
        payload = {
            "행정규칙기본정보": {
                "행정규칙ID": "AR-BODY-001",
                "행정규칙명": "body_text 검증 훈령",
                "소관부처명": "국세청",
                "발령일자": "20240101",
                "시행일자": "20240101",
                "발령번호": "훈령 제5호",
            },
            "조문내용": [{"조문번호": "1", "조문내용": "조문"}],
            "별표": {"별표단위": [{"별표내용": table_annex}]},
        }
        doc = normalize(payload)
        box_count = sum(1 for c in doc.body_text if c in _BOX_CHARS)
        box_ratio = box_count / len(doc.body_text) if doc.body_text else 0
        assert box_ratio < 0.01

    def test_rule_addendum_chunks_unaffected(self):
        """annex 전략 변경이 rule/addendum chunk 생성에 영향을 주지 않는다."""
        from domains.platform_sync.mappers.admin_rule_mapper import (
            build_chunks,
            normalize,
        )

        payload = {
            "행정규칙기본정보": {
                "행정규칙ID": "AR-REG-001",
                "행정규칙명": "회귀 검증 훈령",
                "소관부처명": "국세청",
                "발령일자": "20240101",
                "시행일자": "20240101",
                "발령번호": "훈령 제6호",
            },
            "조문내용": [
                {"조문번호": "1", "조문내용": "이 훈령은 업무 기준을 정한다."},
                {"조문번호": "2", "조문내용": "세무조사는 관할 세무서장이 실시한다."},
            ],
            "부칙": {"부칙내용": "이 훈령은 공포한 날부터 시행한다."},
            "별표": {"별표단위": [{"별표내용": "별표 1. 기준표\n항목: 값"}]},
        }
        doc = normalize(payload)
        chunks = build_chunks(doc, payload)
        chunk_types = {c.chunk_type for c in chunks}
        rule_chunks = [c for c in chunks if c.chunk_type == "rule"]
        addendum_chunks = [c for c in chunks if c.chunk_type == "addendum"]
        assert "rule" in chunk_types
        assert "addendum" in chunk_types
        assert "annex" in chunk_types
        assert len(rule_chunks) == 2
        assert len(addendum_chunks) == 1
