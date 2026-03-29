# 서버 배포 절차

## 구조 개요

```
jiyun.dev
  └─ Cloudflare Tunnel (cloudflared)
       └─ nginx:80
            ├─ /api/  → backend:8000
            ├─ /ws    → backend:8000 (WebSocket)
            └─ /      → frontend:3000
```

개발 환경은 `docker-compose.yml` 단독 사용으로 그대로 유지된다.  
서버 배포는 `docker-compose.server.yml`을 overlay로 추가한다.

---

## 파일 구조

```
team/
├── docker-compose.yml              # 개발용 기본 (변경 없음)
├── docker-compose.override.yml     # 개발 편의용 (변경 없음)
├── docker-compose.server.yml       # 서버 배포 overlay (서버에서만 사용)
├── deploy/
│   ├── nginx/nginx.conf            # 서버용 reverse proxy 설정
│   └── cloudflared/config.yml      # Cloudflare Tunnel 설정 템플릿
├── frontend/
│   └── Dockerfile.prod             # 프로덕션 빌드용
├── backend/
│   └── Dockerfile.prod             # 프로덕션 실행용
└── .github/workflows/
    ├── ci.yml                      # lint/build 검증
    └── deploy.yml                  # Docker Hub 푸시 + 홈서버 배포

# 서버 로컬 (repo 밖, gitignore/checkout 영향 없음)
D:\jiyun-env\
└── backend.env                     # 운영 환경변수 (시크릿 포함)
```

---

## 네트워크 구조

서버 배포 시 모든 서비스는 `app-network` 단일 브리지 네트워크에 속한다.  
`docker-compose.server.yml`에서 db, redis, qdrant를 포함한 전 서비스에 `app-network`를 명시해  
서비스명(`db`, `redis`, `qdrant`, `backend` 등)으로 상호 통신이 보장된다.

```
app-network (bridge)
  ├─ frontend
  ├─ backend        → db, redis, qdrant 서비스명으로 접근
  ├─ celery_worker  → db, redis, qdrant 서비스명으로 접근
  ├─ db
  ├─ redis
  ├─ qdrant
  ├─ nginx
  └─ cloudflared
```

ollama, phpmyadmin은 서버에서 실행하지 않는다 (`profiles: dev-only`).

---

## Ollama 서버 운영 방침

서버(집 컴퓨터)에서는 **ollama 컨테이너를 띄우지 않는다.**  
`docker-compose.server.yml`에서 ollama를 `profiles: dev-only`로 비활성화한다.

서버에서 LLM 추론이 필요한 경우 아래 중 하나를 선택한다.

| 방법 | `OLLAMA_HOST` 값 예시 |
|------|----------------------|
| 개발 PC의 ollama를 ngrok으로 노출 | `https://xxxx.ngrok.io` |
| 별도 외부 Ollama 서버 | `http://<IP>:11434` |
| 외부 OpenAI-compatible API | 별도 설정 |

`D:\jiyun-env\backend.env`에서 아래와 같이 지정한다:

```env
# 서버용: ollama 컨테이너 없이 외부 엔드포인트 직접 지정
OLLAMA_HOST=https://xxxx.ngrok.io   # ngrok 사용 시
# 또는
OLLAMA_HOST=http://192.168.0.10:11434  # 로컬 네트워크 내 다른 PC
```

개발 환경에서는 `docker-compose.yml`의 ollama 서비스가 그대로 동작한다.

---

## 최초 서버 셋업

### 1. 운영 env 파일 생성 (repo 밖 경로, Windows 기준)

운영 환경변수는 **repo 내부가 아닌 서버 로컬 고정 경로**에 둔다.  
`actions/checkout`은 repo 디렉토리만 건드리므로, 이 경로는 deploy 시 절대 삭제되지 않는다.

```powershell
New-Item -ItemType Directory -Force D:\jiyun-env
notepad D:\jiyun-env\backend.env
```

`D:\jiyun-env\backend.env` 주요 항목 (`backend/.env.server` 템플릿 전체 참고):

