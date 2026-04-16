# Backend Architecture — Document Pipeline & Chat Knowledge Flow

> 작성 기준: 문서 분류 + normalized cache + 승인 인덱싱 정합화 완료 시점
> 대상 독자: 신규 합류 개발자, 구조 파악이 필요한 팀원

---

## 1. Document Pipeline

PDF 업로드부터 분류/요약/인덱싱까지의 흐름.

```
PDF 파일
  │
  ▼
DocumentSchemaResolver.get_or_create()    domains/document/document_schema_resolver.py
  - normalized cache(runtime/normalized_documents/{id}.json)를 먼저 확인
  - cache hit: ExtractedDocument 생략, DocumentSchema 직접 반환
  - cache miss: ExtractService → NormalizeService 호출 후 저장
  - 반환: DocumentSchema (source of truth)
  │
  ▼
DocumentClassificationService             domains/document/classification_service.py
  - title + body_text(최대 3000자) → LLM 단일 호출
  - 반환: {document_type, category}
  - 허용값 외 응답 및 LLM 오류 → "미분류" fallback (파이프라인 중단 없음)
  │
  ▼
Document.document_type                    domains/document/repository.py
Document.category                         update_classification() → DB commit
  (source of truth)
  │
  ▼
DocumentSummaryPayloadService             domains/document/summary_payload.py
  - [본문]/[표] LLM 입력 문자열 조립
  │
  ▼
LLMService.summarize()                    domains/document/summary_llm_service.py
  - summary_text, key_points 생성
  - document_type는 추출하지 않음 (분류는 별도 단계에서 완료)
  │
  ▼
SummaryRepository.create_summary()
  - summary_text, key_points 저장
  - metadata: {"source": "group_document_summary"} (보조 기록)
  │
  ▼
processing_status = DONE → approval 상태 확인
  - APPROVED 이면 index_approved_document.delay() 호출
  - 미승인이면 스킵 (approve_document() 쪽에서 enqueue)
  │
  ▼
DONE
```

### 분류 허용값

| 필드 | 허용값 |
|---|---|
| `document_type` | 계약서, 신청서, 준비서면, 의견서, 내용증명, 소장, 고소장, 기타, 미분류 |
| `category` | 민사, 계약, 회사, 행정, 형사, 노동, 기타, 미분류 |

### source of truth 원칙

- `document_type`, `category` → `Document` 모델이 유일한 source of truth
- summary metadata는 보조 기록 전용이며, 어떤 화면/서비스도 분류 기준으로 읽지 않는다
- PDF 생성, 목록/상세 응답, 운영 조회 전부 `Document.document_type` / `Document.category` 직접 참조
- **DocumentSchema는 처리 중간 산출물이다. 오직 `Document` 모델만이 source of truth다.**

### 핵심 계약

| 타입 | 위치 | 역할 |
|---|---|---|
| `ExtractedDocument` | `domains/document/extract_service.py` | 추출기 원본 (raw) |
| `DocumentSchema` | `domains/document/document_schema.py` | 정규화된 공통 소비 계약 |
| `DocumentTableBlock` | `domains/document/document_schema.py` | 표 단위 객체 |
| `DocumentPage` | `domains/document/document_schema.py` | 페이지 단위 (v1: 전체 = 1페이지) |

---

## 2. 승인 후 RAG 인덱싱

승인(APPROVE) 전에는 RAG 인덱싱을 수행하지 않는다.
승인 시점 또는 process 완료 시점에 `index_approved_document` Celery task가 호출된다.

**인덱싱 enqueue 시점 규칙:**

| 시나리오 | 인덱싱 enqueue 시점 |
|---|---|
| 일반 승인 (처리 완료 후 승인) | `approve_document()` 시점 — processing_status==DONE 확인 후 |
| 조기 승인 (승인 후 시간이 지나 처리 완료) | `process_file()` 완료 시점 — APPROVED 확인 후 |
| auto-approved 업로드 (OWNER/ADMIN) | 동일: `process_file()` 완료 시점에 APPROVED 확인 후 |

