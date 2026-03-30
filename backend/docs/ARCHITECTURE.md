# Backend Architecture — Document Pipeline & Chat Knowledge Flow

> 작성 기준: 13단계 완료 시점  
> 대상 독자: 신규 합류 개발자, 구조 파악이 필요한 팀원

---

## 1. Document Pipeline

PDF 업로드부터 저장/인덱싱까지의 흐름.

```
PDF 파일
  │
  ▼
DocumentExtractService          services/document_extract_service.py
  - opendataloader-pdf 1차 시도
  - body 없으면 LocalOcrService fallback
  - 반환: ExtractedDocument(markdown, json_data, source_type)
  │
  ▼
DocumentNormalizeService         services/document_normalize_service.py
  - extractor가 넘긴 source_type 사용 (odl | ocr)
  - body_text, table_blocks, pages, metadata 생성
  - 반환: DocumentSchema
  │
  ├──▶ DocumentSummaryPayloadService    services/summary/document_summary_payload_service.py
  │      - [본문]/[표] LLM 입력 문자열 조립
  │      - ProcessService → LLMService → SummaryRepository
  │
  ├──▶ DocumentChunkService            services/rag/document_chunk_service.py
  │      - body chunk / table chunk 분할
  │      - group_document_indexing_service → Qdrant + BM25
  │
  └──▶ SessionDocumentPayloadService   services/chat/session_document_payload_service.py
         - 세션 임시 첨부용 단일 텍스트 (body 6000자 / table 2000자 상한)
         - ChatSession.reference_document_text 에 저장
```

### 핵심 계약

| 타입 | 위치 | 역할 |
|---|---|---|
| `ExtractedDocument` | `document_extract_service.py` | 추출기 원본 (raw) |
| `DocumentSchema` | `schemas/document_schema.py` | 정규화된 공통 소비 계약 |
| `DocumentTableBlock` | `schemas/document_schema.py` | 표 단위 객체 |
| `DocumentPage` | `schemas/document_schema.py` | 페이지 단위 (v1: 전체 = 1페이지) |

---

## 2. Chat Knowledge Flow

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

## 3. Workspace Selection Flow

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

## 4. 현재 제약 및 다음 과제

| 항목 | 현재 상태 | 다음 과제 |
|---|---|---|
| `pages` 분리 | v1: 전체 문서 = 1페이지로 단순화 | ODL/OCR page 정보 실제 분리 |
| `document_type` | normalize 단계에서 None | DocumentClassificationService 추가 |
| workspace `mode="documents"` | 지원 (BM25 + Qdrant whitelist) | folder/category 확장 가능 |
| session retrieval | 단일 텍스트 블록 반환 | 긴 문서 분할 후 top chunk 반환 |
| LangChain | 미도입 | core contract는 완성됨, adapter 검토 가능 |
| reranker | 미도입 | KnowledgeRetrievalService 결과에 추가 가능 |

---

## 5. 운영 튜닝 포인트

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

## 6. 패키지 구조 요약

```
backend/
├── schemas/
│   ├── document_schema.py      DocumentSchema, DocumentTableBlock, DocumentPage
│   ├── knowledge.py            KnowledgeType, RetrievedKnowledgeItem, KnowledgeRetrievalRequest
│   └── chat.py                 ChatWorkspaceSelectionInput
│
├── services/
│   ├── document_extract_service.py      ExtractedDocument 생성
│   ├── document_normalize_service.py    ExtractedDocument → DocumentSchema
│   │
│   ├── summary/
│   │   ├── process_service.py                  요약 파이프라인 진입점
│   │   └── document_summary_payload_service.py DocumentSchema → LLM 입력
│   │
│   ├── rag/
│   │   ├── document_chunk_service.py           DocumentSchema → chunk 리스트
│   │   ├── group_document_indexing_service.py  extract → normalize → index
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
```
