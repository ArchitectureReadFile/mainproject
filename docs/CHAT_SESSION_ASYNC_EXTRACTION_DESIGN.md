# Chat Session Async Extraction Design

이 문서는 채팅 세션 임시 첨부 문서의 추출/정규화를 동기 요청에서 분리하고,
비동기 task로 이관하기 위한 계약 설계안이다.

목표:
- 큰 PDF/ODL 지연이 채팅 API 응답 시간을 직접 잡아먹지 않게 한다.
- "첨부 저장 성공 + 메시지 저장 성공 + 답변 task enqueue 실패" 같은 partial success를 없앤다.
- 세션 문서 상태를 `processing / ready / failed`로 명시적으로 관리한다.

비목표:
- 세션 문서를 workspace 문서처럼 영속 인덱스로 운영하지 않는다.
- 한 세션에 여러 첨부 문서를 동시에 유지하지 않는다.
- 이번 설계에서 citation 체계까지 확장하지 않는다.

---

## 1. 현재 문제

현재 흐름:

1. `POST /chat/sessions/{id}/messages`
2. multipart `file`가 오면 요청 처리 중 바로 extract/normalize
3. `chat_session_references.extracted_text` 저장
4. 사용자 메시지 저장
5. `process_chat_message.delay()`

문제:
- ODL 지연이 곧 HTTP 응답 지연이다.
- 큰 첨부 문서는 채팅 요청 자체를 timeout/실패로 만들 수 있다.
- 파일 첨부와 메시지 전송이 한 요청에 묶여 있어 상태 분리가 약하다.
- enqueue 실패 시 현재는 보상 처리까지 했지만, 근본적으로는 "첨부 준비"와 "질문 전송"을 같은 계약에 묶는 게 복잡도를 만든다.

핵심 판단:
- 무결성 우선이면 `send_message(file=...)`를 계속 유지하는 설계는 버리는 게 맞다.
- 첨부 업로드와 메시지 전송을 **2단계 계약**으로 분리해야 한다.

---

## 2. 권장 사용자 플로우

### 새 플로우

1. 사용자가 채팅에서 파일 첨부
2. `POST /chat/sessions/{id}/reference-upload`
3. 서버는 reference 상태를 `PROCESSING`으로 저장하고 Celery task enqueue
4. 프론트는 reference 상태를 polling 또는 세션 refresh로 확인
5. 상태가 `READY`가 되면 사용자가 메시지 전송
6. `POST /chat/sessions/{id}/messages`는 이제 **질문 전송만** 담당

### 제거/중단할 계약

- `POST /chat/sessions/{id}/messages`의 multipart `file` 업로드 경로는 제거 대상
- 이후 제거 대상

이유:
- `file + message`를 같은 요청에 유지하면 pending message 상태 저장이 필요해진다.
- 무결성 기준에서는 업로드와 답변 요청을 분리하는 것이 더 명확하다.

---

## 3. 데이터 모델 권장안

채팅 세션에 reference 상태를 직접 추가하는 방식보다,
별도 child entity로 빼는 것이 무결성에 더 맞다.

### 신규 테이블: `chat_session_references`

```text
chat_session_references
- id                         PK
- session_id                 FK(chat_sessions.id), UNIQUE
- source_type                VARCHAR(32)     -- upload | workspace_document
- title                      VARCHAR(255)
- upload_path                TEXT NULL       -- 업로드 파일 임시 경로
- extracted_text             TEXT NULL
- status                     VARCHAR(32)     -- processing | ready | failed
- failure_code               VARCHAR(64) NULL
- error_message              TEXT NULL
- created_at                 DATETIME
- updated_at                 DATETIME
```

관계:
- 한 `ChatSession`은 최대 하나의 active reference만 가진다.
- 새 파일 업로드 시 기존 reference row를 교체하거나 덮어쓴다.

### 보조 테이블: `chat_session_reference_chunks`

```text
chat_session_reference_chunks
- id                         PK
- reference_id               FK(chat_session_references.id)
- chunk_order                INTEGER
- chunk_text                 TEXT
- created_at                 DATETIME
```

의도:
- 추출 성공 후 retrieval용 chunk를 영속 저장한다.
- 질문마다 on-the-fly chunking을 반복하지 않는다.
- 현재는 lexical ranking만 적용하고, 별도 vector/BM25 인덱스는 두지 않는다.

### 왜 `ChatSession`에 직접 넣지 않나

직접 필드 추가안:
- `reference_status`
- `reference_error_message`
- `reference_upload_path`

이 방식도 가능하지만, 아래 문제가 있다.
- 세션 본체와 첨부 상태가 한 엔티티에 섞인다.
- reference lifecycle이 늘어날수록 `ChatSession`이 커진다.
- `workspace_document` 참조와 `upload` 참조의 계약 차이를 분리하기 어렵다.

따라서 무결성 우선이면 **별도 child entity**가 더 낫다.

---

## 4. API 계약 권장안

### A. reference 업로드

```text
POST /api/chat/sessions/{session_id}/reference-upload
Content-Type: multipart/form-data

Form:
- file
```

