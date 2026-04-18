# User Flow Review

이 문서는 실제 사용자 플로우를 기준으로 시스템 흐름을 정의하고, 각 플로우별 안정성/동시성/병목/상태 불일치 리스크를 점검하기 위한 리뷰 문서다.

검토 원칙:
- 화면 기준이 아니라 실제 사용자 행동 기준으로 플로우를 나눈다.
- 각 플로우의 진입점, 주요 상태 전이, 공유 자원, 비동기 작업을 먼저 적는다.
- 검토 결과는 각 플로우 하단의 `검토 메모`와 `발견 이슈`에 누적한다.
- 구현 변경 전, 먼저 이 문서에서 문제를 구조적으로 정리한다.

---

## 전체 플로우 목록

1. 인증 플로우
2. 워크스페이스 플로우
3. 문서 업로드·검토 플로우
4. 워크스페이스 RAG 채팅 플로우
5. 세션 첨부 문서 채팅 플로우
6. 전체 다운로드 플로우
7. 관리자·플랫폼 동기화 플로우

---

## 1. 인증 플로우

### 사용자 흐름
- 랜딩 진입
- 이메일 인증 또는 소셜 로그인
- 토큰 발급 및 세션 유지
- 마이페이지/워크스페이스 진입

### 주요 진입점
- Frontend
  - `frontend/src/pages/Landing`
  - `frontend/src/pages/Mypage`
- Backend
  - `/api/auth/*`
  - `/api/auth/social/*`
  - `/api/email/*`

### 주요 상태 / 자원
- User
- 소셜 계정 연동 정보
- access / refresh 토큰
- 로그인 시도 제한 Redis 키

### 비동기 / 외부 연동
- 이메일 인증 코드 발송
- OAuth provider
- Redis rate-limit

### 검토 메모
- 업로드 요청은 원본 파일 저장 → Document/Approval 생성 → commit → `process_next_pending_document.delay()` 순으로 진행된다.
- 실제 처리 큐 진입점은 `process_next_pending_document` 1개이며, task 내부에서 다음 PENDING 문서를 다시 enqueue하는 체인 방식이다.
- 처리 파이프라인은 preview 생성 → extract/normalize → classify → summarize → DONE → APPROVED면 index enqueue 순서다.
- 승인과 인덱싱은 분리돼 있다. 승인 시점과 처리 완료 시점 중 어느 쪽이 먼저 와도 `APPROVED + DONE` 시점에 인덱싱되도록 계약이 정리돼 있다.
- 삭제는 `DELETE_PENDING`으로 먼저 전환하고, APPROVED 문서면 즉시 deindex task를 enqueue한다. 최종 파일 삭제는 별도 task/beat가 담당한다.

### 발견 이슈
- 현재 즉시 운영 리스크:
  - 업로드 commit 이후 `process_next_pending_document.delay()` 호출이 실패하면 문서가 `PENDING` 상태로 남을 수 있다. 현재 이를 주기적으로 다시 깨워주는 sweep task는 없다.
  - 문서 삭제/복구는 lifecycle 상태를 먼저 commit한 뒤 deindex/index task와 알림을 보낸다. 후속 enqueue 또는 알림 실패 시 상태와 부수효과가 어긋나는 partial success가 가능하다.
  - 처리 중인 문서도 삭제 가능하다. 이 경우 이미 시작된 preview/요약 작업은 계속 진행되고, 마지막 인덱싱만 stale lifecycle 체크로 스킵된다. 불필요한 처리 비용이 남는다.
  - `process_file()`은 extract/classify/summarize 어느 단계에서 실패해도 최종적으로 동일한 `FAILED`로 합쳐 처리한다. 운영에서 원인 구분이 어렵다.
- 구조적/확장 리스크:
  - `claim_next_pending_document()`는 단순 조회 후 상태 변경 방식이다. 현재 서버는 `document_worker` 1개라 즉시 충돌은 적지만, document worker를 수평 확장하면 중복 claim 방어가 약하다.
  - 원본 파일은 DB commit 전에 먼저 저장된다. 이후 DB/알림 단계에서 예외가 나면 orphan 파일이 남을 수 있다.

---

## 2. 워크스페이스 플로우

### 사용자 흐름
- 그룹 생성 또는 초대 수락
- 멤버 초대/수락/거절
- 역할 권한 관리
- 그룹 상세 진입

### 주요 진입점
- Frontend
  - `frontend/src/pages/Workspace`
- Backend
  - `/api/groups/*`
  - `/api/notifications/*`

### 주요 상태 / 자원
- Group
- GroupMember
- 초대 알림 / 멤버 상태
- 역할(OWNER / ADMIN / MEMBER)

### 비동기 / 외부 연동
- 알림 발송
- 삭제 예정 workspace 정리 task

### 검토 메모
- 채팅 요청은 API에서 사용자 메시지를 먼저 DB에 저장한 뒤, Celery `process_chat_message` task를 enqueue한다.
- 실제 답변 생성은 `chat_queue`에서 수행되고, 진행 상태/토큰 스트림은 Redis Pub/Sub 채널 `chat:{session_id}:{user_id}`로 WebSocket에 전달된다.
- retrieval 조립은 `platform / workspace / session` 3개 지식원을 합쳐 answer context를 만드는 구조다.
- workspace RAG는 `group_id + workspace_selection`이 있을 때만 활성화된다.
- session 문서는 별도 인덱스가 아니라 세션 텍스트 payload로 컨텍스트에 주입된다.

### 발견 이슈
- 현재 즉시 운영 리스크:
  - 사용자 메시지는 task enqueue 전에 먼저 DB에 저장된다. enqueue 실패 시 사용자 메시지만 남고 답변은 생성되지 않는 partial success가 가능하다.
  - `stop_message()`는 Redis에 저장된 task id를 revoke/kill 하지만, 이미 생성된 assistant 메시지 저장 직전 상태와 경합할 수 있다. 사용자는 stop을 눌렀어도 일부 답변이 저장될 수 있다.
  - Redis Pub/Sub는 비내구성 채널이다. WebSocket이 잠시 끊기면 중간 스트림 조각은 유실된다. 현재는 완료 후 assistant full message만 DB에 남는다.
  - retrieval 실패는 warning으로만 남기고 답변 생성은 계속한다. 사용자 입장에서는 “참조 실패”와 “일반 답변”이 구분되지 않을 수 있다.
- 현재 확인된 품질/설계 이슈:
  - 워크스페이스 참조는 group/document 범위를 보내지만, 실제 retrieval query는 마지막 사용자 메시지 그대로 사용한다. 질문이 짧거나 모호하면 그룹 참조가 붙어 있어도 검색 품질이 낮다.
  - 세션 첨부 문서는 chunk retrieval이 아니라 단일 텍스트 payload로만 들어간다. 긴 문서는 앞부분 위주로 잘려 실제 참조 품질이 낮다.
  - 세션 문서는 업로드 시 1차 truncate, answer context 조립 시 2차 truncate가 걸려 장문 참조 품질이 더 떨어진다.
- 구조적/확장 리스크:
  - 세션별 active task 추적이 Redis key `chat_task:{session_id}` 하나로만 이뤄진다. 동일 세션에 대해 중복 요청이 겹치면 새 task가 이전 task id를 덮어쓸 수 있다.
  - 현재 chat worker 병렬도는 높지만, 세션 단위 직렬화 락은 없다. 같은 세션에 대한 연속 요청이 빠르게 겹치면 응답 순서와 session summary 기준점이 흔들릴 수 있다.

---

## 3. 문서 업로드·검토 플로우

### 사용자 흐름
- 문서 업로드
- preview 생성
- ODL 추출 및 정규화
- 분류/요약
- 검토/승인/반려
- 승인 완료 시 인덱싱 반영

