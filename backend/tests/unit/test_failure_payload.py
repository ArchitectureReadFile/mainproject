from errors import (
    AppException,
    ErrorCode,
    FailureStage,
    build_exception_failure_payload,
    build_failure_payload,
)


def test_build_failure_payload_with_legacy_fields():
    payload = build_failure_payload(
        stage=FailureStage.GENERATE,
        error_code=ErrorCode.LLM_ALL_PROFILES_FAILED,
        status="error",
        include_legacy_error_fields=True,
        retryable=False,
    )

    assert payload["status"] == "error"
    assert payload["failure_stage"] == "generate"
    assert payload["failure_code"] == ErrorCode.LLM_ALL_PROFILES_FAILED.code
    assert payload["error_message"] == ErrorCode.LLM_ALL_PROFILES_FAILED.message
    assert payload["code"] == ErrorCode.LLM_ALL_PROFILES_FAILED.code
    assert payload["message"] == ErrorCode.LLM_ALL_PROFILES_FAILED.message
    assert payload["error_code"] == ErrorCode.LLM_ALL_PROFILES_FAILED.code


def test_build_exception_failure_payload_uses_app_exception_code():
    payload = build_exception_failure_payload(
        stage=FailureStage.PREVIEW,
        exc=AppException(ErrorCode.FILE_NOT_FOUND),
        fallback_error_code=ErrorCode.DOC_INTERNAL_PARSE_ERROR,
    )

    assert payload["failure_stage"] == "preview"
    assert payload["failure_code"] == ErrorCode.FILE_NOT_FOUND.code
    assert payload["error_message"] == ErrorCode.FILE_NOT_FOUND.message
