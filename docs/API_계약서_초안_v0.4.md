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

- 설명: PDF 1건 업로드 후 백그라운드 요약 시작
- 인증: 필요
- 요청 형식: `multipart/form-data`
- 필드:
  - `file`: PDF 파일 1개
- 제약:
  - `application/pdf`만 허용
  - 최대 20MB
- 성공 응답:

```json
{
  "message": "업로드 중",
  "document_ids": [101]
}
```

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
  "case_number": "2023다12345",
  "case_name": "손해배상(기)",
  "court_name": "대법원",
  "judgment_date": "2023-10-01",
  "summary_title": "손해배상 청구 사건 요약",
  "summary_main": "본 사건은 ...",
  "plaintiff": "홍길동",
  "defendant": "김철수",
  "facts": "사실관계 ...",
  "judgment_order": "피고는 ...",
  "judgment_reason": "증거에 따르면 ...",
  "related_laws": "민법 제750조",
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

## 6. 현재 구현 기준 메모

- 관리자 전용 API는 현재 별도 라우터로 구현되어 있지 않습니다.
- 회원탈퇴 API는 현재 문서 범위에서 구현되어 있지 않습니다.
- 업로드 세션 관련 계약은 Redis 기반 복구 기능을 포함합니다.
- 문서 목록의 keyword 검색 조건은 summary가 없는 문서 동작을 별도 점검하는 것이 좋습니다.
