# API 계약서 v0.4

이 문서는 현재 FastAPI 구현을 기준으로 정리한 API 계약서 초안입니다.

## 1. 공통 규칙

### 1-1. Base URL

```text
/api
```

프론트는 Vite 프록시를 통해 `/api` 기준으로 호출합니다.

### 1-2. 인증 방식

| 항목 | 저장 위치 | 설명 |
| --- | --- | --- |
| `access_token` | Cookie | 프론트 요청 시 사용 |
| `refresh_token` | Cookie | 토큰 재발급용 |

현재 구현 기준:
- `access_token`은 `httpOnly: false`
- `refresh_token`은 `httpOnly: true`
- Axios 인터셉터가 `/api/auth/refresh`를 이용해 1회 재시도합니다.

### 1-3. 공통 에러 응답

```json
{
  "code": "AUTH_001",
  "message": "로그인이 필요합니다."
}
```

주의:
- `AppException`은 위 형식으로 응답합니다.
- FastAPI validation 에러는 별도 `detail` 배열 형식을 사용할 수 있습니다.

### 1-4. 문서 상태값

| 값 | 설명 |
| --- | --- |
| `PENDING` | 업로드 완료, 처리 대기 |
| `PROCESSING` | 요약 처리 중 |
| `DONE` | 요약 완료 |
| `FAILED` | 처리 실패 |

### 1-5. 사용자 역할

| 값 | 설명 |
| --- | --- |
| `GENERAL` | 일반 사용자 |
| `ADMIN` | 관리자 |

### 1-6. 공통 처리 상태값

워크스페이스 문서 처리와 RAG 판례 인덱싱에 공통으로 사용하는 처리 상태입니다.

| 값 | 설명 |
| --- | --- |
| `PENDING` | 작업 대기 |
| `PROCESSING` | 작업 진행 중 |
| `DONE` | 작업 완료 |
| `FAILED` | 작업 실패 |

### 1-7. 업로드 파이프라인 구분

업로드는 UI 상에서 비슷해 보여도 저장 위치, 권한, 후처리 목적이 다르므로 아래 3개 파이프라인으로 구분합니다.

#### `group_document_upload`

- 목적: 워크스페이스 문서를 영속 저장하고 요약을 생성합니다.
- 인증: 로그인 + 그룹 업로드 권한 필요
- 저장:
  - 원본 파일 저장소
  - `documents` row 생성
  - `summaries` row 생성(비동기 완료 시)
- 상태:
  - `Document.processing_status`
  - Redis `upload_session`
- 비동기 처리:
  - 업로드 요청은 파일 저장 + `PENDING` 생성까지만 수행
  - OCR/요약은 Celery worker에서 수행

#### `precedent_upload`

- 목적: 판례 원문을 RAG 지식베이스에 반영합니다.
- 인증: 관리자
- 저장:
  - `precedents` row 생성
  - Dense/BM25 인덱스 반영
- 상태:
  - `Precedent.processing_status`
- 비동기 처리:
  - 판례 인덱싱은 Celery task로 수행

#### `chat_temp_upload`

- 목적: 채팅 답변 생성 시 일회성 참고 컨텍스트를 확보합니다.
- 인증: 로그인
- 저장:
  - 임시 저장소 또는 메모리 기반 처리
  - 영속 DB 저장 없음
- 상태:
  - 세션 범위 임시 상태만 관리
- 비동기 처리:
  - 별도 장기 보관/요약 파이프라인 없음

## 2. Auth API

### POST `/api/auth/signup`

- 설명: 회원가입
- 요청:

```json
{
  "username": "홍길동",
  "email": "user@example.com",
  "password": "password1234"
}
```

- 성공 응답:
  - `201 Created`
  - 본문 없음
- 전제 조건:
  - Redis의 `email_verified:{email}` 값이 있어야 함

### POST `/api/auth/login`

- 설명: 로그인
- 요청:

```json
{
  "email": "user@example.com",
  "password": "password1234"
}
```

- 성공 응답:

```json
{
  "id": 1,
  "email": "user@example.com",
  "username": "홍길동",
  "role": "GENERAL",
  "is_active": true,
  "created_at": "2026-03-13T10:00:00"
}
```

- 부가 동작:
  - `access_token`, `refresh_token` 쿠키 설정
  - 로그인 실패 횟수 Redis 기록

### POST `/api/auth/refresh`

- 설명: 액세스 토큰 / 리프레시 토큰 재발급
- 요청 바디: 없음
- 성공 응답: 로그인 응답과 동일한 `UserResponse`

### POST `/api/auth/logout`

- 설명: 로그아웃
- 요청 바디: 없음
- 성공 응답:
  - `204 No Content`

### GET `/api/auth/me`

- 설명: 현재 로그인 사용자 조회
- 인증: 필요
- 성공 응답: 로그인 응답과 동일

### POST `/api/auth/confirm-account`

- 설명: 이메일 인증 후 가입 계정 확인
- 요청:

```json
{
  "email": "user@example.com"
}
```

