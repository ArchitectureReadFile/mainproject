# 지윤

법률 문서 검토, 승인 문서 검색, 플랫폼 지식 검색, 채팅형 질의응답을 하나의 워크스페이스 흐름으로 묶은 서비스입니다.

## 핵심 구성

- Frontend: React, Vite
- Backend API: FastAPI, SQLAlchemy
- Async: Celery, Redis
- Storage: MariaDB, Qdrant, BM25
- AI: ODL Hybrid, Ollama 또는 외부 OpenAI-compatible API
- Infra: Docker Compose, Nginx, Cloudflare Tunnel

## 빠른 시작

### 1. 환경변수 준비

```bash
cp backend/.env.example backend/.env
```

`backend/.env`에는 최소 아래 값이 있어야 합니다.

- `DATABASE_URL`
- `MARIADB_ROOT_PASSWORD`
- `MARIADB_DATABASE`
- `MARIADB_USER`
- `MARIADB_PASSWORD`
- `JWT_SECRET_KEY`

### 2. 로컬 개발 실행

기본 서비스:

```bash
docker compose up -d --build
```

비동기 worker까지 포함한 개발 실행:

```bash
docker compose --profile dev up -d --build
```

또는 이미 기본 서비스가 떠 있다면 worker만 추가로 실행합니다.

```bash
docker compose --profile dev up -d celery_worker
```

### 3. 확인 포인트

- `backend_migrate_container`는 정상일 때 `Exited (0)`입니다.
- `backend_container`, `celery_beat_container`는 `Up`이어야 합니다.
- 로컬 개발에서 비동기 처리가 필요하면 `celery_worker_container`도 `Up`이어야 합니다.

### 4. 접속 주소

| 서비스 | 주소 |
| --- | --- |
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger | http://localhost:8000/docs |
| phpMyAdmin | http://localhost:5050 |

## 실행 구조

### 로컬 개발

- `docker-compose.yml` 단독 사용
- `backend_migrate` one-shot 실행 후 backend/beat/worker 기동
- `celery_worker`는 `dev` profile에 포함
- `backend`는 reload 모드

### 서버 운영

- `docker-compose.yml` + `docker-compose.server.yml` overlay 사용
- `backend_migrate` 성공 이후 backend/worker들이 시작
- worker는 역할별로 분리
  - `chat_worker`
  - `chat_reference_worker`
  - `document_worker`
  - `export_worker`
  - `platform_worker`
  - `platform_sync_worker`
  - `maintenance_worker`

## 현재 구조 기준 핵심 규칙

- 문서는 업로드 후 추출/정규화/분류/요약을 거칩니다.
- 승인된 문서만 검색 인덱스 대상입니다.
- 세션 첨부 문서는 `reference-upload` 비동기 경로로만 처리합니다.
- 플랫폼 지식의 source of truth는 `platform_documents` 계층입니다.
- DB 스키마는 앱 시작 시 자동 생성되지 않고 Alembic migration으로 관리합니다.

## 문서 안내

- [문서 인덱스](/Users/ijiyun/team/docs/README.md)
- [배포 문서](/Users/ijiyun/team/docs/deploy.md)
- [운영자 매뉴얼](/Users/ijiyun/team/docs/11_운영자매뉴얼.md)
- [백엔드 아키텍처](/Users/ijiyun/team/backend/docs/ARCHITECTURE.md)
- [ERD](/Users/ijiyun/team/docs/04_ERD.md)
- [프로그램 목록](/Users/ijiyun/team/docs/05_프로그램목록.md)

## 저장소 구조

```text
team/
├── frontend/                  # React UI
├── backend/                   # API, domains, async tasks
├── deploy/                    # nginx / cloudflared 설정
├── docs/                      # 사용자/운영/설계 문서
├── docker-compose.yml         # 로컬 개발 기본 구성
└── docker-compose.server.yml  # 서버 운영 overlay
```

## 주의사항

- 운영 시크릿은 저장소 밖 env 파일에서 관리합니다.
- `backend_migrate`는 계속 떠 있는 서비스가 아니라 migration job입니다.
- `backend_migrate_container`가 `Exited (0)`이면 정상입니다.
- 로컬에서 worker를 안 올리면 채팅/문서 비동기 처리가 수행되지 않습니다.