### 주요 진입점
- Frontend
  - `frontend/src/pages/Upload`
  - `frontend/src/pages/Workspace/DocumentsTab`
  - `frontend/src/pages/Workspace/ApprovalsTab`
- Backend
  - `/api/groups/{group_id}/documents/*`
  - summary / classification / approval 관련 service/task

### 주요 상태 / 자원
- Document
- Approval
- Summary
- preview PDF
- normalized document cache
- runtime/uploads
- runtime/cache

### 비동기 / 외부 연동
- Celery document queue
- ODL hybrid
- Ollama 분류/요약
- Qdrant / BM25 인덱싱

### 검토 메모
- 미작성

### 발견 이슈
- 없음

---

## 4. 워크스페이스 RAG 채팅 플로우

### 사용자 흐름
- 채팅 세션 생성
- 그룹/문서 범위 선택
- workspace retrieval
- 근거 문서 검색
- 답변 생성 및 스트리밍

### 주요 진입점
- Frontend
  - `frontend/src/pages/Landing`
  - `frontend/src/features/chat/*`
- Backend
  - `/api/chat/*`
  - `/api/ws/*`

### 주요 상태 / 자원
- ChatSession
- ChatMessage
- workspace selection
- 검색 결과 context
- platform/workspace/session knowledge item

### 비동기 / 외부 연동
- WebSocket 스트리밍
- Qdrant
- BM25
- Ollama 답변 생성

### 검토 메모
- 미작성

### 발견 이슈
- 없음

---

## 5. 세션 첨부 문서 채팅 플로우

### 사용자 흐름
- 채팅 중 임시 문서 업로드
- 추출/정규화
- 세션 reference 문서 저장
- 채팅 답변 시 session knowledge로 참조

### 주요 진입점
- Frontend
  - `frontend/src/features/chat/*`
- Backend
  - `/api/chat/sessions/{session_id}/messages`
  - `/api/chat/sessions/{session_id}/reference`

### 주요 상태 / 자원
- ChatSession.reference_document_text
- 세션 문서 추출 결과
- 세션 knowledge item

### 비동기 / 외부 연동
- ODL 추출
- Ollama 답변 생성

### 검토 메모
- 세션 첨부 문서는 별도 문서 엔티티나 인덱스로 관리하지 않고, `ChatSession.reference_document_title / reference_document_text` 두 필드에 직접 저장한다.
- 임시 문서 업로드 API와 `send_message(file_bytes=...)` 경로 모두 요청 처리 중에 바로 extract/normalize를 수행한다. 즉 세션 문서 추출은 Celery 비동기 작업이 아니라 동기 처리다.
- 세션 문서 payload는 `DocumentSchema`에서 `[본문] + [표]` 형태의 단일 텍스트로 조립한 뒤 세션에 저장한다.
- retrieval 시 session 지식원은 query-aware chunk 검색을 하지 않고, 저장된 세션 텍스트 전체를 `RetrievedKnowledgeItem` 1개로 감싼 뒤 platform/workspace 결과와 함께 합친다.
- answer context 조립 단계에서 session 블록은 별도 top-k / max-char 제한을 다시 적용한다. 즉 세션 문서는 저장 시 truncate, prompt 조립 시 truncate가 모두 걸린다.

### 발견 이슈
- 현재 즉시 운영 리스크:
  - 세션 문서 업로드와 메시지 전송 시 파일 추출이 동기 처리된다. 큰 PDF나 ODL 지연이 있으면 채팅 API 응답 자체가 오래 걸리거나 실패할 수 있다.
  - 세션 문서는 `ChatSession` 한 레코드에 하나만 유지된다. 같은 세션에서 새 문서를 붙이거나 기존 workspace 문서를 참조로 선택하면 이전 세션 문서 텍스트가 그대로 덮어써진다.
  - 세션 문서 저장과 메시지 저장이 같은 요청 안에서 commit된다. 첨부 추출은 성공했지만 task enqueue가 실패하면, 세션 참조 문서와 사용자 메시지만 남고 실제 답변 생성은 안 될 수 있다.
- 현재 확인된 품질/설계 이슈:
  - 세션 문서는 chunking 없이 단일 텍스트 item으로만 retrieval에 들어간다. 질문과 관련된 일부만 고르는 과정이 없어 긴 문서는 앞부분 위주로만 활용된다.
  - 세션 문서는 2중 truncate가 걸린다. 업로드 시 `SESSION_DOCUMENT_BODY_MAX / SESSION_DOCUMENT_TABLE_MAX`로 1차 축약되고, answer context 조립 시 `ANSWER_CONTEXT_SESSION_TEXT_MAX`로 다시 잘린다.
  - 세션 지식원은 score 1.0인 단일 item으로 들어간다. query relevance 계산 없이 platform/workspace 결과와 같은 정렬 단계에 섞여, 실제 관련도보다 앞쪽 텍스트만 반영될 수 있다.
- 구조적/확장 리스크:
  - 세션 문서가 별도 엔티티/파일/청크로 관리되지 않아, 향후 “문서 여러 개 첨부”, “세션 문서만 재검색”, “세션 문서 citation” 같은 기능 확장이 어렵다.
  - 현재 구조는 세션 문서를 payload 컨텍스트로 취급하므로 workspace/platform처럼 동일한 retrieval 품질 계약을 적용할 수 없다.

---

## 6. 전체 다운로드 플로우

### 사용자 흐름
- 전체 다운로드 요청
- export job 생성
- ZIP 비동기 생성
- 상태 조회
- 완료 후 다운로드

### 주요 진입점
- Frontend
  - 문서/워크스페이스 화면의 전체 다운로드 진입
- Backend
  - `/api/exports`
  - `/api/exports/latest`
  - `/api/exports/{job_id}`
  - `/api/exports/{job_id}/download`

### 주요 상태 / 자원
- ExportJob
- runtime/exports
- ZIP 임시 파일 / 최종 파일

### 비동기 / 외부 연동
- Celery export queue
- 파일 시스템 I/O

### 검토 메모
- export는 API에서 job row를 만들고, 실제 ZIP 생성은 Celery task가 수행하는 비동기 구조다.
- 동일 사용자/그룹에 대해 `PENDING/PROCESSING` 상태 job은 재사용한다.
- ZIP 생성은 runtime/exports 아래에 `export_{job.id}.tmp` → `export_{job.id}.zip` 순서로 원자적 교체한다.
- 문서 파일이 없으면 job 전체를 실패시키지 않고 `missing_files.txt`에 누락 목록을 남긴다.
- export task는 `export_queue`로 분리해 platform/RAG 계열 queue와 병목을 끊도록 정리했다.

### 발견 이슈
- 현재 즉시 운영 리스크:
  - job 생성 commit 후 `build_group_export.delay()`가 실패하면 `PENDING` job이 남고 실제 처리자는 없다.
  - 취소는 DB 상태를 `CANCELLED`로 먼저 바꾸고 task는 루프 중간에 이를 polling해 멈춘다. 이미 ZIP에 일부 파일이 들어간 상태일 수 있으며, 취소 시점에 따라 temp/final 파일 정리가 경합할 수 있다.
  - `cancel_job()`은 service 레벨에서 즉시 파일 삭제를 시도하고, task 쪽도 취소 예외에서 temp/final 파일 삭제를 수행한다. 현재는 idempotent에 가깝지만 파일 삭제 타이밍이 이중화돼 있다.
  - `get_group_documents_for_export()`는 ACTIVE와 DELETE_PENDING 문서를 모두 포함한다. 휴지통 문서 포함이 의도된 정책이지만, 사용자가 “전체 다운로드”를 active 문서만으로 기대하면 혼동될 수 있다.