동작:
- 세션 권한 확인
- 기존 active reference가 있으면 교체 준비
- 업로드 파일을 runtime 경로에 저장
- `chat_session_references.status = "processing"`
- Celery `process_session_reference_document.delay(reference_id)` enqueue
- 응답은 즉시 반환

응답 예시:

```json
{
  "session_id": 12,
  "reference": {
    "status": "processing",
    "title": "계약서.pdf",
    "failure_code": null,
    "error_message": null
  }
}
```

### B. reference 상태 조회

```text
GET /api/chat/sessions/{session_id}/reference
```

응답 예시:

```json
{
  "status": "ready",
  "title": "계약서.pdf",
  "failure_code": null,
  "error_message": null
}
```

### C. reference 삭제

기존:
- `DELETE /api/chat/sessions/{session_id}/reference`

유지:
- 이 endpoint는 유지 가능
- 다만 삭제 대상은 `chat_session_references` row와 temp file

### D. 메시지 전송

```text
POST /api/chat/sessions/{session_id}/messages
```

새 계약:
- `text`
- `group_id`
- `workspace_selection_json`
- **file 없음**

규칙:
- 세션 reference가 `processing`이면:
  - `409 CONFLICT`
  - code: `CHAT_REFERENCE_PROCESSING`
- 세션 reference가 `failed`이면:
  - 질문은 막지 않고 reference 없이 보낼지,
  - 또는 재업로드를 유도할지 정책 결정 필요

권장:
- `processing`일 때만 차단
- `failed`는 reference 사용 불가로만 표시하고 질문 자체는 허용

---

## 5. Celery / 파일 처리 흐름

### 신규 task

```text
tasks.chat_task.process_session_reference_document
queue: chat_reference_queue
```

### 권장 queue

`chat_reference_queue`

이유:
- ODL 추출은 `document_queue`와 같은 유형의 무거운 작업이다.
- 하지만 UX는 chat 첨부 쪽이 더 민감하다.
- workspace bulk upload와 같은 queue에 섞으면 세션 첨부 준비가 밀릴 수 있다.

### task 흐름

1. reference row load
2. `upload_path` 파일 읽기
3. extract/normalize
4. session payload build
5. `extracted_text` 저장
6. `chat_session_reference_chunks` 생성
7. `status = ready`
8. 실패 시:
   - `status = failed`
   - `failure_code`
   - `error_message`
8. 마지막에 temp file 정리

### temp file 저장 위치

권장:

```text
/app/runtime/uploads/chat_references/{session_id}/{uuid}_{filename}
```

이유:
- 기존 document 업로드 경로와 책임 분리
- cleanup 기준이 명확함

---

## 6. 프론트 UX 계약

### 업로드 시
- 파일 첨부 후 즉시 `reference-upload`
- 상태 badge:
  - `분석 중`
  - `준비됨`
  - `실패`

### 메시지 입력창
- reference가 `processing`이면 send 비활성화
- placeholder 예:
  - `첨부 문서를 분석 중입니다...`

### 실패 시
- reference badge에 실패 사유 노출
- 재업로드 버튼 노출

### 기존 optimistic message
- `file + message` 동시 전송이 사라지므로
- enqueue 보상 복잡도가 크게 줄어든다

---

## 7. 오류 계약

### 신규 ErrorCode 권장

```text
CHAT_REFERENCE_PROCESSING
CHAT_REFERENCE_PARSE_FAILED
CHAT_REFERENCE_ENQUEUE_FAILED
```

### failure_stage 권장

```text
enqueue
extract
normalize
finalize
```

저장 위치:
- `chat_session_references.failure_code`
- `chat_session_references.error_message`

---

## 8. 마이그레이션/구현 순서

1. DB
   - `chat_session_references` 추가
2. backend
   - repository/service/router/task 추가
   - 기존 `send_message(file=...)` 경로 제거
3. frontend
   - upload와 send 분리
   - reference status polling / refresh 반영
4. cleanup
   - 구 `ChatSession.reference_document_title/reference_document_text` 제거

---

## 9. 기존 컬럼 처리 방향

기존:
- `chat_session_references.title`
- `chat_session_references.extracted_text`
- `chat_sessions.reference_group_id`

권장:
- `reference_group_id`는 세션 scope reference로 당분간 유지 가능
- document upload reference는 `chat_session_references`로 이동
- 최종적으로는 `chat_sessions`의 legacy reference 컬럼 제거

즉:
- group reference와 upload reference를 같은 컬럼 집합으로 계속 섞지 않는다

---

## 10. 최종 권장안

무결성 우선 기준에서 최종 권장안은 아래다.

- `send_message(file=...)` 계약 제거
- `reference-upload` 비동기 API 신설
- `chat_session_references` child table 도입
- `chat_reference_queue`로 ODL 첨부 추출 분리
- 메시지 전송은 reference가 `READY`일 때만 진행

이 방향이:
- 상태가 가장 명확하고
- partial success를 가장 줄이며
- 이후 다중 첨부/세션 citation 확장에도 가장 유리하다.