```
[approve_document() 경로 — processing_status==DONE 일 때]
DocumentReviewService.approve_document()
  │
  ├─ DocumentApproval.status = APPROVED → DB commit
  │
  └─ doc.processing_status == DONE
       └─▶ index_approved_document.delay(doc.id)

[process_file() 완료 경로 — auto-approved / 조기 승인 포함]
ProcessService.process_file()
  │
  ├─ processing_status = DONE → DB commit
  │
  └─ approval.status == APPROVED 확인
       └─▶ index_approved_document.delay(document_id)

[index task]
index_approved_document.delay(document_id)    domains/document/index_task.py
  │
  ├─ lifecycle_status / group_status stale 확인
  ├─ approval.status == APPROVED 재확인 (guard)
  │
  ▼
index_group_document()    domains/rag/group_document_indexing_service.py
  - DocumentSchemaResolver.get_or_create() → DocumentSchema(cache)
  - document.document_type / document.category → 각 chunk payload에 포함
  - Qdrant + BM25 저장
```

### chunk payload 계약

| 필드 | 설명 |
|---|---|
| `chunk_id` | `gdoc:{document_id}:chunk:{order_index}` |
| `document_id` | 그룹핑 기준 |
| `group_id` | 권한/검색 범위 필터 |
| `file_name` | citation / 카드 표시용 |
| `source_type` | `"pdf"` |
| `chunk_type` | `"body"` \| `"table"` |
| `document_type` | `Document.document_type` 값 (metadata) |
| `category` | `Document.category` 값 (metadata) |

`document_type` / `category`는 현재 chunk payload metadata로 저장된다.
인덱싱 시점에는 반드시 DB에 저장된 값이어야 하므로,
process_file 완료 후 enqueue하는 구조가 stale metadata 인덱싱을 방지한다.

### group document chunking 전략

현재 그룹 문서 chunking은 아래 우선순위를 따른다.

| 전략 | 설명 |
|---|---|
| `section` | `DocumentSchema.sections` 기반. heading을 `section_title` anchor로 사용하고, 같은 섹션 문단을 병합하며 표는 별도 chunk로 분리 |
| `page` | `DocumentPage` 기반. 실제 page 정보가 있을 때만 사용하고, page별 body/table chunk를 생성 |
| `text` | `body_text` 문단/길이 기반 fallback |

선택 규칙:
- `DOCUMENT_CHUNK_STRATEGY=auto` 이면 `section → page → text` 순으로 시도
- `section` 강제 시에도 `sections=[]` 이면 `text`로 downgrade
- `page` 강제 시에도 `pages`가 없거나 전부 `estimated=True` 이면 `text`로 downgrade

현재 `NormalizeService._build_pages()`는 v1 단순화 구현이라, page 전략은 **실제 page 정보가 들어온 문서에서만** 의미가 있다.

---

## 3. 분류 수동 수정

운영 중 미분류 문서나 잘못 분류된 문서를 수정하는 경로.

```
PATCH /groups/{group_id}/documents/{doc_id}/classification
  - OWNER / ADMIN 권한 필요
  - 허용값 외 입력 → 422 (Pydantic Literal 검증)

  DocumentService.update_classification()
    - Document.document_type / Document.category 업데이트 → commit
    - approval.status == APPROVED 이면 index_approved_document.delay() 호출
      → Qdrant payload 재동기화
```

미분류 문서 목록 조회:
```
GET /groups/{group_id}/documents/unclassified
  - document_type IS NULL 또는 "미분류"
  - category IS NULL 또는 "미분류"
  - ADMIN 이상 권한
```

---

## 4. Chat Knowledge Flow

챗봇 답변 생성 시 지식원 검색과 context 조립 흐름.

```
사용자 메시지
  │
  ▼
ChatProcessor.process_chat()     domains/chat/processor.py
  │
  ├─ KnowledgeRetrievalRequest 생성
  │    include_platform=True (항상)
  │    include_workspace=bool(workspace_selection)
  │    include_session=bool(reference_document_text)
  │
  ▼
KnowledgeRetrievalService        domains/knowledge/knowledge_retrieval_service.py
  │  (sort → dedupe → 반환)
  │
  ├──▶ PlatformKnowledgeRetriever    platform/  판례 RAG (항상 호출)
  │      retrieve_precedents() → RetrievedKnowledgeItem[]
  │
  ├──▶ WorkspaceKnowledgeRetriever   workspace/ 그룹 문서 RAG (선택형)
  │      retrieve_group_documents()  mode="all" | mode="documents"(whitelist)
  │      → RetrievedKnowledgeItem[]
  │
  └──▶ SessionDocumentRetriever      session/   임시 첨부 문서 (있을 때만)
         reference_document_text → RetrievedKnowledgeItem (score=1.0)
  │
  ▼
AnswerContextBuilder.build()     domains/knowledge/answer_context_builder.py
  - [플랫폼 지식] / [워크스페이스 문서] / [임시 문서] 블록 조립
  - source별 top-k 및 텍스트 길이 제한
  │
  ▼
system_content += rag_context
  │
  ▼
LLMClient.stream_chat()          스트리밍 답변 생성
```

