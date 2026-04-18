from enum import Enum
from typing import Any

from errors.error_codes import ErrorCode
from errors.exceptions import AppException


class FailureStage(str, Enum):
    ENQUEUE = "enqueue"
    PREVIEW = "preview"
    EXTRACT = "extract"
    NORMALIZE = "normalize"
    CLASSIFY = "classify"
    SUMMARIZE = "summarize"
    RETRIEVE = "retrieve"
    GENERATE = "generate"
    INDEX = "index"
    DEINDEX = "deindex"
    ZIP_BUILD = "zip_build"
    FINALIZE = "finalize"
    SYNC_FETCH = "sync_fetch"
    SYNC_INDEX = "sync_index"
    PROCESS = "process"


def build_failure_payload(
    *,
    stage: FailureStage,
    error_code: ErrorCode,
    status: str = "failed",
    retryable: bool = False,
    include_legacy_error_fields: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status,
        "failure_stage": stage.value,
        "failure_code": error_code.code,
        "error_message": error_code.message,
        "retryable": retryable,
    }
    if include_legacy_error_fields:
        payload["code"] = error_code.code
        payload["message"] = error_code.message
        payload["error_code"] = error_code.code
    payload.update(extra)
    return payload


def build_exception_failure_payload(
    *,
    stage: FailureStage,
    exc: Exception,
    fallback_error_code: ErrorCode,
    status: str = "failed",
    retryable: bool = False,
    include_legacy_error_fields: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    error_code = (
        exc.error_code if isinstance(exc, AppException) else fallback_error_code
    )
    return build_failure_payload(
        stage=stage,
        error_code=error_code,
        status=status,
        retryable=retryable,
        include_legacy_error_fields=include_legacy_error_fields,
        **extra,
    )
