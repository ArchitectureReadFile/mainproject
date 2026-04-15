# backend 목표 구조 매핑표

최종 목표 구조: `app / core / infra / domains / prompts / tests`

---

## core — 설정, 보안, 에러, 공통 의존성

| 현재 경로 | 목표 경로 | 비고 |
|---|---|---|
| `main.py` | `app/main.py` | FastAPI 앱 엔트리 |
| `database.py` | `core/db.py` | SQLAlchemy engine/session |
| `dependencies.py` | `core/dependencies.py` | FastAPI Depends 모음 |
| `errors/error_codes.py` | `core/error_codes.py` | |
| `errors/exceptions.py` | `core/exceptions.py` | |
| `settings/chat.py` | `core/settings/chat.py` | |
| `settings/knowledge.py` | `core/settings/knowledge.py` | |
| `settings/platform.py` | `core/settings/platform.py` | |

---

## infra — 외부 시스템 클라이언트

| 현재 경로 | 목표 경로 | 비고 |
|---|---|---|
| `database.py` | `infra/db/session.py` | core와 중복 정의 가능, 역할 분리 필요 |
| `redis_client.py` | `infra/redis/client.py` | |
| `celery_app.py` | `infra/celery/app.py` | task_routes 포함 |
| `services/rag/embedding_service.py` | `infra/ml/embedding.py` | SentenceTransformer 로딩 |
| `services/rag/vector_store.py` | `infra/vectorstore/qdrant.py` | Qdrant 클라이언트 |
| `services/rag/bm25_store.py` | `infra/vectorstore/bm25.py` | Redis 기반 BM25 |
| `services/summary/llm_client.py` | `infra/llm/ollama_client.py` | Ollama HTTP 통신 |
| `services/ocr/` (전체) | `infra/ocr/` | LibreOffice/OCR 인프라 |
| `extractors/` (전체) | `infra/extractors/` | 문서 파싱 인프라 |
| `services/platform/korea_law_open_api_client.py` | `infra/external/korea_law_api.py` | 외부 API 클라이언트 |

---

## domains — 기능 단위

### auth
| 현재 경로 | 목표 경로 |
|---|---|
| `routers/auth.py` | `domains/auth/router.py` |
| `services/auth_service.py` | `domains/auth/service.py` |
| `services/cookie_service.py` | `domains/auth/cookie_service.py` |
| `repositories/auth_repository.py` | `domains/auth/repository.py` |
| `schemas/auth.py` | `domains/auth/schemas.py` |

### oauth
| 현재 경로 | 목표 경로 |
|---|---|
| `routers/oauth.py` | `domains/oauth/router.py` |
| `services/oauth_service.py` | `domains/oauth/service.py` |
| `repositories/oauth_repository.py` | `domains/oauth/repository.py` |

### email
| 현재 경로 | 목표 경로 |
|---|---|
| `routers/email.py` | `domains/email/router.py` |
| `services/email_service.py` | `domains/email/service.py` |
| `repositories/email_repository.py` | `domains/email/repository.py` |
| `schemas/email.py` | `domains/email/schemas.py` |

### chat
| 현재 경로 | 목표 경로 |
|---|---|
| `routers/chat.py` | `domains/chat/router.py` |
| `routers/ws.py` | `domains/chat/ws_router.py` |
| `services/chat/chat_service.py` | `domains/chat/service.py` |
| `services/chat/chat_processor.py` | `domains/chat/processor.py` |
| `services/chat/session_document_payload_service.py` | `domains/chat/session_payload.py` |
| `services/chat/workspace_selection_parser.py` | `domains/chat/workspace_selection_parser.py` |
| `repositories/chat_repository.py` | `domains/chat/repository.py` |
| `schemas/chat.py` | `domains/chat/schemas.py` |
| `schemas/knowledge.py` | `domains/chat/knowledge_schemas.py` |
| `schemas/search.py` | `domains/chat/search_schemas.py` |
| `tasks/chat_task.py` | `domains/chat/tasks.py` |

### workspace (group)
| 현재 경로 | 목표 경로 |
|---|---|
| `routers/group.py` | `domains/workspace/router.py` |
| `services/group_service.py` | `domains/workspace/service.py` |
| `repositories/group_repository.py` | `domains/workspace/repository.py` |
| `schemas/group.py` | `domains/workspace/schemas.py` |
| `tasks/workspace_deletion_task.py` | `domains/workspace/tasks.py` |

