# Backend

## Run
```bash
uvicorn main:app --reload
```

## Auth env
- `JWT_SECRET_KEY`: JWT 서명 키
- `JWT_ALGORITHM`: 기본값 `HS256`
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`: 토큰 만료(분), 기본값 `60`
- `CORS_ALLOW_ORIGINS`: 허용할 프론트 오리진(쉼표 구분)
- `LOGIN_RATE_LIMIT_MAX_ATTEMPTS`: 로그인 최대 실패 횟수
- `LOGIN_RATE_LIMIT_WINDOW_SECONDS`: 로그인 실패 집계 시간(초)
- `LOGIN_RATE_LIMIT_BLOCK_SECONDS`: 제한 시간(초)

## Auth APIs
- `POST /api/auth/signup`
- `POST /api/auth/login`
- `GET /api/auth/me` (Authorization: `Bearer <token>`)