- 성공 응답:

```json
{
  "email": "user@example.com",
  "username": "홍길동",
  "message": "가입된 계정 정보가 확인되었습니다."
}
```

### POST `/api/auth/reset-password`

- 설명: 비밀번호 재설정
- 요청:

```json
{
  "email": "user@example.com",
  "new_password": "newPassword1234"
}
```

- 성공 응답:

```json
{
  "message": "비밀번호가 성공적으로 변경되었습니다."
}
```

### PATCH `/api/auth/username`

- 설명: 닉네임 변경
- 인증: 필요
- 요청:

```json
{
  "username": "새닉네임"
}
```

- 성공 응답:

```json
{
  "username": "새닉네임"
}
```

- 현재 구현 기준:
  - 중복 닉네임이면 `USER_USERNAME_ALREADY_EXISTS`

## 3. Email API

### POST `/api/email/send-verification-code`

- 설명: 이메일 인증번호 발송
- 요청:

```json
{
  "email": "user@example.com"
}
```

- 성공 응답:

```json
{
  "message": "인증 코드가 발송되었습니다."
}
```

### POST `/api/email/verify-code`

- 설명: 인증번호 확인
- 요청:

```json
{
  "email": "user@example.com",
  "code": "123456"
}
```

- 성공 응답:

```json
{
  "message": "인증이 완료되었습니다."
}
```

- 부가 동작:
  - `email_verify:{email}` 삭제
  - `email_verified:{email}` 600초 저장

## 4. Document API

### POST `/api/documents/upload-session`

- 설명: 업로드 세션 생성
- 인증: 필요
- 요청:

```json
{
  "file_names": ["판례1.pdf", "판례2.pdf"]
}
```

- 성공 응답:

```json
{
  "items": [
    {
      "file_name": "판례1.pdf",
      "status": "waiting",
      "doc_id": null,
      "summary": null,
      "error": null,
      "updated_at": "2026-03-13T10:00:00+00:00"
    }
  ],
  "is_running": false,
  "started_at": "2026-03-13T10:00:00+00:00",
  "abandoned_at": null
}
```

### GET `/api/documents/upload-session`

- 설명: 현재 사용자 업로드 세션 조회
- 인증: 필요
- 성공 응답: 업로드 세션 생성 응답과 동일

### POST `/api/documents/upload-session/abandon`

- 설명: 업로드 세션 중 대기 상태 항목을 실패 처리
- 인증: 필요
- 성공 응답: 업로드 세션 조회 응답과 동일

### DELETE `/api/documents/upload-session`

- 설명: 업로드 세션 삭제
- 인증: 필요
- 성공 응답:
  - `204 No Content`

### POST `/api/documents/upload`

- 설명: 워크스페이스 문서 PDF 1건 업로드 후 백그라운드 요약 시작
- 인증: 필요
- 권한:
  - 그룹의 `OWNER`, `ADMIN`, `EDITOR`
- 요청 형식: `multipart/form-data`
- 필드:
  - `file`: PDF 파일 1개
  - `group_id`: 업로드 대상 워크스페이스 ID
- 제약:
  - `application/pdf`만 허용
  - 최대 20MB
- 처리 순서:
  1. 파일 저장
  2. `documents` row를 `PENDING` 상태로 생성
  3. 업로드 세션을 `processing`으로 갱신
  4. Celery task enqueue
  5. worker가 OCR/요약 후 `DONE` 또는 `FAILED` 반영
- 성공 응답:

```json
{
  "message": "업로드 중",
  "document_ids": [101]
}
```

- 비고:
  - 이 API는 `group_document_upload` 전용입니다.
  - 채팅 임시 파일 업로드와 판례 업로드는 별도 파이프라인으로 관리합니다.

### GET `/api/documents`

- 설명: 문서 목록 조회
- 인증: 필요
- 쿼리 파라미터:
  - `skip`
  - `limit`
  - `keyword`
  - `status`
  - `view_type`
  - `category`
- 성공 응답:

```json
{
  "items": [
    {
      "id": 101,
      "summary_id": 1,
      "title": "대법원 2023다12345",
      "preview": "요약 미리보기",
      "status": "DONE",
      "created_at": "2026-03-13T10:00:00",
      "court_name": "대법원",
      "judgment_date": "2023-10-01",
      "uploader": "홍길동"
    }
  ],
  "total": 12
}
```

### GET `/api/documents/{doc_id}`

- 설명: 문서 상세 조회
- 인증: 필요
- 성공 응답:

```json
{
  "id": 101,
  "uploader": "홍길동",
  "summary_id": 1,
  "status": "DONE",
  "document_type": "판결문",
  "summary_text": "이 문서는 손해배상 청구 사건의 경과와 쟁점을 정리한 판결문이다.",
  "key_points": [
    "손해배상 책임 성립 여부가 핵심 쟁점이다.",
    "증거 관계와 인과관계 판단이 중요하게 다뤄진다."
  ],
  "metadata": {
    "source": "group_document_summary"
  },
  "created_at": "2026-03-13T10:00:00"
}
```