- 구조적/확장 리스크:
  - 재사용 정책은 동일 사용자/그룹 기준이다. 같은 그룹에 대해 여러 사용자가 동시에 export를 걸면 별도 job이 각각 생성될 수 있다.
  - export는 파일 시스템 I/O와 ZIP 압축 시간이 길어질 수 있어, queue 분리 전에는 platform 작업과 강하게 병목됐다. 현재는 `export_queue`로 분리했지만 worker concurrency와 저장소 I/O는 계속 관찰이 필요하다.

---

## 7. 관리자·플랫폼 동기화 플로우

### 사용자 흐름
- 관리자 페이지 진입
- 통계/사용량 확인
- 플랫폼 source sync 실행
- 플랫폼 지식 반영 및 검색 반영

### 주요 진입점
- Frontend
  - `frontend/src/pages/Admin`
- Backend
  - `/api/admin/*`
  - platform sync task / precedent task

### 주요 상태 / 자원
- platform raw source
- platform document
- platform chunks
- sync run / failure 기록

### 비동기 / 외부 연동
- Korea Law Open API
- Celery platform queue
- Qdrant / BM25

### 검토 메모
- 관리자 화면에서 source_type별 sync 요청을 보내면 `PlatformSyncRun` row를 먼저 만들고, 이후 Celery `run_platform_source_sync` task를 enqueue한다.
- 실제 동기화는 페이지 단위 검색 → 아이템 단위 상세 fetch → normalize/index → 진행률 commit의 순서로 long-running task 안에서 수행된다.
- stop 요청은 `PlatformSyncRun.status=cancelled`로 먼저 전환하고, meta에 저장된 Celery task id가 있으면 revoke를 시도한다. 실제 sync 루프도 페이지/아이템 루프마다 cancelled 상태를 다시 확인한다.
- item 단위 실패는 `PlatformSyncFailure`에 누적 저장하고, sync 전체는 `queued / running / completed / failed / cancelled` 상태를 갖는다.
- 현재 `platform_queue`는 플랫폼 sync 외에 precedent 인덱싱/재처리, subscription reconcile도 함께 소비한다. 서버 워커는 `concurrency=1`이다.

### 발견 이슈
- 현재 즉시 운영 리스크:
  - `PlatformSyncRun` row commit 이후 `run_platform_source_sync.delay()`가 실패하면 run은 `queued`로 남고 실제 작업자는 없다. 현재 이를 주기적으로 재검사하는 sweep은 없다.
  - stop 요청은 cancelled 상태와 revoke를 함께 걸지만, 이미 진행 중인 외부 API 호출/normalize/index 한 건은 즉시 멈추지 않을 수 있다. 다음 cancelled 체크 전까지 일부 아이템이 더 처리될 수 있다.
  - long-running platform sync와 precedent 인덱싱, subscription reconcile이 같은 `platform_queue`를 공유한다. 현재 서버는 `platform_worker concurrency=1`이므로 대형 sync 1건이 다른 플랫폼 계열 작업을 모두 지연시킬 수 있다.
- 현재 확인된 품질/정책 이슈:
  - sync 중복 방지는 `source_type` 단위만 본다. 같은 source_type은 막지만 서로 다른 source_type sync는 동시에 queued될 수 있고, 실제 실행은 단일 워커에 직렬로 밀린다.
  - precedent는 migration flag에 따라 legacy corpus와 platform corpus 경로가 갈린다. 운영자가 현재 corpus 모드를 명확히 모르면 “동기화는 됐는데 검색 반영이 안 된다”는 혼선이 생길 수 있다.
- 구조적/확장 리스크:
  - 진행률 업데이트와 item 실패 기록이 매우 잦은 commit 기반이다. 대규모 sync에서 DB write 부하가 누적될 수 있다.
  - 플랫폼 sync, precedent 인덱싱, 구독 정리가 모두 platform 계열 큐에 묶여 있어, 향후 플랫폼 데이터량이 커지면 별도 queue/worker 분리가 필요할 가능성이 높다.

---

## 공통 점검 항목

각 플로우를 검토할 때 아래 항목을 공통으로 본다.

- 상태 전이가 원자적인가
- 동일 요청 중복 처리 가능성이 있는가
- 큐/워커 병목이 다른 플로우에 전이되는가
- runtime 파일 경합이 있는가
- Redis / DB / Qdrant 공유 자원 충돌이 있는가
- 실패 원인이 사용자에게 충분히 구분되어 보이는가
- 취소/재시도/복구 경로가 있는가

---

## 공통 구조 리뷰 축

플로우별 이슈 외에, 전체 코드베이스에서 반복적으로 봐야 할 구조 축을 따로 둔다.

### 1. 책임 분리
- Router는 입출력/권한 확인까지만 담당하는가
- Service는 비즈니스 규칙과 상태 전이만 담당하는가
- Repository는 조회/저장 추상화에 머무르는가
- Task는 장기 실행/비동기 작업만 담당하는가
- 한 클래스가 orchestration, 상태 변경, 외부 호출, 포맷팅을 동시에 떠안고 있지 않은가

### 2. Celery 큐 설계
- 긴 작업과 짧은 작업이 같은 큐를 공유하지 않는가
- 사용자 응답 경로(chat 등)와 운영 배치(platform sync 등)가 분리돼 있는가
- queue별 concurrency와 worker 수가 실제 업무 성격과 맞는가
- DB 상태 생성 후 enqueue 실패 시 복구 경로가 있는가

### 3. 공통 로직 모듈화
- 같은 상태 전이/검증/파일 정리/notification 로직이 여러 service에 흩어져 있지 않은가
- payload 조립, context build, chunking, lifecycle check 같은 공통 규칙이 한 곳에 모여 있는가
- 비슷한 로직이 여러 흐름에서 조금씩 다른 형태로 중복돼 있지 않은가

### 4. 코드 스타일 / 계약 일관성
- 상태값, lifecycle, queue 이름, error code가 한 규칙으로 관리되는가
- 예외 처리 방식이 service/task마다 들쭉날쭉하지 않은가
- 실패 원인이 단일 `FAILED`로 과도하게 합쳐지지 않는가
- timeout, top-k, truncate 같은 설정이 하드코딩이 아니라 settings로 모여 있는가

### 5. 운영 관리성
- runtime 산출물과 소스 코드가 분리돼 있는가
- 로그만으로 어느 단계가 병목/실패인지 식별 가능한가
- 관리자 기능과 사용자 기능이 같은 자원을 두고 충돌하지 않는가
- 재처리, 취소, 복구, cleanup 경로가 운영 관점에서 명확한가

---

## 공통 개선 후보

현재까지 플로우 리뷰를 바탕으로, 구조 관점에서 우선 검토할 후보를 정리한다.

1. enqueue 실패 복구 패턴 정리
- 업로드, 채팅, export, platform sync 모두 “DB 상태 생성 → Celery enqueue” 패턴이 있다.
- 공통적으로 stuck 상태를 감지/복구하는 sweep 또는 watchdog이 필요할 수 있다.

2. 큐 토폴로지 재정리
- export는 분리 완료
- platform sync / precedent / subscription은 여전히 같은 `platform_queue`
- chat / document / platform / export 각 큐의 성격과 concurrency를 다시 정의할 필요가 있다.

3. 세션 문서 처리 계약 정리
- 현재는 payload형 임시 컨텍스트로만 다뤄진다.
- session knowledge를 계속 유지할지, 별도 엔티티/청크/인덱스형으로 올릴지 결정이 필요하다.

4. 실패 원인 분리
- document `FAILED`, retrieval fallback, sync queued 고착 등은 운영상 원인 추적이 어렵다.
- 최소한 failure reason / stage를 공통 규칙으로 남기는 설계가 필요하다.

