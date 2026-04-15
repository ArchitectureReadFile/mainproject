# Backend Architecture — Document Pipeline & Chat Knowledge Flow

> 작성 기준: 문서 분류 시스템 구현 완료 시점
> 대상 독자: 신규 합류 개발자, 구조 파악이 필요한 팀원

---

## 1. Document Pipeline

PDF 업로드부터 분류/요약/인덱싱까지의 흐름.

```
PDF 파일
  │
  ▼
DocumentExtractService          services/document_extract_service.py
  - opendataloader-pdf hybrid OCR 호출
  - scanned/image PDF 포함 단일 추출 경로
  - 반환: ExtractedDocument(markdown, json_data, source_type)
  │
  ▼
DocumentNormalizeService        services/document_normalize_service.py
  - extractor가 넘긴 source_type 사용 (odl | ocr)
  - body_text, table_blocks, pages, metadata 생성
  - 반환: DocumentSchema
  │
  ▼
DocumentClassificationService   services/document_classification_service.py
  - title + body_text(최대 3000자) → LLM 단일 호출
  - 반환: {document_type, category}
  - 허용값 외 응답 및 LLM 오류 → "미분류" fallback (파이프라인 중단 없음)
  │
  ▼
Document.document_type          repositories/document_repository.py
Document.category               update_classification() → DB commit
  (source of truth)
  │
  ▼
DocumentSummaryPayloadService   services/summary/document_summary_payload_service.py
  - [본문]/[표] LLM 입력 문자열 조립
  │
  ▼
LLMService.summarize()          services/summary/llm_service.py
  - summary_text, key_points 생성
  - document_type는 추출하지 않음 (분류는 별도 단계에서 완료)
  │
  ▼
SummaryRepository.create_summary()
  - summary_text, key_points 저장
  - metadata: {"source": "group_document_summary"} (보조 기록)
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

### 핵심 계약

| 타입 | 위치 | 역할 |
|---|---|---|
| `ExtractedDocument` | `document_extract_service.py` | 추출기 원본 (raw) |
| `DocumentSchema` | `schemas/document_schema.py` | 정규화된 공통 소비 계약 |
| `DocumentTableBlock` | `schemas/document_schema.py` | 표 단위 객체 |
| `DocumentPage` | `schemas/document_schema.py` | 페이지 단위 (v1: 전체 = 1페이지) |

---

## 2. 승인 후 RAG 인덱싱

승인(APPROVE) 전에는 RAG 인덱싱을 수행하지 않는다.
승인 시점에 `index_approved_document` Celery task가 호출된다.

```
DocumentReviewService.approve_document()
  │
  ├─ DocumentApproval.status = APPROVED → DB commit
  │
  └─ index_approved_document.delay(document_id)   tasks/group_document_task.py
       │
       ▼
     index_group_document()     services/rag/group_document_indexing_service.py
       - extract → normalize → chunk
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
검색 boost 연결은 별도 설계 후 추가 예정이다.

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
ChatProcessor.process_chat()     services/chat/chat_processor.py
  │
  ├─ KnowledgeRetrievalRequest 생성
  │    include_platform=True (항상)
  │    include_workspace=bool(workspace_selection)
  │    include_session=bool(reference_document_text)
  │
  ▼
KnowledgeRetrievalService        services/knowledge/knowledge_retrieval_service.py
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
AnswerContextBuilder.build()     services/knowledge/answer_context_builder.py
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
├── schemas/
│   ├── document_schema.py      DocumentSchema, DocumentTableBlock, DocumentPage
│   ├── knowledge.py            KnowledgeType, RetrievedKnowledgeItem, KnowledgeRetrievalRequest
│   └── chat.py                 ChatWorkspaceSelectionInput
│
├── services/
│   ├── document_extract_service.py           ExtractedDocument 생성
│   ├── document_normalize_service.py         ExtractedDocument → DocumentSchema
│   ├── document_classification_service.py    DocumentSchema → document_type / category
│   │
│   ├── summary/
│   │   ├── process_service.py                       요약 파이프라인 진입점
│   │   │                                            (classify → save → summarize → save)
│   │   └── document_summary_payload_service.py      DocumentSchema → LLM 입력
│   │
│   ├── rag/
│   │   ├── document_chunk_service.py           DocumentSchema → chunk 리스트
│   │   ├── group_document_indexing_service.py  extract → normalize → index
│   │   │                                       chunk payload에 document_type/category 포함
│   │   └── group_document_retrieval_service.py group/document 범위 검색
│   │
│   ├── chat/
│   │   ├── chat_processor.py                   단일 retrieval 진입점 사용
│   │   ├── chat_service.py                     workspace 권한 검증 포함
│   │   ├── session_document_payload_service.py DocumentSchema → 세션 저장 텍스트
│   │   └── workspace_selection_parser.py       API 입력 파싱/검증
│   │
│   └── knowledge/
│       ├── knowledge_retrieval_service.py      retriever orchestrator
│       ├── answer_context_builder.py           검색 결과 → context 문자열
│       ├── platform_knowledge_retriever.py     판례 RAG
│       ├── workspace_knowledge_retriever.py    그룹 문서 RAG (selection 지원)
│       └── session_document_retriever.py       임시 첨부 문서
│
├── prompts/
│   ├── classify_prompt.py      분류 LLM 프롬프트 (허용값 고정)
│   └── summarize_prompt.py     요약 LLM 프롬프트
│
└── repositories/
    └── document_repository.py  update_classification() — 분류 저장 단일 진입점
```