---

## 5. Workspace Selection Flow

사용자가 특정 그룹 문서를 선택해 검색 범위를 지정하는 흐름.

```
POST /chat/sessions/{id}/messages
  Form: workspace_selection_json={"mode":"all","document_ids":[]}
        group_id=5
  │
  ▼
workspace_selection_parser.parse_workspace_selection()
  - JSON 파싱 + validation
  - mode="documents" + empty ids → 422 (fail-closed)
  │
  ▼
ChatService.send_message()
  - workspace_selection is not None → _require_group_membership() 검증
    - group ACTIVE + user ACTIVE 멤버십 확인
    - 실패 시 GROUP_NOT_FOUND / AUTH_FORBIDDEN
  - task payload에 group_id, workspace_selection dict 포함
  │
  ▼
Celery task: process_chat_message(payload)
  - WorkspaceSelection 복원
  │
  ▼
ChatProcessor.process_chat(group_id, workspace_selection)
  - include_workspace = workspace_selection is not None
  │
  ▼
WorkspaceKnowledgeRetriever.retrieve()
  mode="all"       → retrieve_group_documents(document_ids=None)
  mode="documents" → retrieve_group_documents(document_ids=[...])
                     BM25: group ∩ document_ids whitelist
                     Qdrant: MatchAny(document_ids) 필터
                     Python 재검증: whitelist 밖 chunk 제거 (이중 보장)
```

---

## 6. 현재 제약 및 다음 과제

| 항목 | 현재 상태 | 다음 과제 |
|---|---|---|
| `pages` 분리 | v1: 전체 문서 = 1페이지로 단순화 | ODL page 정보 실제 분리 |
| group document chunking | `section → page → text` 전략 계층 + env override 지원 | 실제 page-aware 품질 개선 및 section heuristics 고도화 |
| 분류 수정 이력 | 1차 미구현 | 2차에서 수정 이력 저장 검토 |
| 검색 boost | chunk payload에 분류값 저장 완료 | 질문 측 category 근거 설계 후 연결 예정 |
| workspace `mode="documents"` | 지원 (BM25 + Qdrant whitelist) | folder/category 확장 가능 |
| session retrieval | 단일 텍스트 블록 반환 | 긴 문서 분할 후 top chunk 반환 |
| LangChain | 미도입 | core contract는 완성됨, adapter 검토 가능 |
| reranker | 미도입 | KnowledgeRetrievalService 결과에 추가 가능 |

---

## 7. 운영 튜닝 포인트

운영 중 retrieval 개수, context 길이, 세션 저장 길이를 조정해야 할 때
우선 확인할 위치는 아래 두 파일이다.

### `settings/knowledge.py`

- `DEFAULT_KNOWLEDGE_RETRIEVAL_TOP_K`
  - 기본 retrieval 결과 개수
- `KNOWLEDGE_DEDUPE_TEXT_PREFIX_LEN`
  - `chunk_id`가 없을 때 dedupe 비교에 쓰는 텍스트 prefix 길이
- `ANSWER_CONTEXT_PLATFORM_TOP_K`
- `ANSWER_CONTEXT_WORKSPACE_TOP_K`
- `ANSWER_CONTEXT_SESSION_TOP_K`
  - source별 AnswerContextBuilder 노출 개수
- `ANSWER_CONTEXT_PLATFORM_TEXT_MAX`
- `ANSWER_CONTEXT_WORKSPACE_TEXT_MAX`
- `ANSWER_CONTEXT_SESSION_TEXT_MAX`
  - source별 context text trim 길이

### `settings/chat.py`

- `SESSION_DOCUMENT_BODY_MAX`
- `SESSION_DOCUMENT_TABLE_MAX`
  - 세션 임시 첨부 문서를 `ChatSession.reference_document_text`에 저장할 때의 길이 상한

튜닝 원칙:
- retrieval 개수를 늘릴수록 recall은 올라가지만 context noise도 증가할 수 있다
- context text max를 늘릴수록 근거는 많아지지만 prompt 길이와 응답 지연이 늘 수 있다
- session 문서는 현재 score=1.0으로 포함되므로 길이 상한을 과하게 늘리지 않는 편이 안전하다