5. 공통 lifecycle / side effect 묶기
- approve/delete/restore/index/deindex/notify가 여러 서비스에 분산돼 있다.
- 상태 전이와 부수효과를 묶는 공통 orchestration 계층이 필요한지 검토한다.

---

## 공통 개선 후보 우선순위

우선순위 기준:
- 사용자 영향이 즉시 큰가
- 병목/고착이 다른 플로우로 전이되는가
- 공통 패턴이라 한 번 정리하면 여러 흐름에 동시에 효과가 있는가

### P1

1. enqueue 실패 복구 패턴 정리
- 이유:
  - 업로드, 채팅, export, platform sync에 공통으로 걸친다.
  - 현재는 `DB 상태 생성 → Celery enqueue` 후 실패 시 stuck 상태가 남는다.
  - 운영에서 가장 먼저 문제를 만드는 공통 패턴이다.
- 목표:
  - stuck `PENDING/queued/processing` 상태를 감지하는 sweep/watchdog 설계
  - enqueue 성공 여부와 상태 전이를 분리해서 추적

2. 큐 토폴로지 재정리
- 이유:
  - export는 분리했지만 platform 계열은 아직 long-running sync와 재인덱싱/구독 정리가 섞여 있다.
  - 병목이 즉시 사용자 체감과 운영 작업에 전이된다.
  - concurrency/queue 경계가 정리되지 않으면 이후 성능 이슈가 반복된다.
- 목표:
  - `platform_queue` 내부 작업 성격 재분류
  - long-running sync와 짧은 maintenance 성격 작업 분리 검토
  - queue별 concurrency 기준 정의

3. 실패 원인 분리
- 이유:
  - document `FAILED`, retrieval fallback, sync queued 고착이 모두 운영에서 추적이 어렵다.
  - 원인 가시성이 낮으면 병목/장애를 재현해도 개선 속도가 느리다.
- 목표:
  - failure reason / stage를 최소 공통 규칙으로 남기기
  - 로그/DB 상태만으로 어느 단계가 실패했는지 구분 가능하게 하기

### P2

4. 세션 문서 처리 계약 정리
- 이유:
  - 사용자 품질 이슈는 분명하지만, 현재는 payload형이라는 계약이 명확하다.
  - retrieval 품질 개선 효과는 크지만, 구조 변경 범위도 크다.
- 목표:
  - payload형 유지 vs 별도 엔티티/청크/인덱스형 전환 결정
  - session knowledge의 검색/인용 계약 재정의

5. 공통 lifecycle / side effect 묶기
- 이유:
  - approve/delete/restore/index/deindex/notify가 흩어져 있어 코드 일관성은 떨어진다.
  - 다만 지금 당장 장애를 일으키는 원인보다는 구조 정리 성격이 더 강하다.
- 목표:
  - 상태 전이와 부수효과를 묶는 orchestration 계층 필요 여부 판단
  - document/workspace lifecycle의 공통 패턴 정리

### 권장 진행 순서

1. enqueue 실패 복구 패턴
2. 큐 토폴로지 재정리
3. 실패 원인 분리
4. 세션 문서 처리 계약
5. 공통 lifecycle / side effect 묶기

---

## P1-1. enqueue 실패 복구 패턴 설계 초안

### 문제 정의

현재 여러 플로우가 아래 공통 패턴을 가진다.

1. DB 상태를 먼저 생성/변경한다.
2. 그 다음 Celery task를 enqueue한다.
3. enqueue 실패 시 DB 상태만 남고 실제 처리자는 없다.

이 패턴은 현재 최소 아래 흐름에 공통으로 존재한다.

- 문서 업로드 → `Document(PENDING)` 생성 후 `process_next_pending_document.delay()`
- 채팅 전송 → `ChatMessage(USER)` 저장 후 `process_chat_message.delay()`
- export 생성 → `ExportJob(PENDING)` 생성 후 `build_group_export.delay()`
- platform sync → `PlatformSyncRun(queued)` 생성 후 `run_platform_source_sync.delay()`

### 목표

- enqueue 실패 시 stuck 상태를 운영에서 감지할 수 있어야 한다.
- 자동 복구 또는 재기동 가능한 최소 경로가 있어야 한다.
- “DB 상태는 있는데 worker가 없다”는 상황을 명시적으로 구분해야 한다.

### 기본 원칙

1. DB 상태와 enqueue 성공 여부를 같은 의미로 취급하지 않는다.
2. `PENDING/queued`는 “작업 요청이 생성됨”이지 “worker가 실제 잡음”을 뜻하지 않는다.
3. 최소한 아래 2단계를 구분한다.
   - 요청 생성됨
   - task enqueue 확인됨

### 권장 공통 계약

#### A. 상태 외에 enqueue 메타를 남긴다

각 비동기 대상 엔티티에 가능하면 아래 메타를 둔다.

- `queue_name`
- `task_id` (enqueue 성공 시)
- `enqueued_at`
- `last_enqueue_error`
- `retry_count` 또는 `enqueue_attempts`

모든 엔티티에 컬럼을 바로 추가하기 어렵다면, 최소한 JSON metadata 또는 별도 audit/event 테이블로 남긴다.

#### B. API/service 레벨에서 enqueue 예외를 삼킨 채 성공 응답하지 않는다

현재는 일부 흐름이 “DB commit 성공 + enqueue 실패”여도 사용자에겐 성공처럼 보일 수 있다.

권장:
- enqueue 실패 시
  - API에선 명시적으로 에러 응답
  - 또는 DB 상태를 `enqueue_failed` 성격으로 남김

즉 `PENDING`과 `ENQUEUE_FAILED`를 운영상 구분 가능하게 한다.

#### C. watchdog / sweep task를 둔다

주기적으로 아래 대상을 점검하는 공통 sweep이 필요하다.

- 오래된 `PENDING/queued`
- `task_id is null` 인 비동기 엔티티
- `PROCESSING`인데 heartbeat/updated_at이 너무 오래된 엔티티

복구 방식:
- 재enqueue 가능하면 재enqueue
- 재enqueue 불가하면 `FAILED` 또는 `enqueue_failed`로 명시 전환
- 운영자 확인이 필요한 경우 failure reason 기록

### 흐름별 적용 방향

#### 1. 문서 업로드
- 현재:
  - Document/Approval commit 후 `process_next_pending_document.delay()`
- 권장:
  - upload 후 `document_queue_kick_requested_at` 또는 공통 enqueue audit 남김
  - 오래된 `PENDING` 문서를 sweep이 다시 깨우는 경로 추가

핵심:
- 문서는 개별 task_id보다 “queue kick” 성격이 강하므로,
  per-document task 추적보다 “오래된 PENDING 문서 감지 + queue re-kick”가 더 맞다.

#### 2. 채팅
- 현재:
  - USER 메시지 commit 후 `process_chat_message.delay()`
- 권장:
  - assistant 미생성 + active task 없음 + 최근 USER 메시지 존재 상태를 재처리 가능 대상으로 본다.

핵심:
- 채팅은 재enqueue 시 중복 assistant 생성 위험이 있으므로
  “세션 단위 active task 부재 + 마지막 메시지 처리 미완료” 조건을 엄격히 둬야 한다.

#### 3. export
- 현재:
  - ExportJob commit 후 `build_group_export.delay()`
- 권장:
  - `PENDING`이 일정 시간 이상 지속되고 `task_id`가 없으면 재enqueue 또는 `enqueue_failed`

핵심:
- export는 엔티티와 task가 1:1에 가까워서 가장 단순하게 복구 가능하다.

#### 4. platform sync
- 현재:
  - `PlatformSyncRun(queued)` commit 후 `run_platform_source_sync.delay()`
- 권장:
  - `queued`인데 `task_id`가 없거나 너무 오래 지속되면 재enqueue 또는 `failed`

