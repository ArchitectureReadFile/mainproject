# 판례 AI 플랫폼

법률 특화 AI 자문관 서비스. 챗봇으로 판례를 검색하고, 워크스페이스에서 문서를 업로드해 AI 요약을 활용한다.

---

## 기술 스택

| 영역       | 기술                                |
| ---------- | ----------------------------------- |
| 프론트엔드 | React 19, Vite, Tailwind CSS v4     |
| 백엔드     | FastAPI, SQLAlchemy, MariaDB, Redis |
| AI         | Ollama (EXAONE), ChromaDB (RAG)     |
| 인프라     | Docker, Nginx                       |

---

## 시작하기

### 사전 요구사항

- Docker & Docker Compose
- Node.js 18+

---

### 1. 저장소 클론

```bash
git clone <repo-url>
cd team
```

---

### 2. 환경변수 설정

```bash
cp backend/.env.example backend/.env
# backend/.env 파일 열어서 값 설정
```

---

### 3. Docker 실행

```bash
docker compose up -d
```

---

### 4. Ollama 설정

**Docker로 실행하는 경우** `docker-compose.yml`에서 ollama 서비스 주석 해제 후:

```bash
docker compose up -d ollama
```

**로컬에서 직접 실행하는 경우** (호스트 머신에 Ollama 설치 필요):

```bash
ollama serve
ollama pull exaone3.5:7.8b
```

> `OLLAMA_HOST=http://host.docker.internal:11434` 설정이 되어 있으므로 로컬 실행 시 별도 설정 불필요

---

### 5. 접속

| 서비스             | URL                        |
| ------------------ | -------------------------- |
| 프론트엔드         | http://localhost:5173      |
| 백엔드 API         | http://localhost:8000      |
| API 문서 (Swagger) | http://localhost:8000/docs |
| phpMyAdmin         | http://localhost:5050      |

---

## 개발 환경 세팅 (팀원 공통)

### 프론트엔드

```bash
cd frontend
npm install
npm run dev
```

### 백엔드 (로컬 직접 실행 시)

```bash
cd backend
pip install -r requirements.txt --break-system-packages
uvicorn main:app --reload
```

### 코드 품질 도구 설치 (최초 1회)

커밋 전 자동으로 lint 검사가 실행된다.

```bash
# 개발 도구 설치
pip install -r backend/requirements-dev.txt --break-system-packages

# pre-commit hook 등록 (프로젝트 루트에서)
pre-commit install
```

설치 후 커밋할 때마다 자동으로 아래가 실행된다.

- 프론트: ESLint (React, Hooks 규칙 검사)
- 백엔드: Ruff (lint + format 검사)

수동으로 실행하려면:

```bash
# 프론트
cd frontend && npm run lint
cd frontend && npm run lint:fix   # 자동 수정

# 백엔드
cd backend && ruff check .
cd backend && ruff format .       # 자동 수정

# 전체 한번에
pre-commit run --all-files
```

---

## 브랜치 전략

```
main
└── dev
    ├── feat/jiyun    # 이지윤  — AI 모델 + RAG
    ├── feat/insu     # insuJu  — 챗봇 + 랜딩
    ├── feat/leeseul  # 이슬님  — 워크스페이스 + 문서
    └── feat/lhj      # 혜지님  — 마이페이지 + 어드민
```

- PR은 항상 `feat/* → dev` 로
- `dev → main` 은 배포 시에만

---

## 역할 분담

| 담당   | 영역                                                               |
| ------ | ------------------------------------------------------------------ |
| 이지윤 | AI 모델 (EXAONE QLoRA 파인튜닝), 판례 데이터 수집, ChromaDB 벡터화 |
| insuJu | 랜딩 UX, 챗봇 UI, `chat` API                                       |
| 이슬님 | 워크스페이스, 문서 업로드/목록/상세, `group` API                   |
| 혜지님 | 마이페이지, 알림, 어드민, `notification` API                       |

---

## 폴더 구조

```
team/
├── backend/
│   ├── routers/       # API 엔드포인트
│   ├── services/      # 비즈니스 로직
│   │   ├── summary/   # AI 요약 파이프라인
│   │   └── rag/       # RAG 파이프라인 (ChromaDB)
│   ├── repositories/  # DB 쿼리
│   ├── schemas/       # 요청/응답 스키마
│   ├── models/        # DB 모델
│   └── prompts/       # LLM 프롬프트
│
└── frontend/src/
    ├── features/      # 도메인별 기능
    │   ├── auth/
    │   ├── chat/
    │   ├── workspace/
    │   ├── document/
    │   ├── upload/
    │   └── notification/
    ├── pages/         # 라우트 1:1 매핑
    ├── components/    # 공용 컴포넌트
    └── lib/           # Axios, 에러 처리
```