---

## 8. 패키지 구조 요약

```
backend/
├── domains/
│   ├── document/
│   │   ├── document_schema.py      DocumentSchema, DocumentTableBlock, DocumentPage
│   │   ├── schemas.py              API 입출력 스키마
│   │   ├── extract_service.py      ExtractedDocument 생성
│   │   ├── normalize_service.py    ExtractedDocument → DocumentSchema
│   │   ├── classification_service.py  DocumentSchema → document_type / category
│   │   ├── document_schema_resolver.py  normalized cache 진입점 (cache hit/miss → DocumentSchema)
│   │   ├── normalized_document_store.py  cache 저장소 (.json/.tmp/.lock 관리)
│   │   ├── summary_process.py      요약 파이프라인 진입점 (cache → classify → summarize → DONE → index enqueue)
│   │   ├── summary_payload.py      DocumentSchema → LLM 입력
│   │   ├── summary_llm_service.py  LLM 요약 호출
│   │   └── repository.py           update_classification() — 분류 저장 단일 진입점
│   │
│   ├── rag/
│   │   ├── document_chunk_service.py           DocumentSchema → chunk 리스트
│   │   ├── group_document_indexing_service.py  DocumentSchema(cache) → chunk → index
│   │   │                                       chunk payload에 document_type/category 포함
│   │   └── group_document_retrieval_service.py group/document 범위 검색
│   │
│   ├── chat/
│   │   ├── processor.py                단일 retrieval 진입점 사용
│   │   ├── service.py                  workspace 권한 검증 포함
│   │   ├── session_payload.py          DocumentSchema → 세션 저장 텍스트
│   │   └── workspace_selection_parser.py  API 입력 파싱/검증
│   │
│   └── knowledge/
│       ├── knowledge_retrieval_service.py   retriever orchestrator
│       ├── answer_context_builder.py        검색 결과 → context 문자열
│       ├── platform_knowledge_retriever.py  판례 RAG
│       ├── workspace_knowledge_retriever.py 그룹 문서 RAG (selection 지원)
│       └── session_document_retriever.py    임시 첨부 문서
│
├── prompts/
│   ├── classify_prompt.py      분류 LLM 프롬프트 (허용값 고정)
│   └── summarize_prompt.py     요약 LLM 프롬프트
│
└── models/
    └── model.py                전체 ORM 모델 (domain 분리 전까지 현위치 유지)
```

---

## 9. Normalized Document Cache Lifecycle

normalized document cache는 `runtime/normalized_documents/{document_id}.json`에 저장되며
요약과 인덱싱 양쪽에서 공유한다.

### 재사용 조건 (세 조건 모두 충족 시 cache 재사용)

| 조건 | 설명 |
|---|---|
| `schema_version` 일치 | DocumentSchema 구조 버전 (`v1` 고정) |
| `normalization_version` 일치 | NormalizeService 구현 버전 |
| source fingerprint 일치 | 파일 size/mtime/sha256 모두 동일 |

### fingerprint 비교 전략

```
1단계 (fast path): os.stat 기반 size + mtime 비교
  └─ 일치 → sha256 계산 없이 즉시 cache 재사용
  └─ 불일치 → 2단계

2단계 (slow path): sha256 포함 full fingerprint 계산
  └─ 일치 → cache 재사용
  └─ 불일치 → extract → normalize → 저장
```

### 파일 구조

| 파일 | 역할 |
|---|---|
| `{id}.json` | normalized DocumentSchema 본체 |
| `{id}.json.tmp` | atomic write 중간 파일. 정상 완료 시 자동 정리된다. |
| `{id}.lock` | fcntl 동시 작성 차단용. 중단 시 남을 수 있으나 안전하게 재사용 가능하다. |

### cache cleanup lifecycle

```
문서 최종 삭제 (DELETED 상태 전환)
  │
  ▼
enqueue_document_file_cleanup(document_id)
  │
  ▼
cleanup_document_files Celery task
  - stored_path 삭제
  - preview_pdf_path 삭제
  - NormalizedDocumentStore.get_cleanup_paths(document_id)
      └─ {id}.json, {id}.json.tmp, {id}.lock 삭제 (없으면 skip)
```

- cleanup은 idempotent: 파일이 없어도 예외 없이 skip
- cache 소실된 뒤 다시 필요하면 extract/normalize 시 자동 복구
- 이 파일들은 언제든 삭제해도 안전하다 (DB와 원본 파일이 source of truth)