핵심:
- 현재도 meta에 `task_id`를 기록하고 있어, 4개 플로우 중 가장 먼저 표준화 기준으로 삼기 좋다.

### 구현 우선순위 제안

1. export / platform sync부터 `task_id + enqueued_at + enqueue_failed` 계약 정리
- 엔티티와 task가 1:1이라 적용이 쉽다.

2. 문서 업로드는 “오래된 PENDING 감지 + queue re-kick” sweep 추가
- 개별 task 추적보다 queue kick 복구가 더 적합하다.

3. 채팅은 마지막
- 중복 assistant 답변 생성 방지가 추가로 필요하다.

### 최소 성공 기준

- 운영자가 “왜 이 작업이 안 움직이는지”를 DB/로그만 보고 구분할 수 있다.
- 일정 시간 이상 stuck 상태는 자동 복구되거나, 최소한 `enqueue_failed`로 표면화된다.
- 사용자에게는 “요청은 저장됐지만 실제 처리는 아직 시작되지 않았다”는 상태를 구분해 보여줄 수 있다.

---

## P1-2. 큐 토폴로지 재정리 초안

### 현재 상태

현재 라우팅 기준 큐는 아래 4개다.

- `chat_queue`
- `document_queue`
- `platform_queue`
- `export_queue`

하지만 실제 소비 구조는 환경별로 다르다.

#### 개발 환경
- `celery_worker` 1개가
  - `chat_queue, document_queue, platform_queue, export_queue`
  전부를 같이 소비한다.
- 즉 dev에서는 큐를 나눠도 실제 격리는 거의 없다.

#### 서버 환경
- `chat_worker` / `document_worker` / `platform_worker` / `export_worker`로 분리
- 다만 `platform_queue` 안에는 현재 아래 작업이 같이 있다.
  - platform sync
  - precedent 처리/인덱싱
  - subscription reconcile

### 문제 정의

현재 큐 분리의 핵심 문제는 두 가지다.

1. long-running 작업과 maintenance 작업이 같은 큐를 공유한다.
- 대표적으로 `platform_queue`
- 대형 sync 1건이 precedent 재처리나 subscription 정리를 막을 수 있다.

2. queue 이름은 분리돼도 실제 worker 격리와 concurrency 정책이 충분히 정의되지 않았다.
- dev에서는 모든 큐를 단일 worker가 소비
- 서버에서도 platform 계열은 여전히 한 worker, `concurrency=1`

### 큐 분리 원칙

큐는 “도메인 이름”보다 “실행 성격” 기준으로 나누는 것이 더 중요하다.

권장 원칙:

1. 사용자 응답 지연에 직접 영향 주는 작업
- chat
- 필요 시 가장 높은 우선순위

2. 문서 처리 파이프라인처럼 중간 길이 작업
- preview / extract / summarize / index / deindex

3. 운영 배치/동기화처럼 긴 작업
- platform sync

4. maintenance/cleanup 성격의 짧은 작업
- subscription reconcile
- expired export cleanup
- pending finalize 계열

즉 “기능”이 아니라
- interactive
- pipeline
- batch
- maintenance
관점으로 보는 것이 맞다.

### 현재 기준 권장 토폴로지

#### 유지
- `chat_queue`
- `document_queue`
- `export_queue`

#### 분리 검토
- `platform_queue`를 아래 둘 이상으로 분리 검토
  - `platform_sync_queue`
  - `maintenance_queue`

필요 시 precedent를 별도 분리:
  - `precedent_queue`

### 권장 배치

#### 최소 분리안
- `chat_queue`
- `document_queue`
- `export_queue`
- `platform_sync_queue`
- `maintenance_queue`

이때:
- `run_platform_source_sync` → `platform_sync_queue`
- `reconcile_subscriptions` → `maintenance_queue`
- `cleanup_expired_exports` / `finalize_pending_*` → `maintenance_queue`
- precedent 계열은 우선 `platform_sync_queue` 또는 `document_queue` 중 성격을 보고 선택

#### 강화 분리안
- `chat_queue`
- `document_queue`
- `export_queue`
- `platform_sync_queue`
- `precedent_queue`
- `maintenance_queue`

이 안은 플랫폼 데이터량이 커질 때 유리하지만, 운영 복잡도는 올라간다.

### precedent 작업 위치 판단

precedent 계열은 현재 애매하다.

- `process_next_pending_precedent`
- `index_precedent`
- `delete_precedent_index`

특성:
- 플랫폼 데이터 성격이지만
- 실제로는 chunk 생성 + embedding + vector/BM25 저장까지 포함한 pipeline형 작업이다.

판단 기준:
- precedent 등록/재처리가 관리자 운영 작업에 가깝다면 `platform_sync_queue`
- precedent 인덱싱이 검색 품질 유지용 상시 작업이라면 `precedent_queue` 또는 `document_queue` 성격

현재로서는 long-running sync와 묶지 않는 것이 우선이다.

### dev 환경 정책

dev에서 모든 큐를 한 worker가 먹는 현재 구조는 개발 편의상 이해는 되지만,
병목/우선순위 검증에는 도움이 안 된다.

권장:
- dev 기본은 단일 worker 유지 가능
- 다만 queue 병목 재현이 필요한 경우,
  최소한 `platform_sync_queue` 또는 `export_queue`는 별도 worker로 띄울 수 있는 override를 둔다.

### queue별 concurrency 기준 초안

- `chat_queue`
  - 낮은 작업 시간 / 사용자 응답 민감
  - concurrency 상대적으로 높게 가능

- `document_queue`
  - ODL/요약/인덱싱 포함
  - CPU/IO 부담 크므로 보수적으로

- `export_queue`
  - ZIP 생성 / 파일 I/O
  - concurrency 낮게 유지

- `platform_sync_queue`
  - 외부 API + normalize + index
  - concurrency 낮게 유지

- `maintenance_queue`
  - 짧고 자주 도는 작업
  - concurrency 낮아도 무방하나 long-running queue와 분리하는 것이 핵심

### 권장 적용 순서

1. `platform_queue`에서 `maintenance_queue` 분리
- 가장 대비 효과가 크고 범위가 작다.

2. `run_platform_source_sync`를 `platform_sync_queue`로 이동
- 긴 sync를 maintenance와 precedent에서 분리

3. precedent 계열 위치 재판단
- 데이터량/운영 빈도를 보고 `platform_sync_queue` 유지 vs `precedent_queue` 신설 결정

### 최소 성공 기준

- long-running platform sync가 subscription reconcile이나 cleanup 계열을 막지 않는다.
- export와 platform 병목이 분리된 것처럼, platform sync와 maintenance도 서로 전이되지 않는다.
- queue 이름만 분리된 것이 아니라, worker/concurrency 정책까지 함께 설명 가능해야 한다.

---

## P1-3. 실패 원인 분리 설계 초안

### 현재 상태

현재 실패 정보는 엔티티/플로우마다 형식이 다르다.

#### 문서 처리
- `Document.processing_status = FAILED`
- 부가 정보는 주로 `error_message` 또는 로그로만 남는다.
- extract/classify/summarize 어느 단계 실패인지 DB 상태만으로는 구분이 어렵다.

#### export
- `ExportJob.status = FAILED`
- `error_message`는 저장되지만, stage 개념은 없다.

#### platform sync
- `PlatformSyncRun.status`
- item 단위는 `PlatformSyncFailure(error_type, error_message, payload_snippet)`로 가장 잘 분리돼 있다.
- 현재 코드베이스에서 실패 분리의 가장 성숙한 형태다.

#### 채팅
- 사용자에게는 WS payload의 에러 코드로 전달될 수 있지만,
- 세션/메시지 단위 영속화된 failure stage는 거의 없다.
- retrieval 실패는 warning log만 남고 일반 답변으로 fallback된다.