### DELETE `/api/documents/{doc_id}`

- 설명: 문서 삭제
- 인증: 필요
- 권한:
  - 업로더 본인
  - 관리자
- 성공 응답:
  - `204 No Content`

## 5. Summary API

### GET `/api/summaries/{summary_id}/download`

- 설명: 요약 PDF 다운로드
- 인증: 필요
- 성공 응답:
  - `application/pdf`
  - 첨부 다운로드 헤더 포함

## 6. Admin API 초안

어드민은 고객 워크스페이스 내부 운영에 직접 개입하지 않고, 플랫폼 운영 및 RAG용 판례 데이터베이스를 관리합니다.

### GET `/api/admin/stats`

- 설명: 관리자 대시보드 핵심 지표 조회
- 인증: 필요
- 권한: `ADMIN`
- 성공 응답 예시:

```json
{
  "total_users": 1284,
  "premium_users": 236,
  "premium_conversion_rate": 18.4,
  "active_groups": 142,
  "ai_success_rate": 97.2
}
```

### GET `/api/admin/usage`

- 설명: 저장소/AI 처리량 통계 조회
- 인증: 필요
- 권한: `ADMIN`
- 성공 응답 예시:

```json
{
  "service_usage": {
    "storage": {
      "used_gb": 84.3,
      "limit_gb": 200
    },
    "daily_uploads": [
      { "date": "2026-03-10", "count": 43 },
      { "date": "2026-03-11", "count": 58 }
    ],
    "document_jobs": {
      "DONE": 92,
      "PROCESSING": 5,
      "FAILED": 3
    }
  },
  "rag_usage": {
    "precedent_count": 24381,
    "vector_storage_mb": 12840,
    "index_jobs": {
      "DONE": 24195,
      "PROCESSING": 186,
      "FAILED": 54
    }
  }
}
```

### GET `/api/admin/users`

- 설명: 사용자 목록 조회
- 인증: 필요
- 권한: `ADMIN`
- 성공 응답 예시:

```json
{
  "items": [
    {
      "id": 1,
      "username": "김대표",
      "email": "daeyo@abclaw.kr",
      "role": "GENERAL",
      "is_active": true,
      "plan": "PREMIUM",
      "active_group_count": 1,
      "created_at": "2026-03-13T10:00:00"
    }
  ],
  "total": 1284
}
```

### PATCH `/api/admin/users/{user_id}`

- 설명: 사용자 상태 변경
- 인증: 필요
- 권한: `ADMIN`
- 요청 예시:

```json
{
  "is_active": false
}
```

### DELETE `/api/admin/users/{user_id}`

- 설명: 사용자 삭제
- 인증: 필요
- 권한: `ADMIN`
- 성공 응답:
  - `204 No Content`

### GET `/api/admin/precedents`

- 설명: RAG용 판례 메타 및 처리 상태 목록 조회
- 인증: 필요
- 권한: `ADMIN`
- 성공 응답 예시:

```json
{
  "items": [
    {
      "id": 15,
      "source_url": "https://example.com/cases/2023da12345",
      "title": "대법원 2023다12345 손해배상(기)",
      "processing_status": "DONE",
      "error_message": null,
      "uploaded_by_admin_id": 3,
      "created_at": "2026-03-15T10:00:00",
      "updated_at": "2026-03-15T10:03:00"
    }
  ],
  "total": 24381
}
```

### POST `/api/admin/precedents`

- 설명: 지원된 도메인의 판례 URL 등록
- 인증: 필요
- 권한: `ADMIN`
- 요청 예시:

```json
{
  "source_url": "https://example.com/cases/2023da12345"
}
```

- 부가 동작:
  - `precedents` row 생성
  - URL 기준 메타 추출 및 벡터화 파이프라인 시작
  - 동일한 `source_url`은 중복 등록 불가

### POST `/api/admin/precedents/{precedent_id}/retry`

- 설명: 실패한 판례 인덱싱 재처리
- 인증: 필요
- 권한: `ADMIN`
- 부가 동작:
  - 기존 row 재사용
  - `processing_status`를 다시 갱신하여 파이프라인 재실행
  - 새 row를 생성하지 않음

### POST `/api/admin/precedents/reindex`

- 설명: RAG 인덱스 재생성 실행
- 인증: 필요
- 권한: `ADMIN`
- 요청 바디: 추후 범위 지정 옵션 추가 가능
- 성공 응답:
  - 작업 시작 정보 또는 `202 Accepted`

## 7. 현재 구현 기준 메모

- 관리자 전용 API는 현재 별도 라우터로 구현되어 있지 않습니다.
- 회원탈퇴 API는 현재 문서 범위에서 구현되어 있지 않습니다.
- 업로드 세션 관련 계약은 Redis 기반 복구 기능을 포함합니다.
- 문서 목록의 keyword 검색 조건은 summary가 없는 문서 동작을 별도 점검하는 것이 좋습니다.
