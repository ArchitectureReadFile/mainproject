# ERD

## 1. 문서 개요

- 시스템명: RAG기반 법률 상담 및 문서 요약 시스템
- 문서 목적:
  - 시스템의 핵심 엔티티와 관계를 정의한다.
  - 기능 요구사항을 데이터 구조 관점에서 정리한다.
  - 백엔드, AI/RAG, 프론트엔드가 동일한 데이터 기준으로 협업할 수 있도록 한다.

## 2. 작성 방식

- 제출용 문서에는 ERD 다이어그램 이미지와 주요 엔티티 설명을 포함한다.
- ERD 원본은 별도 다이어그램 툴에서 관리한다.
- 본 문서는 다이어그램에 포함될 엔티티와 관계 기준을 정리한 초안이다.

권장 산출물 구성:

- `docs/04_ERD.md`
- `docs/assets/erd.png`
- 필요 시 원본 파일 (`.drawio`, `.dbml` 등)

## 3. 핵심 엔티티 목록

### 3.1 User

- 설명: 시스템 사용자 정보
- 주요 속성:
  - id
  - email
  - username
  - password
  - role
  - is_active
  - created_at
  - updated_at
  - deactivated_at

### 3.2 Subscription

- 설명: 사용자 구독 정보
- 주요 속성:
  - id
  - user_id
  - plan
  - status
  - auto_renew
  - started_at
  - ended_at
  - created_at
  - updated_at

### 3.3 Group

- 설명: 워크스페이스 정보
- 주요 속성:
  - id
  - owner_user_id
  - name
  - description
  - status
  - pending_reason
  - delete_scheduled_at
  - created_at
  - updated_at

### 3.4 GroupMember

- 설명: 워크스페이스 멤버십 및 권한 정보
- 주요 속성:
  - id
  - group_id
  - user_id
  - role
  - status
  - invited_by_user_id
  - joined_at
  - created_at
  - updated_at

### 3.5 Document

- 설명: 워크스페이스 업로드 문서 정보
- 주요 속성:
  - id
  - group_id
  - uploader_user_id
  - title
  - original_filename
  - stored_path
  - processing_status
  - lifecycle_status
  - metadata_json
  - created_at
  - updated_at
  - deleted_at
  - deleted_by_user_id

### 3.6 Summary

- 설명: 문서 요약 결과
- 주요 속성:
  - id
  - document_id
  - summary_text
  - key_points
  - case_number
  - case_name
  - court_name
  - judgment_date
  - created_at
  - updated_at

### 3.7 DocumentApproval

- 설명: 문서 승인 및 반려 상태
- 주요 속성:
  - id
  - document_id
  - assignee_user_id
  - reviewer_user_id
  - status
  - feedback
  - reviewed_at
  - created_at
  - updated_at

### 3.8 DocumentComment

- 설명: 문서 협업 댓글
- 주요 속성:
  - id
  - document_id
  - parent_id
  - author_user_id
  - scope
  - content
  - page
  - x
  - y
  - is_deleted
  - deleted_by_user_id
  - created_at
  - updated_at

### 3.9 ChatSession

- 설명: 사용자 채팅 세션
- 주요 속성:
  - id
  - user_id
  - title
  - reference_document_title
  - reference_document_text
  - reference_group_id
  - created_at
  - updated_at

### 3.10 ChatMessage

- 설명: 채팅 세션별 메시지
- 주요 속성:
  - id
  - session_id
  - role
  - content
  - created_at

### 3.11 Notification

- 설명: 시스템 알림
- 주요 속성:
  - id
  - user_id
  - actor_user_id
  - group_id
  - type
  - title
  - body
  - is_read
  - target_type
  - target_id
  - created_at

### 3.12 NotificationSetting

- 설명: 사용자별 알림 수신 설정
- 주요 속성:
  - id
  - user_id
  - notification_type
  - enabled
  - created_at
  - updated_at

### 3.13 PlatformKnowledge

- 설명: 법률 및 판례 기반 플랫폼 지식 데이터
- 주요 속성:
  - id
  - source_type
  - source_key
  - title
  - content
  - metadata_json
  - processing_status
  - created_at
  - updated_at

## 4. 엔티티 관계

### 4.1 사용자 중심 관계

- User 1 : 1 Subscription
- User 1 : N Group
- User 1 : N GroupMember
- User 1 : N Document
- User 1 : N ChatSession
- User 1 : N Notification
- User 1 : N DocumentComment

### 4.2 워크스페이스 중심 관계

- Group 1 : N GroupMember
- Group 1 : N Document
- Group 1 : N Notification

### 4.3 문서 중심 관계

- Document 1 : 1 Summary
- Document 1 : N DocumentApproval
- Document 1 : N DocumentComment

### 4.4 채팅 중심 관계

- ChatSession 1 : N ChatMessage
- Group 1 : N ChatSession
  - 선택적 참조 관계로 사용 가능

### 4.5 댓글 계층 관계

- DocumentComment 1 : N DocumentComment
  - parent_id를 통한 대댓글 구조

## 5. ERD 다이어그램 작성 기준

다이어그램에는 아래 관계를 우선 반영한다.

- `users - subscriptions`
- `users - groups`
- `groups - group_members - users`
- `groups - documents`
- `documents - summaries`
- `documents - document_approvals`
- `documents - document_comments`
- `users - chat_sessions - chat_messages`
- `users - notifications`

표현 권장 방식:

- PK, FK를 명확히 구분한다.
- 상태값은 enum 또는 코드값으로 별도 표시한다.
- soft delete, 승인 상태, 처리 상태는 주석으로 의미를 표시한다.
- AI/RAG 인덱스 저장소는 물리 DB 엔티티와 분리해서 설명한다.

## 6. 비고

- 본 문서는 논리 ERD 기준 초안이다.
- 실제 물리 ERD 작성 시 컬럼명, nullable 여부, 제약조건, index 여부를 추가 정리해야 한다.
- 벡터 저장소와 BM25 저장소는 별도 검색 인프라로 관리되므로, 핵심 ERD에는 보조 구조로 표기하는 것이 적절하다.