### 문제 정의

현재는 “실패했다”는 사실은 남아도,
운영자가 아래를 빠르게 구분하기 어렵다.

- 어느 단계(stage)에서 실패했는가
- 어떤 분류(code)의 실패인가
- 자동 재시도 가능한가
- 사용자에게는 어떻게 보여줘야 하는가

즉 status만으로는 부족하고, status를 보조하는 공통 실패 메타가 필요하다.

### 기본 원칙

1. status enum은 크게 유지한다.
- `FAILED` 자체를 지나치게 세분화하지 않는다.
- 상태 폭증보다 failure metadata를 붙이는 것이 현실적이다.

2. 최소한 아래 3개는 분리한다.
- `failure_stage`
- `failure_code`
- `failure_message`

3. 운영자 관점과 사용자 관점을 분리한다.
- 운영자용: stage/code/message/snippet
- 사용자용: 안전한 에러 코드/메시지

4. retry 가능 여부를 판단할 수 있어야 한다.
- `enqueue_failed`
- `timeout`
- `external_api_failure`
- `normalize_error`
- `validation_error`
등은 재시도 가능성이 다르다.

### 권장 공통 계약

#### A. 공통 필드

실패가 저장되는 엔티티에는 가능하면 아래 메타를 남긴다.

- `failure_stage`
  - 예: `preview`, `extract`, `classify`, `summarize`, `enqueue`, `retrieve`, `stream`, `zip`, `platform_fetch`, `platform_normalize`, `platform_index`

- `failure_code`
  - 예: `timeout`, `external_api_error`, `normalize_error`, `index_error`, `enqueue_failed`, `permission_error`
  - 가능하면 `ErrorCode`와 직접 연결되거나 맵핑 가능해야 한다.

- `failure_message`
  - 내부용 상세 메시지

- `failed_at`
  - 이미 `updated_at`가 있더라도 실패 시점을 명시하면 운영 추적이 쉽다.

별도 컬럼이 부담되면 metadata JSON으로 먼저 시작해도 된다.

#### A-1. 현재 모델 제약 기준 현실적인 저장 위치

현재 엔티티를 보면:

- `Document`
  - `error_message` 없음
  - `metadata_json`도 없음
- `ExportJob`
  - `error_message`만 있음
  - `metadata_json` 없음
- `ChatSession`
  - reference 필드만 있음
  - failure metadata용 필드 없음
- `PlatformSyncRun`
  - `metadata_json` 있음
- `PlatformSyncFailure`
  - `error_type`, `error_message` 있음

즉 바로 적용 가능한 수준이 다르다.

#### A-2. 최소 변경안

최소 변경안은 “새 엔티티를 만들지 않고, 기존 엔티티에 필요한 최소 컬럼/메타만 추가”하는 방식이다.

- `Document`
  - `error_message`
  - `failure_stage`
  - `failure_code`

- `ExportJob`
  - `failure_stage`
  - `failure_code`

- `ChatSession` 또는 `ChatMessage`
  - 별도 영속화는 나중으로 미루고
  - 우선 로그 + Redis status payload에 `failure_stage/failure_code` 반영

- `PlatformSyncRun`
  - 지금 구조 유지
  - `metadata_json`에 stage summary를 더 명시

장점:
- 가장 빠르게 적용 가능
- 운영 가시성이 즉시 올라감

단점:
- 채팅처럼 “요청 단위” failure 추적은 여전히 약함
- 엔티티마다 컬럼 구성이 완전히 같진 않음

#### A-3. 확장안

확장안은 공통 failure event/audit 테이블을 두는 방식이다.

예:
- `async_failures`
  - `flow_type`
  - `entity_type`
  - `entity_id`
  - `stage`
  - `code`
  - `message`
  - `retryable`
  - `payload_snippet`
  - `created_at`

장점:
- 문서/export/chat/platform을 한 화면에서 동일 규칙으로 조회 가능
- 운영 도구/관리자 화면 확장에 유리

단점:
- DB/조회/UI 범위가 커짐
- 지금 단계에서는 과할 수 있음

#### B. status와 failure metadata의 관계

- status는 high-level
  - `PENDING / PROCESSING / DONE / FAILED`
- failure metadata는 low-level
  - `FAILED + stage=extract + code=timeout`

즉 “상태는 단순하게, 원인은 풍부하게”가 원칙이다.

### 흐름별 적용 방향

#### 1. 문서 처리

최소 stage:
- `preview`
- `extract`
- `classify`
- `summarize`
- `index_enqueue`

권장:
- `Document.error_message`만 쓰지 말고 `failure_stage`, `failure_code`를 같이 남긴다.
- `summary_process.py`에서 모든 예외를 `FAILED`로 합치더라도, stage만이라도 보존해야 한다.

#### 2. export

최소 stage:
- `enqueue`
- `zip_prepare`
- `zip_write`
- `finalize`
- `cleanup`

권장:
- 현재 `error_message` 외에 `failure_stage` 추가
- export는 1:1 job 구조라 가장 먼저 적용하기 쉽다.

#### 3. platform sync

현재 가장 잘 돼 있다.

유지 방향:
- `error_type`를 공통 failure_code 사전과 맞춘다.
- `fetch_error / normalize_error / index_error`를 다른 플로우와도 비교 가능한 naming으로 정리한다.

즉 platform을 기준 모델로 삼는 것이 좋다.

#### 4. 채팅

최소 stage:
- `enqueue`
- `retrieve`
- `generate`
- `stream`
- `save_assistant`

권장:
- retrieval 실패가 warning만 남고 일반 답변으로 fallback되는 경우,
  사용자 메시지에는 “fallback 답변”임을 알리는 표식이 필요할 수 있다.
- 최소한 운영 로그/세션 metadata에는 retrieval failure 여부를 남긴다.

### ErrorCode와의 관계

현재 `errors/error_codes.py`는 사용자 응답용 코드 체계로 이미 잘 정리돼 있다.

권장:
- `failure_code`는 `ErrorCode.code`와 직접 같을 필요는 없지만,
  최소한 아래 둘 중 하나를 만족해야 한다.
  - `ErrorCode`를 그대로 저장
  - 내부 failure_code → `ErrorCode` 맵핑 테이블 제공

즉 운영 코드와 사용자 코드가 완전히 따로 놀지 않게 해야 한다.

### 권장 적용 순서

1. export
- 엔티티가 단순하고 효과가 바로 보인다.

2. 문서 처리
- 현재 `FAILED` 뭉개짐이 가장 큰 운영 pain point다.

3. platform sync naming 정리
- 이미 구조가 있으므로 공통 규칙과 맞추기 쉽다.

4. 채팅
- 영속화 지점을 먼저 정해야 한다.

### 최소 성공 기준

- 운영자가 DB/로그만 보고 “어느 stage에서 왜 실패했는지”를 구분할 수 있다.
- retry 가능/불가능 판단이 가능하다.
- status enum을 과도하게 늘리지 않고도 실패 원인 분석이 가능하다.

## 정규화 관점 점검

### 목적

- 공통 구조는 공통 계약으로 묶고
- source of truth가 둘 이상인 필드는 줄이고
- 반대로 운영상 필요한 의도적 비정규화는 유지한다.

### 1. 바로 묶을 수 있는 것

#### A. failure metadata 계약

현재:
- `Document`: 구조화된 failure 필드 없음
- `ExportJob`: `error_message`만 있음
- `Precedent`: `error_message`만 있음
- `PlatformSyncFailure`: `error_type + error_message`

권장:
- async/job 성격 엔티티는 공통적으로 아래 계약을 맞춘다.
  - `failure_stage`
  - `failure_code`
  - `error_message`

