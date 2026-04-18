# 오류 정규화 설계

## 1. 목적

- HTTP API 오류 계약은 유지한다.
- 비동기 작업, WebSocket, 운영성 로그/실패 기록의 오류 형식을 통일한다.
- 실패 원인을 `상태(status)`와 `원인(failure)`로 분리해 다룬다.
- 이후 DB 반영 여부와 무관하게 동일한 실패 계약을 먼저 적용할 수 있게 한다.

## 2. 현재 상태

### 유지 대상

- `AppException(ErrorCode)`
- FastAPI exception handler
- HTTP 응답의 `code`, `message`, `status_code`

현재 HTTP API 계층은 이미 일관적이다. 이 영역은 구조를 바꾸지 않는다.

### 문제 구간

비동기/운영 경로는 실패 정보를 제각각 남긴다.

- `upload_task.py`
  - `AppException`이면 `{error_code, message}`
  - 일반 예외면 `{error}`
- `chat/processor.py`
  - Redis Pub/Sub 에러 payload가 `{status, code, message}`
  - retrieval 실패는 warning만 찍고 stage 정보 없음
- `export`
  - `error_message`만 저장
- `platform sync`
  - `error_type` 문자열을 별도 규칙으로 사용

즉 HTTP API는 정리돼 있지만, runtime failure contract는 없다.

## 3. 목표 계약

### 3-1. 공통 원칙

- `status`는 현재 처리 상태를 의미한다.
- `failure_*`는 실패 원인을 의미한다.
- 같은 실패 정보를 로그, task return, Redis payload, 운영 표시에서 같은 모양으로 남긴다.

### 3-2. 공통 payload shape

```json
{
  "status": "error",
  "failure_stage": "generate",
  "failure_code": "LLM_006",
  "error_message": "LLM 응답 생성에 실패했습니다.",
  "retryable": false
}
```

필수 필드:

- `status`
- `failure_stage`
- `failure_code`
- `error_message`
- `retryable`

선택 필드:

- `document_id`
- `session_id`
- `group_id`
- `task_id`

## 4. stage 규칙

### 4-1. FailureStage 초안

아래 stage 이름을 공통 enum으로 관리한다.

- `enqueue`
- `preview`
- `extract`
- `normalize`
- `classify`
- `summarize`
- `retrieve`
- `generate`
- `index`
- `deindex`
- `zip_build`
- `finalize`
- `sync_fetch`
- `sync_index`
- `process`

원칙:

- domain-specific 이름보다 공통 실행 단계 이름을 우선한다.
- 호출부에서 실제로 구분 가능한 단계만 사용한다.
- 한 함수가 여러 내부 단계를 감쌀 때는 넓은 stage(`process`)를 허용한다.

### 4-2. stage 적용 기준

#### 문서 업로드 task

- preview 생성 실패 → `preview`
- `ProcessService.process_file()` 전체 실패 → 우선 `process`
  - 이후 내부 서비스가 stage를 더 분리할 수 있으면 `extract/classify/summarize`로 세분화

#### 채팅 processor

- 세션/이력 로드 실패 → `process`
- retrieval 실패 → `retrieve`
- LLM 생성 실패 → `generate`

#### export

- queue enqueue 실패 → `enqueue`
- zip 작성 실패 → `zip_build`
- 완료 처리/파일 정리 실패 → `finalize`

#### platform sync

- 외부 소스 fetch 실패 → `sync_fetch`
- normalize/index 반영 실패 → `sync_index`

## 5. 예외 매핑 규칙

### 5-1. `AppException`

`AppException`은 이미 `ErrorCode`를 갖고 있으므로 그대로 쓴다.

- `failure_code = exc.code`
- `error_message = exc.message`

### 5-2. 일반 예외

일반 예외는 호출부에서 fallback `ErrorCode`를 명시한다.

예:

- upload task generic failure → `DOC_INTERNAL_PARSE_ERROR`
- chat history/process generic failure → `CHAT_HISTORY_LOAD_FAILED`
- chat generate generic failure → `LLM_ALL_PROFILES_FAILED`

원칙:

- generic exception도 반드시 stage를 가진다.
- `except Exception`을 완전히 없애기보다, stage-aware fallback으로 바꾼다.

## 6. backward compatibility

### 6-1. WebSocket

프론트 `useChat`는 현재 `data.message`만 사용한다.

따라서 chat error payload는 아래처럼 확장한다.

```json
{
  "status": "error",
  "code": "CHAT_003",
  "message": "채팅 기록을 불러오지 못했습니다.",
  "failure_stage": "process",
  "failure_code": "CHAT_003",
  "error_message": "채팅 기록을 불러오지 못했습니다.",
  "retryable": false
}
```

즉:

- 기존 `code`, `message`는 유지
- 신규 `failure_*`, `retryable` 추가

### 6-2. HTTP API

