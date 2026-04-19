# ERD

## 1. 목적

- 현재 서비스의 실제 엔티티와 관계를 정리한다.
- 기능 요구와 데이터 source of truth를 같은 기준으로 맞춘다.
- 플랫폼 지식, 문서 처리, 채팅 첨부, export 구조를 한 번에 본다.

## 2. 핵심 엔티티

### 2.1 사용자 / 구독

#### User

- id
- email
- username
- password
- role
- is_active
- created_at
- updated_at
- deactivated_at

#### SocialAccount

- id
- user_id
- provider
- provider_id
- email
- created_at

#### Subscription

- id
- user_id
- plan
- status
- auto_renew
- started_at
- ended_at
- created_at
- updated_at

### 2.2 워크스페이스

#### Group

- id
- owner_user_id
- name
- description
- status
- pending_reason
- delete_requested_at
- delete_scheduled_at
- deleted_at
- created_at
- updated_at

#### GroupMember

- id
- user_id
- group_id
- role
- status
- invited_by_user_id
- invited_at
- joined_at
- removed_at
- created_at
- updated_at

### 2.3 문서

#### Document

- id
- group_id
- uploader_user_id
- original_filename
- stored_path
- original_content_type
- preview_pdf_path
- preview_status
- title
- document_type
- category
- processing_status
- failure_stage
- failure_code
- error_message
- lifecycle_status
- delete_requested_at
- delete_scheduled_at
- deleted_at
- deleted_by_user_id
- created_at
- updated_at

설명:
- 문서 분류의 source of truth는 `documents.document_type`, `documents.category`
- 처리 실패 메타는 `documents.failure_*`

#### DocumentApproval

- id
- document_id
- assignee_user_id
- reviewer_user_id
- status
- feedback
- reviewed_at
- created_at
- updated_at

#### Summary

- id
- document_id
- summary_text
- key_points
- metadata_json
- created_at
- updated_at

#### DocumentComment

- id
- document_id
- author_user_id
- parent_id
- content
- comment_scope
- page
- x
- y
- deleted_by_user_id
- deleted_at
- created_at
- updated_at

#### DocumentCommentMention

- id
- comment_id
- mentioned_user_id
- snapshot_username
- start_index
- end_index
- created_at

### 2.4 채팅

#### ChatSession

- id
- user_id
- title
- reference_group_id
- created_at
- updated_at

#### ChatMessage

- id
- session_id
- role
- content
- metadata_json
- created_at

설명:
- 답변 citation과 retrieval failure 메타는 `metadata_json`에 저장된다.

#### ChatSessionReference

- id
- session_id
- source_type
- title
- upload_path
- extracted_text
- status
- failure_code
- error_message
- created_at
- updated_at

#### ChatSessionReferenceChunk

- id
- reference_id
- chunk_order
- chunk_text
- created_at

설명:
- 세션 첨부 문서는 `chat_session_references` + `chat_session_reference_chunks`가 source of truth
- 예전 `chat_sessions.reference_document_*` 컬럼은 제거됨

### 2.5 알림 / export

#### Notification

- id
- user_id
- actor_user_id
- group_id
- type
- title
- body
- is_read
- read_at
- target_type
- target_id
- created_at

#### NotificationSetting

- id
- user_id
- notification_type
- enabled
- created_at
- updated_at

#### ExportJob

- id
- user_id
- group_id
- requester_role
- status
- file_path
- export_file_name
- failure_stage
- failure_code
- error_message
- total_file_count
- exported_file_count
- missing_file_count
- started_at
- finished_at
- cancelled_at
- expires_at
- created_at
- updated_at

### 2.6 플랫폼 지식

#### PlatformRawSource

- id
- source_type
- provider
- api_target
- external_id
- raw_format
- raw_payload
- fetched_at
- checksum
- status
- extra_meta
- created_at
- updated_at

#### PlatformDocument

- id
- raw_source_id
- source_type
- external_id
- title
- body_text
- document_url
- effective_date
- metadata_json
- created_at
- updated_at

#### PlatformDocumentChunk

- id
- document_id
- chunk_id
- chunk_order
- chunk_type
- chunk_text
- metadata_json
- created_at
- updated_at

#### PlatformSyncRun

- id
- source_type
- started_at
- finished_at
- status
- stats_json
- metadata_json
- created_at
- updated_at

#### PlatformSyncFailure

- id
- run_id
- source_type
- external_id
- title
- error_type
- error_message
- created_at

설명:
- 플랫폼 지식 source of truth는 `platform_documents` / `platform_document_chunks`
- 판례도 `source_type='precedent'`로 여기서 관리

## 3. 주요 관계

### 3.1 사용자 중심

- User 1 : 1 Subscription
- User 1 : N SocialAccount
- User 1 : N Group(owned_groups)
- User 1 : N GroupMember
- User 1 : N Document
- User 1 : N ChatSession
- User 1 : N Notification
- User 1 : N ExportJob

### 3.2 워크스페이스 중심

- Group 1 : N GroupMember
- Group 1 : N Document
- Group 1 : N Notification
- Group 1 : N ExportJob
- Group 1 : N ChatSession(선택 참조)

### 3.3 문서 중심

- Document 1 : 1 DocumentApproval
- Document 1 : 1 Summary
- Document 1 : N DocumentComment
- DocumentComment 1 : N DocumentComment(replies)
- DocumentComment 1 : N DocumentCommentMention

### 3.4 채팅 중심

- ChatSession 1 : N ChatMessage
- ChatSession 1 : 1 ChatSessionReference
- ChatSessionReference 1 : N ChatSessionReferenceChunk

### 3.5 플랫폼 지식 중심

- PlatformRawSource 1 : N PlatformDocument
- PlatformDocument 1 : N PlatformDocumentChunk
- PlatformSyncRun 1 : N PlatformSyncFailure

## 4. ERD 해석 기준

- source of truth가 둘 이상인 구조는 문서 기준으로 허용하지 않는다.
- 문서 분류값은 `documents`를 기준으로 본다.
- 세션 첨부는 `chat_session_references` 계층을 기준으로 본다.
- 플랫폼 지식은 `platform_*` 계층을 기준으로 본다.
