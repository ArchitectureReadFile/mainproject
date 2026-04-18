# 배포 문서

## 1. 개요

이 프로젝트는 두 단계 compose 구조를 사용합니다.

- 로컬 개발: `docker-compose.yml`
- 서버 운영: `docker-compose.yml` + `docker-compose.server.yml`

DB 스키마는 앱 시작 시 자동 생성되지 않습니다.
항상 `backend_migrate` one-shot 서비스가 먼저 실행되고, 성공 후 backend/worker가 올라갑니다.

## 2. 로컬 개발 실행

### 2.1 사전 준비

```bash
cp backend/.env.example backend/.env
```

`backend/.env`에는 최소 아래 값이 필요합니다.

- `DATABASE_URL`
- `MARIADB_ROOT_PASSWORD`
- `MARIADB_DATABASE`
- `MARIADB_USER`
- `MARIADB_PASSWORD`
- `JWT_SECRET_KEY`

### 2.2 기본 실행

```bash
docker compose up -d --build
```

이 명령은 아래를 올립니다.

- db
- redis
- qdrant
- backend_migrate
- backend
- celery_beat
- frontend
- phpmyadmin
- odl_hybrid

### 2.3 worker 포함 실행

로컬에서 채팅/문서 비동기 처리가 필요하면 `dev` profile worker를 같이 띄웁니다.

```bash
docker compose --profile dev up -d --build
```

이미 기본 서비스가 떠 있다면 worker만 추가해도 됩니다.

```bash
docker compose --profile dev up -d celery_worker
```

### 2.4 정상 상태

```bash
docker compose ps -a
```

정상 예시:

- `backend_migrate_container` → `Exited (0)`
- `backend_container` → `Up`
- `celery_beat_container` → `Up`
- `celery_worker_container` → `Up` 또는 로컬에서 worker를 안 띄웠다면 없음

## 3. 서버 운영 구조

서버는 overlay compose를 사용합니다.

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml up -d --remove-orphans
```

운영 overlay에서 달라지는 점:

- production image 사용
- `D:/jiyun-env/backend.env` 외부 env 사용
- `backend_migrate` 선행 실행
- worker를 역할별로 분리
- nginx / cloudflared 사용

## 4. 운영 서비스 구성

### 4.1 backend 계열

- `backend_migrate`
- `backend`
- `celery_beat`
- `chat_worker`
- `chat_reference_worker`
- `document_worker`
- `export_worker`
- `platform_worker`
- `platform_sync_worker`
- `maintenance_worker`

### 4.2 공통 인프라

- `db`
- `redis`
- `qdrant`
- `odl_hybrid`

### 4.3 프록시 계열

- `frontend`
- `nginx`
- `cloudflared`

## 5. migration 규칙

### 5.1 기본 원칙

- 앱은 `create_all()`로 스키마를 만들지 않습니다.
- Alembic revision만 신뢰합니다.
- compose는 `backend_migrate` 성공 후 backend/worker를 올립니다.

### 5.2 수동 실행

필요하면 backend 실행 환경에서 수동으로 migration을 적용합니다.

```bash
cd backend
alembic upgrade head
```

### 5.3 기존 pre-Alembic DB

기존 스키마가 이미 있는데 `alembic_version`이 없거나 비어 있는 DB는
`backend_migrate`가 현재 스키마를 `head`로 stamp합니다.

즉 아래 상태는 정상입니다.

- 앱 테이블 존재
- `backend_migrate` 실행
- `Detected pre-Alembic schema. Stamping current schema to head.`

## 6. 서버 env 파일

운영 env는 repo 밖 경로에 둡니다.

```text
D:/jiyun-env/backend.env
```

최소 핵심 값:

```env
DATABASE_URL=mysql+pymysql://user:PASSWORD@db:3306/readfile
MARIADB_ROOT_PASSWORD=CHANGE_ME
MARIADB_DATABASE=readfile
MARIADB_USER=user
MARIADB_PASSWORD=CHANGE_ME
JWT_SECRET_KEY=CHANGE_ME
REDIS_HOST=redis
QDRANT_HOST=qdrant
ODL_HYBRID_URL=http://odl_hybrid:5002
```

## 7. 장애 확인 순서

### 7.1 backend가 안 뜰 때

1. `db` health 확인
2. `backend_migrate_container` exit code 확인
3. `backend_migrate_container` 로그 확인
4. `backend_container` 로그 확인

### 7.2 worker가 안 뜰 때

로컬:
- `celery_worker`는 `dev` profile입니다.
- `docker compose --profile dev up -d celery_worker`

서버:
- overlay worker 서비스별 상태 확인
  - `chat_worker`
  - `document_worker`
  - `export_worker`
  - `platform_worker`
  - `platform_sync_worker`
  - `maintenance_worker`

### 7.3 검색/채팅이 안 될 때

1. `redis`, `qdrant` 상태 확인
2. worker 상태 확인
3. `odl_hybrid` 상태 확인
4. backend 로그에서 retrieval/llm 오류 확인

## 8. 운영 체크리스트

- `backend_migrate_container`가 `Exited (0)`인지 확인
- backend와 필요한 worker가 모두 떠 있는지 확인
- `backend/.env` 또는 운영 env 파일에 MariaDB 비밀번호가 하드코딩되지 않았는지 확인
- 채팅 첨부는 `reference-upload` 비동기 경로만 사용하는지 확인
- 승인된 문서만 인덱싱되는지 확인