HTTP API는 기존 `AppException` 응답 shape를 유지한다.  
이번 정규화는 runtime failure contract를 추가하는 것이지 HTTP 응답 규약을 바꾸는 작업이 아니다.

## 7. 우선 적용 대상

### 7-1. 1순위

- `backend/domains/document/upload_task.py`
- `backend/domains/chat/processor.py`

이유:

- 사용자 체감이 가장 큼
- broad exception으로 정보가 유실되는 대표 구간

### 7-2. 2순위

- `backend/domains/export/service.py`
- `backend/domains/export/tasks.py`
- `backend/domains/platform_sync/sync_task.py`
- `backend/domains/admin/platform_service.py`

#### 현재 적용 상태

- export는 2차 적용 완료
  - `create_job()` enqueue 실패 시 `FAILED + enqueue + EXPORT_005`로 마킹 후 예외 반환
  - `run_group_export_job()` zip 생성 실패 시 `FAILED + zip_build + EXPORT_006`로 정규화
- platform sync는 3차 적용 완료
  - `enqueue_platform_source_sync()` enqueue 실패 시 `run.status=failed`로 정리
  - `PlatformSyncRun.metadata_json`에 `failure_stage/failure_code` 저장
  - `sync_task` return payload를 common failure shape로 정규화
- document는 4차 적용 완료
  - `documents`에 `failure_stage / failure_code / error_message` 저장
  - `upload_task`는 `preview/process` stage 실패를 DB와 task return payload에 함께 반영
  - `ProcessService.process_file()`는 `extract/classify/summarize` stage 실패를 분리 저장
  - 승인 완료 후 index enqueue 실패는 문서 자체를 `FAILED`로 되돌리지 않고 경고로 분리
- chat enqueue는 5차 적용 완료
  - `send_message()`에서 `process_chat_message.delay()` 실패를 `CHAT_ENQUEUE_FAILED`로 표면화
  - enqueue 실패 시 Redis active task key를 남기지 않음
  - enqueue 실패 시 저장된 사용자 메시지와 세션 reference 변경을 보상 트랜잭션으로 원복

## 8. 권장 구현 순서

### 1단계. 공통 오류 모듈 추가

새 파일 예시:

- `backend/errors/failure.py`

포함 내용:

- `FailureStage`
- 공통 failure payload builder
- `AppException` / generic exception 매핑 helper

### 2단계. upload task 적용

목표:

- `AppException`과 일반 예외 모두 같은 payload shape 반환
- `preview`와 `process` stage 구분
- `DocumentStatus.FAILED` 처리 전후 로그에 같은 stage/code 사용

### 3단계. chat processor 적용

목표:

- `_publish_error()`에 stage 추가
- Redis payload에 `failure_*` 추가
- retrieval warning도 stage-aware log로 정리

## 9. DB 반영 범위

현재까지 반영된 DB failure metadata는 아래와 같다.

- `documents.failure_stage`
- `documents.failure_code`
- `documents.error_message`
- `export_jobs.failure_stage`
- `export_jobs.failure_code`

운영성 원칙:

- document/export는 엔티티에 현재 failure 상태를 남긴다.
- chat은 WS payload와 로그를 우선 기준으로 삼는다.
- platform sync는 `PlatformSyncRun.metadata_json`에 failure 메타를 남긴다.

## 10. 적용 완료 기준

아래 조건을 만족하면 1차 정규화가 완료된 것으로 본다.

- `upload_task` 반환 payload shape가 통일됨
- chat WS error payload에 `failure_stage/failure_code/error_message`가 포함됨
- 기존 프론트 소비(`message`)는 깨지지 않음
- generic failure도 stage와 fallback code를 가짐
- 문서/채팅 로그에서 stage 기반 검색이 가능해짐

## 11. 파일별 적용 체크리스트

### 11-1. `backend/domains/document/upload_task.py`

- `preview_service.ensure_preview_pdf()`를 별도 try 블록으로 감싸 `preview` stage 부여
- `ProcessService.process_file()`를 별도 try 블록으로 감싸 `process` stage 부여
- `AppException` branch와 generic exception branch 모두 공통 payload builder 사용
- 반환 shape를 다음으로 통일

```json
{
  "processed": false,
  "document_id": 123,
  "status": "failed",
  "failure_stage": "preview",
  "failure_code": "DOC_006",
  "error_message": "문서 처리 중 서버 내부 오류가 발생했습니다.",
  "retryable": false
}
```

### 11-2. `backend/domains/chat/processor.py`

- `_publish_error()` 시그니처를 `error_code` 단독에서 `stage + error_code`로 확장
- Redis payload에 아래 키 추가
  - `failure_stage`
  - `failure_code`
  - `error_message`
  - `retryable`
- 기존 `code`, `message` 키는 유지
- retrieval 예외는 여전히 degrade gracefully 하되 `retrieve` stage로 로그 정리
- generation 예외는 `generate` stage로 publish
- outer process 예외는 `process` stage로 publish