### document
| 현재 경로 | 목표 경로 |
|---|---|
| `routers/group_document.py` | `domains/document/router.py` |
| `routers/summarize.py` | `domains/document/summary_router.py` |
| `services/document_service.py` | `domains/document/service.py` |
| `services/document_classification_service.py` | `domains/document/classification_service.py` |
| `services/document_comment_service.py` | `domains/document/comment_service.py` |
| `services/document_extract_service.py` | `domains/document/extract_service.py` |
| `services/document_normalize_service.py` | `domains/document/normalize_service.py` |
| `services/document_preview_service.py` | `domains/document/preview_service.py` |
| `services/document_review_service.py` | `domains/document/review_service.py` |
| `services/upload/service.py` | `domains/document/upload_service.py` |
| `repositories/document_repository.py` | `domains/document/repository.py` |
| `repositories/document_comment_repository.py` | `domains/document/comment_repository.py` |
| `repositories/document_review_repository.py` | `domains/document/review_repository.py` |
| `repositories/summary_repository.py` | `domains/document/summary_repository.py` |
| `schemas/document.py` | `domains/document/schemas.py` |
| `schemas/document_schema.py` | `domains/document/document_schema.py` |
| `schemas/comment.py` | `domains/document/comment_schemas.py` |
| `schemas/summary.py` | `domains/document/summary_schemas.py` |
| `tasks/upload_task.py` | `domains/document/upload_task.py` |
| `tasks/group_document_task.py` | `domains/document/index_task.py` |
| `tasks/document_deletion_task.py` | `domains/document/deletion_task.py` |
| `tasks/file_cleanup_task.py` | `domains/document/file_cleanup_task.py` |
| `services/summary/process_service.py` | `domains/document/summary_process.py` |
| `services/summary/llm_service.py` | `domains/document/summary_llm_service.py` |
| `services/summary/document_summary_payload_service.py` | `domains/document/summary_payload.py` |
| `services/summary/summary_mapper.py` | `domains/document/summary_mapper.py` |
| `services/summary/pdf_service.py` | `domains/document/pdf_export_service.py` |

### notification
| 현재 경로 | 목표 경로 |
|---|---|
| `routers/notification.py` | `domains/notification/router.py` |
| `services/notification_service.py` | `domains/notification/service.py` |
| `repositories/notification_repository.py` | `domains/notification/repository.py` |
| `schemas/notification.py` | `domains/notification/schemas.py` |

### admin
| 현재 경로 | 목표 경로 |
|---|---|
| `routers/admin.py` | `domains/admin/router.py` |
| `services/admin_service.py` | `domains/admin/service.py` |
| `services/admin_platform_service.py` | `domains/admin/platform_service.py` |
| `schemas/admin.py` | `domains/admin/schemas.py` |
| `tasks/subscription_task.py` | `domains/admin/subscription_task.py` |

### export
| 현재 경로 | 목표 경로 |
|---|---|
| `routers/export.py` | `domains/export/router.py` |
| `services/export_service.py` | `domains/export/service.py` |
| `repositories/export_repository.py` | `domains/export/repository.py` |
| `schemas/export.py` | `domains/export/schemas.py` |
| `tasks/export_task.py` | `domains/export/tasks.py` |

### platform_sync
| 현재 경로 | 목표 경로 |
|---|---|
| `services/platform/` (전체) | `domains/platform_sync/platform/` |
| `services/precedent/` (전체) | `domains/platform_sync/precedent/` |
| `schemas/platform_knowledge_schema.py` | `domains/platform_sync/schemas.py` |
| `tasks/platform_sync_task.py` | `domains/platform_sync/sync_task.py` |
| `tasks/precedent_task.py` | `domains/platform_sync/precedent_task.py` |

### rag (knowledge)
| 현재 경로 | 목표 경로 |
|---|---|
| `services/rag/document_chunk_service.py` | `domains/rag/chunk_service.py` |
| `services/rag/group_document_chunk_builder.py` | `domains/rag/group_chunk_builder.py` |
| `services/rag/group_document_indexing_service.py` | `domains/rag/group_indexing.py` |
| `services/rag/group_document_retrieval_service.py` | `domains/rag/group_retrieval.py` |
| `services/rag/grouping_service.py` | `domains/rag/grouping.py` |
| `services/rag/retrieval_service.py` | `domains/rag/retrieval.py` |
| `services/knowledge/` (전체) | `domains/rag/knowledge/` |

---

## 공유 레이어

| 현재 경로 | 목표 경로 | 비고 |
|---|---|---|
| `models/model.py` | `models/model.py` | 전체 ORM 모델. domain 분리 전까지 현위치 유지 |
| `models/platform_knowledge.py` | `models/platform_knowledge.py` | 동일 |
| `prompts/` (전체) | `prompts/` | 현위치 유지 |
| `fonts/` | `fonts/` | 현위치 유지 |
| `tests/` | `tests/` | 현위치 유지 |

---

## 1차 이동 대상 도메인 (다음 단계)

우선순위 기준: import 영향 범위 최소 + 독립성 높음

| 순위 | domain | 이유 |
|---|---|---|
| 1 | `auth` | 다른 도메인 의존성 없음. router/service/repo/schema 4개 파일. |
| 2 | `oauth` | auth와 유사 구조. 3개 파일. |
| 3 | `email` | 독립적. 4개 파일. |
| 4 | `notification` | 다른 서비스에서 import하지만 역방향 의존 없음. |
| 5 | `export` | 독립적 흐름. group_service 참조만 정리하면 됨. |

**보류 도메인**: `document`, `chat`, `platform_sync`, `rag`, `workspace`
이유: 상호 참조 빈도가 높고, `models/model.py` 분리 전 이동 시 순환 import 위험.

---

## import 경로 영향 범위 요약

이동 시 수정이 필요한 참조 지점:
- `main.py`: 모든 router import → 도메인별 경로로 변경
- `celery_app.py`: task include 목록 → 도메인별 경로로 변경
- `dependencies.py`: service import → 도메인별 경로로 변경
- 각 service/task 내부의 cross-domain import → 인터페이스 정리 필요