이유:
- 상태값은 유지하고, 실패 원인만 공통 포맷으로 묶는 것이 가장 실용적이다.
- 별도 failure table까지 가지 않아도 운영 가시성이 바로 올라간다.

#### B. 분류 결과 source of truth

현재:
- `Document.document_type`, `Document.category`가 주 source of truth
- 일부 보조 데이터가 `Summary.metadata_json`에도 중복 기록될 수 있음

권장:
- 분류 결과의 source of truth는 `Document`로 고정
- `Summary.metadata_json`에는 구조 보조 정보만 남기고
  `document_type/category` 중복 기록은 점진적으로 제거 검토

이유:
- 현재도 PDF export/문서 응답은 `Document` 값을 기준으로 읽는다.
- 분류 기준이 둘로 보이면 이후 수정/재분류 시 불일치 위험이 생긴다.

### 2. 묶을 수는 있지만 지금은 과한 것

#### A. created_at / updated_at / status 공통화

현재:
- 거의 모든 엔티티에 `created_at`, `updated_at`
- 일부 엔티티에 `status`, `started_at`, `finished_at`

판단:
- DB를 더 정규화해서 별도 테이블로 뺄 대상은 아니다.
- 대신 ORM mixin이나 naming contract로 통일하는 정도가 적절하다.

이유:
- 이런 필드는 조회 성능과 단순성이 더 중요하다.
- 별도 테이블로 분리하면 조인만 늘고 실익이 작다.

#### B. lifecycle / deletion 메타

현재:
- `Group`, `Document`에
  - `status/lifecycle_status`
  - `delete_requested_at`
  - `delete_scheduled_at`
  - `deleted_at`

판단:
- 패턴은 비슷하지만 의미가 완전히 같지 않다.
- 공통 삭제 테이블로 빼기보다 현 구조 유지가 낫다.

이유:
- 그룹 삭제와 문서 삭제는 후속 effect가 다르다.
- 지금은 공통 서비스/헬퍼로 로직을 묶는 것이 더 효과적이다.

### 3. 유지하는 것이 맞는 비정규화

#### A. ChatSession의 reference 필드

현재:
- `reference_document_title`
- `reference_document_text`
- `reference_group_id`

판단:
- 정규화만 보면 별도 `session_attachments` 테이블로 뺄 수 있다.
- 하지만 현재는 “세션 단위 임시 컨텍스트”라는 의미가 명확해서
  우선 유지가 맞다.

주의:
- 다만 세션 문서 retrieval을 개선하려면 장기적으로
  `session_attachments` 또는 `session_knowledge_items` 같은 구조를 검토할 수 있다.

#### B. ExportJob의 파일 집계 필드

현재:
- `total_file_count`
- `exported_file_count`
- `missing_file_count`

판단:
- 별도 detail row로 정규화할 수는 있다.
- 하지만 현재 UI가 이 요약 수치를 바로 쓰고 있어
  현 구조 유지가 낫다.

이유:
- 집계 필드는 조회용 read model 성격이 강하다.
- export detail table을 따로 만들 실익이 아직 크지 않다.

### 4. 현재 가장 약한 컬럼 후보

#### ExportJob.requester_role

현재:
- job 생성 시 snapshot처럼 저장
- 이후 분기/UI/운영 조회에서 직접 사용하는 경로는 현재 뚜렷하지 않다.

판단:
- 실패 메타 컬럼을 넣을 때 “무엇을 줄일 수 있나”를 본다면
  가장 먼저 재검토할 후보는 이것이다.

주의:
- 단, 감사/정책상 “요청 시점 권한”을 남겨야 한다면 유지해야 한다.
- 즉 이 컬럼은 기술적 필요보다 운영 정책 기준으로 판단해야 한다.

### 결론

- 지금 구조에서 가장 가치 있는 정규화는
  “별도 테이블 분해”가 아니라
  “source of truth와 공통 failure 계약 정리”다.
- 즉 우선순위는 아래 순서가 맞다.
  1. failure metadata 공통화
  2. 분류 결과 source of truth 단일화
  3. 저활용 snapshot 컬럼 재검토
  4. 큰 구조 분해는 나중

## 무결성 우선 모델 정리

전제:
- 이번 기준은 “테이블 수 감소”가 아니라 “코드/데이터 무결성 우선”이다.
- 즉 같은 의미를 두 군데 저장하지 않고, legacy 경로를 병행 유지하지 않으며, source of truth를 하나만 남기는 방향을 우선한다.

### 1. 유지할 것

#### A. `documents`

역할:
- 원본 문서와 현재 상태의 source of truth

유지 이유:
- `document_type`, `category`, `processing_status`, `lifecycle_status`는 현재 서비스의 핵심 기준값이다.
- preview/processing/delete lifecycle도 문서 aggregate 안에 두는 것이 가장 명확하다.

원칙:
- 분류 결과는 `documents.document_type`, `documents.category`만 기준으로 본다.
- 다른 테이블이나 metadata에는 같은 의미를 source of truth로 다시 저장하지 않는다.

#### B. `document_approvals`

역할:
- 문서 검토/승인 도메인

유지 이유:
- 승인 상태는 문서 본체와 의미가 다르다.
- summary처럼 재생성 가능한 산출물이 아니라, 업무 상태이자 감사/담당자 흐름과 연결될 수 있다.
- 무결성 우선 기준에서는 `documents`로 흡수하기보다 분리 유지가 더 자연스럽다.

#### C. `summaries`

역할:
- 문서 요약/핵심 포인트라는 파생 산출물

유지 이유:
- summary는 문서 본체와 분리된 파생 결과다.
- 재생성 가능 자산이며, 원본 문서와 lifecycle이 다를 수 있다.
- 무결성 기준에서는 `documents`에 흡수하기보다 별도 산출물로 유지하는 편이 더 정합적이다.

원칙:
- `metadata_json`는 요약/구조 보조 정보만 저장한다.
- `document_type`, `category` 같은 분류 기준값은 저장/참조하지 않는다.

#### D. `platform_documents`, `platform_document_chunks`, `platform_sync_runs`, `platform_sync_failures`

역할:
- 플랫폼 지식 corpus와 동기화 이력의 source of truth

유지 이유:
- 플랫폼 지식과 sync 이력을 구조적으로 분리한 현재 방향이 맞다.
- 특히 `platform_sync_runs`와 `platform_sync_failures`는 운영 이력의 무결성을 위해 별도 유지하는 편이 낫다.

### 2. 통합할 것

#### A. 판례 source of truth를 `platform_documents(source_type='precedent')`로 통합

현재 문제:
- precedent가 legacy `precedents` 테이블 / precedent corpus / platform corpus에 동시에 걸쳐 있다.
- `ENABLE_PLATFORM_PRECEDENT_CORPUS` flag와 precedent 전용 task/BM25/Qdrant 경로가 병행되어 있다.

통합 방향:
- 판례의 유일 source of truth는 `platform_documents(source_type='precedent')`로 고정한다.
- 검색/인덱싱/read path도 platform corpus 하나로 수렴한다.

이유:
- 같은 지식원을 두 corpus로 병행 유지하는 것은 무결성 관점에서 가장 위험하다.
- migration flag가 오래 남을수록 “동기화는 됐는데 검색이 안 된다” 같은 운영 혼선을 만든다.

#### B. 분류 결과 source of truth를 `documents`로 통합

현재 문제:
- `summaries.metadata_json`에 과거 분류 흔적이 남아 있을 수 있다.
- 일부 주석/테스트에서도 “보조 기록”이라는 legacy 표현이 존재한다.

통합 방향:
- `document_type`, `category`는 `documents`만 기준으로 본다.
- export/API/UI/docs/tests 전부 동일 기준으로 정리한다.

### 3. 장기 제거할 것

#### A. `precedents`