```env
DATABASE_URL=mysql+pymysql://user:PASSWORD@db:3306/readfile
JWT_SECRET_KEY=CHANGE_ME_STRONG_SECRET
CORS_ALLOW_ORIGINS=https://jiyun.dev
REDIS_HOST=redis
REDIS_PORT=6379
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# ollama 컨테이너 없이 외부 엔드포인트 지정
OLLAMA_HOST=https://xxxx.ngrok.io
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_NUM_CTX=8192
OLLAMA_NUM_PREDICT=3072
OLLAMA_TIMEOUT_SECONDS=600
```

### 2. self-hosted runner 등록

GitHub → Settings → Actions → Runners → New self-hosted runner  
집 컴퓨터(Windows/WSL2)에서 지시에 따라 runner 설치 및 등록.

label을 `home-server`로 지정해야 `deploy.yml`이 올바른 runner에서 실행됨.

```powershell
.\run.cmd
# 또는 서비스로 등록
.\svc.cmd install
.\svc.cmd start
```

### 3. GitHub Secrets 등록

GitHub → Settings → Secrets and variables → Actions

| 이름 | 설명 |
|------|------|
| `DOCKER_HUB_USER` | Docker Hub 사용자명 |
| `DOCKER_HUB_TOKEN` | Docker Hub Access Token |
| `CLOUDFLARE_TUNNEL_TOKEN` | Cloudflare Zero Trust 터널 토큰 |

### 4. Cloudflare Tunnel 설정

Cloudflare Zero Trust 대시보드 → Networks → Tunnels → 터널 생성  
토큰을 복사해 GitHub Secret `CLOUDFLARE_TUNNEL_TOKEN`에 등록.

Public Hostname 설정:
- 도메인: `jiyun.dev`
- 서비스: `http://nginx:80`

---

## 배포 흐름

### 자동 배포 (main 브랜치 push 시)

```
main push
  → ci.yml: lint + build 검증
  → deploy.yml job1 (GitHub-hosted):
      docker build backend → Docker Hub push
      docker build frontend → Docker Hub push
  → deploy.yml job2 (self-hosted, home-server):
      git checkout (repo만 갱신, D:\jiyun-env\ 무관)
      D:\jiyun-env\backend.env 존재 확인
      docker compose pull
      docker compose up -d --remove-orphans
```

### 수동 배포 (서버에서 직접)

```powershell
cd D:\mainproject
$env:DOCKER_HUB_USER="<user>"
$env:CLOUDFLARE_TUNNEL_TOKEN="<token>"
docker compose -f docker-compose.yml -f docker-compose.server.yml up -d --remove-orphans
```

---

## 개발 환경 실행 (변경 없음)

```bash
docker compose up -d
```

nginx, cloudflared는 절대 뜨지 않음.

---

## 리뷰 포인트 확인

| 항목 | 상태 |
|------|------|
| `docker compose up` 시 서버용 서비스 미실행 | ✅ nginx/cloudflared는 server.yml에만 정의 |
| 서버용 서비스는 server.yml에서만 켜짐 | ✅ overlay 방식으로만 활성화 |
| nginx/cloudflared가 개발 경로와 분리 | ✅ docker-compose.yml에 없음 |
| frontend가 dev command를 실행하지 않음 | ✅ `command: ["nginx", "-g", "daemon off;"]` 명시 |
| production image CMD만 사용 | ✅ base compose command 상속 차단 |
| 운영 env가 deploy 시 삭제되지 않음 | ✅ `D:\jiyun-env\` (repo 밖 고정 경로) |
| 시크릿과 코드 분리 | ✅ repo checkout 영향 범위 밖 |
| ollama 컨테이너 서버 미실행 | ✅ `profiles: dev-only`로 비활성화 |
| 서버 LLM 연결 방식 명시 | ✅ `OLLAMA_HOST` 외부 엔드포인트 지정 |
| 전 서비스 서비스명 통신 보장 | ✅ db/redis/qdrant 포함 전체 `app-network` 명시 |
| self-hosted runner 배포 경로 명확 | ✅ `runs-on: [self-hosted, home-server]` |
| Docker Hub → home server pull 구조 | ✅ job1 push → job2 pull → up |
| jiyun.dev → Tunnel → nginx → frontend/backend | ✅ cloudflared → nginx:80 → upstream |
