"""
tests/unit/test_document_classification_service.py

DocumentClassificationService 단위테스트.
LLM 실제 호출 없이 LLMClient.call_json을 patch해서 검증한다.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture
def svc():
    from services.document_classification_service import DocumentClassificationService

    return DocumentClassificationService()


_PATCH = "services.document_classification_service.LLMClient.call_json"


# TC-CLS-SVC-01 입력이 모두 비어 있으면 fallback 반환
def test_empty_input_returns_fallback(svc):
    result = svc.classify(title=None, body_text="")
    assert result == {"document_type": "미분류", "category": "미분류"}


def test_whitespace_only_input_returns_fallback(svc):
    result = svc.classify(title="   ", body_text="   ")
    assert result == {"document_type": "미분류", "category": "미분류"}


# TC-CLS-SVC-02 LLM 호출 예외 시 fallback 반환
def test_llm_exception_returns_fallback(svc):
    with patch(_PATCH, side_effect=RuntimeError("LLM 연결 실패")):
        result = svc.classify(title="제목", body_text="본문 내용")
    assert result == {"document_type": "미분류", "category": "미분류"}


# TC-CLS-SVC-03 정상 응답이면 허용값 그대로 반환
def test_valid_response_returned_as_is(svc):
    with patch(_PATCH, return_value={"document_type": "계약서", "category": "계약"}):
        result = svc.classify(title="계약서 제목", body_text="계약 본문")
    assert result == {"document_type": "계약서", "category": "계약"}


# TC-CLS-SVC-04 허용되지 않은 document_type → 미분류
def test_invalid_document_type_normalized(svc):
    with patch(_PATCH, return_value={"document_type": "판결문", "category": "민사"}):
        result = svc.classify(title="제목", body_text="본문")
    assert result["document_type"] == "미분류"
    assert result["category"] == "민사"


# TC-CLS-SVC-05 허용되지 않은 category → 미분류
def test_invalid_category_normalized(svc):
    with patch(_PATCH, return_value={"document_type": "소장", "category": "부동산"}):
        result = svc.classify(title="제목", body_text="본문")
    assert result["document_type"] == "소장"
    assert result["category"] == "미분류"


# TC-CLS-SVC-06 둘 다 허용 안되면 둘 다 미분류
def test_both_invalid_both_normalized(svc):
    with patch(
        _PATCH, return_value={"document_type": "알수없음", "category": "기타아님"}
    ):
        result = svc.classify(title="제목", body_text="본문")
    assert result == {"document_type": "미분류", "category": "미분류"}


# TC-CLS-SVC-07 CLASSIFY_MAX_TEXT_CHARS 기준으로 텍스트가 잘림
# {text} 치환 후 prompt에 실제 들어간 내용을 간접 검증한다.
# 고정 prefix/suffix 길이에 의존하지 않고
# max_chars 길이는 포함되고 초과분은 포함되지 않음을 확인한다.
def test_text_truncated_by_max_chars(svc, monkeypatch):
    monkeypatch.setenv("CLASSIFY_MAX_TEXT_CHARS", "10")

    captured = {}

    def fake_call_json(prompt, **kwargs):
        captured["prompt"] = prompt
        return {"document_type": "기타", "category": "기타"}

    with patch(_PATCH, side_effect=fake_call_json):
        svc.classify(title=None, body_text="A" * 100)

    prompt = captured["prompt"]
    # 잘린 텍스트("A" * 10)는 prompt에 포함
    assert "A" * 10 in prompt
    # 초과분("A" * 11)은 포함되지 않음
    assert "A" * 11 not in prompt
