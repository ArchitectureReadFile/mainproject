# 지윤

법률 문서 업무를 위한 워크스페이스형 AI 서비스입니다.  
문서를 업로드해 검토하고, AI 요약과 검색을 활용하며, 법률 지식을 바탕으로 채팅할 수 있습니다.

## 소개

이 프로젝트는 아래 흐름을 하나의 서비스로 묶는 것을 목표로 합니다.

- 문서 업로드와 협업 검토
- AI 기반 문서 요약
- 승인 문서 기반 검색
- 법령·판례 등 플랫폼 지식 검색
- 채팅형 질의응답

## 핵심 기능

- 워크스페이스 생성, 멤버 초대, 권한 기반 협업
- 문서 업로드, 검토, 승인/반려
- AI 문서 요약
- 승인 문서 기반 RAG 검색
- 법률 지식 검색과 채팅
- 관리자용 운영 현황 및 플랫폼 최신화

## 시스템 구성

### 사용자 영역

- Frontend: 사용자 화면, 관리자 화면, 채팅 UI
- Backend API: 인증, 문서, 워크스페이스, 관리자 기능

### 비동기 처리 영역

- Celery: 문서 처리, 채팅 처리, 플랫폼 최신화 등 백그라운드 작업
- Redis: Celery broker / websocket pub-sub

### 데이터 영역

- MariaDB: 서비스 데이터 저장
- Qdrant: 벡터 검색
- BM25 저장소: 텍스트 검색 보조

### AI / 검색 영역

- Ollama 기반 LLM 호출
- 플랫폼 지식과 워크스페이스 문서를 함께 사용하는 검색/답변 흐름

## 기술 스택

| 영역 | 기술 |
| --- | --- |
| Frontend | React, Vite, Tailwind CSS |
| Backend | FastAPI, SQLAlchemy |
| Async | Celery, Redis |
| Database | MariaDB |
| Search | Qdrant, BM25 |
| AI | Ollama |
| Infra | Docker, Nginx, Cloudflare Tunnel |

## 빠른 시작

### 사전 요구사항

- Docker / Docker Compose
- Node.js
- Python

### 저장소 클론

```bash
git clone <repo-url>
cd team
```

### 환경변수 준비

```bash
cp backend/.env.example backend/.env
```

환경값은 실행 환경에 맞게 수정합니다.

### 로컬 실행

```bash
docker compose up -d
```

기본 접속 주소:

| 서비스 | 주소 |
| --- | --- |
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger | http://localhost:8000/docs |
| phpMyAdmin | http://localhost:5050 |

## 로컬 개발

로컬 개발 환경은 빠른 반복 작업을 위한 구성을 사용합니다.

- frontend: Vite dev server
- backend: reload 모드
- worker: 단일 Celery worker
- 로컬 AI/검색 자원은 compose 기반으로 함께 실행 가능

세부 실행 방법과 운영 차이는 아래 문서를 참고합니다.

- [배포 문서](/Users/ijiyun/team/docs/deploy.md)
- [백엔드 아키텍처](/Users/ijiyun/team/backend/docs/ARCHITECTURE.md)

## 서버 운영 개요

서버는 로컬과 달리 운영용 compose overlay를 사용합니다.

- production image 기반 실행
- 외부 운영 env 파일 사용
- nginx / cloudflared 사용
- 비동기 worker를 역할별로 분리할 수 있음

자세한 내용은 [docs/deploy.md](/Users/ijiyun/team/docs/deploy.md)를 참고합니다.

## 주요 도메인 규칙

- 업로드 문서는 검토 흐름을 거칩니다.
- 승인된 문서만 검색 인덱싱 대상이 됩니다.
- AI 결과는 사용자 검토를 전제로 합니다.
- 관리자 기능과 운영성 기능은 일반 사용자 기능과 구분됩니다.

## 저장소 구조

```text
team/
├── frontend/              # 사용자/관리자 UI
├── backend/               # API, 도메인 로직, 비동기 작업
├── deploy/                # 배포용 nginx 등 인프라 설정
├── docs/                  # 운영/배포 문서
├── docker-compose.yml
└── docker-compose.server.yml
```

## 참고 문서

- [배포 문서](/Users/ijiyun/team/docs/deploy.md)
- [백엔드 아키텍처](/Users/ijiyun/team/backend/docs/ARCHITECTURE.md)
- [백엔드 README](/Users/ijiyun/team/backend/README.md)
- [프론트엔드 README](/Users/ijiyun/team/frontend/README.md)

## 주의사항

- 운영 시크릿은 저장소 밖 환경변수 파일로 관리합니다.
- 로컬 환경과 서버 환경은 구성과 의존성이 다를 수 있습니다.
- 배포 시에는 이미지 재빌드/재배포 여부를 함께 확인합니다.