제거 이유:
- platform precedent corpus가 source of truth로 확정되면 legacy `precedents`는 중복 저장소가 된다.
- 현재 구조에서는 가장 큰 legacy aggregate다.

제거 전 조건:
- precedent read path가 platform corpus로 완전히 전환되어야 한다.
- precedent 전용 BM25/Qdrant namespace가 더 이상 사용되지 않아야 한다.
- admin/statistics/test가 platform precedent 기준으로 맞춰져야 한다.

#### B. precedent 전용 task / chunk builder / retrieval 경로

대상:
- `domains.platform_sync.precedent_task`
- `domains.precedent.chunk_builder`
- precedent 전용 BM25/Qdrant path
- precedent grouping/retrieval 유틸
- `ENABLE_PLATFORM_PRECEDENT_CORPUS` flag

제거 이유:
- precedent를 platform corpus로 통합한 뒤에도 남아 있으면 다시 dual path가 된다.
- 무결성 우선 기준에서는 migration 완료 후 반드시 제거해야 할 잔존 경로다.

### 4. 조건부 재검토할 것

#### A. `ExportJob.requester_role`

판단:
- 현재 가장 약한 snapshot 컬럼 후보다.
- 다만 요청 시점 권한 보존이 감사/운영 정책상 필요하면 유지해야 한다.

원칙:
- 기술적 convenience만으로 유지하지 않는다.
- 정책상 필요성이 없으면 제거 후보로 본다.

### 5. 즉시 정리 가능한 legacy 흔적

#### A. summary metadata의 분류 의미 제거

정리 내용:
- `Summary.metadata_json`에서 `document_type`, `category`를 더 이상 저장/참조하지 않는다.
- 주석/문서/테스트에서 “summary metadata 분류값은 보조 기록”이라는 표현을 넘어, “분류 source of truth는 documents뿐”으로 통일한다.

#### B. precedent 중심 naming 정리

현재 흔적:
- `QDRANT_COLLECTION=precedents`
- precedent 중심 용어가 일부 docs/tests/util에 남아 있음

정리 내용:
- 신규 설계와 문서에서는 `platform corpus`를 기준 용어로 사용한다.
- legacy precedent 경로는 명시적으로 `legacy precedent corpus`로 표기한다.

### 결론

- 무결성 우선 기준에서 가장 먼저 정리해야 할 것은 “판례 legacy 이중 경로”다.
- 그 다음은 “분류 source of truth 단일화”다.
- 즉 현재 우선순위는 아래와 같다.
  1. precedent source of truth를 platform corpus로 통합
  2. `documents.document_type/category`를 유일 기준으로 확정
  3. summary metadata의 legacy 분류 흔적 제거
  4. precedent legacy task/corpus/flag를 장기 제거 대상으로 확정

## 플랫폼 지식 모델 구조 점검

질문:
- 플랫폼 지식은 테이블이 많은가?
- 하나로 축소할 수 있는가?

결론:
- 현재 플랫폼 지식 핵심 테이블은 5개다.
  - `platform_raw_sources`
  - `platform_documents`
  - `platform_document_chunks`
  - `platform_sync_runs`
  - `platform_sync_failures`
- “하나의 테이블”로 축소하는 것은 무결성 기준에서 맞지 않는다.
- 다만 “어디까지 축소할 수 있나”로 보면, 현실적인 최소 구조는 **3~4개**다.

### 1. 왜 하나로 못 줄이나

#### A. raw / normalized / chunk는 역할이 다르다

- `platform_raw_sources`
  - 공공 API 원본 응답 보관
  - 재정규화 / 재색인 / 출처 검증 용도
- `platform_documents`
  - 서비스가 실제로 다루는 공통 문서 단위
- `platform_document_chunks`
  - BM25 / Qdrant 적재 기준인 검색용 산출물

판단:
- 이 셋을 하나로 합치면
  - 원본 보존
  - 서비스 문서
  - 검색용 chunk
  가 같은 레코드에 섞인다.
- 무결성 기준에서는 분리 유지가 맞다.

#### B. sync 실행 이력과 도메인 데이터는 분리하는 게 맞다

- `platform_sync_runs`
  - source_type별 동기화 실행 단위
- `platform_sync_failures`
  - item 단위 실패 상세

판단:
- `platform_documents`와 `platform_sync_runs`를 합치면
  문서 상태와 실행 이력이 섞인다.
- 이건 무결성 측면에서 오히려 퇴보다.

### 2. 어디까지는 줄일 수 있나

#### A. `platform_sync_failures`는 축소 검토 가능

현재:
- item 단위 실패를 row로 보관한다.
- admin/service/test가 이 테이블을 직접 읽는다.

축소 방향:
- 상세 실패 row가 정말 필요 없다면
  `platform_sync_runs.metadata_json` 또는 별도 `failure_summary_json`으로 흡수 가능하다.

장점:
- 테이블 수 1개 감소

단점:
- 개별 external_id/title/error_type 단위 조회가 약해진다.
- admin에서 최근 실패 목록 조회 기능이 약해진다.

판단:
- 무결성 우선 기준에서는 **지금 바로 줄일 이유가 약하다.**
- 운영 관찰성과 디버깅 가치가 크기 때문이다.

#### B. `platform_raw_sources`는 정책에 따라 축소 검토 가능

현재:
- raw payload를 별도 보관한다.

축소 방향:
- “원본 장기 보관이 필요 없다”는 정책이면 제거 가능성은 있다.

장점:
- 저장 공간 / 테이블 수 감소

단점:
- 재정규화 / 재색인 / 원본 검증 / provider 응답 비교가 어려워진다.

판단:
- 무결성 우선 기준에서는 **유지하는 편이 맞다.**
- 특히 precedent/interpretation/admin_rule처럼 provider payload 구조가 자주 엇갈릴 수 있어서 raw layer는 가치가 있다.

### 3. 그래서 플랫폼 지식은 몇 개가 적정한가

무결성 우선 기준 적정선:

#### 권장안
- `platform_raw_sources`
- `platform_documents`
- `platform_document_chunks`
- `platform_sync_runs`
- `platform_sync_failures`

즉 현재 5개 구조는 **많아 보이지만, 역할 분리 자체는 과하지 않다.**

#### 최소 축소안
- `platform_raw_sources`
- `platform_documents`
- `platform_document_chunks`
- `platform_sync_runs`

조건:
- `platform_sync_failures`를 `platform_sync_runs`로 흡수

이건 가능하지만, 운영 가시성이 줄어드는 trade-off가 있다.

### 4. 플랫폼 지식과 관련된 진짜 legacy 문제

플랫폼 지식 테이블 수 자체보다 더 큰 문제는 아래다.

#### A. precedent source of truth가 둘이다

- legacy: `precedents` + precedent corpus
- target: `platform_documents(source_type='precedent')`

판단:
- 이게 플랫폼 지식 설계의 핵심 문제다.
- 테이블 수보다 먼저 해결해야 한다.

#### B. platform corpus와 legacy precedent corpus가 병행된다

- `ENABLE_PLATFORM_PRECEDENT_CORPUS` flag
- precedent 전용 task / chunk builder / BM25 / Qdrant path

판단:
- 플랫폼 지식 설계의 레거시는 “플랫폼 테이블이 많다”가 아니라
  “판례만 예외 경로가 아직 남아 있다”는 점이다.

### 결론

- 플랫폼 지식은 현재 5개 테이블이지만, 무결성 기준에서 과한 분해는 아니다.
- 하나의 테이블로 줄이는 방향은 맞지 않는다.
- 실질적인 축소 후보는 `platform_sync_failures` 하나 정도다.
- 그러나 플랫폼 지식에서 더 먼저 해결해야 할 문제는
  **테이블 수가 아니라 precedent legacy dual path 제거**다.
