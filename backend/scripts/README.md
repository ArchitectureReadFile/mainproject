# Scripts Guide

현재 유지하는 스크립트는 아래 4개입니다.

## RAG 검증

- `rag_smoke_test.py`
  - 현재 precedent RAG 인덱스의 `dense / hybrid / answer` 결과를 빠르게 점검합니다.

## Precedent 수집

- `collect_taxlaw_precedent_urls.py`
  - `law.go.kr` 최신 판례 목록을 순회하면서, 실제 seed 가능한 `taxlaw.nts.go.kr` URL만 수집합니다.

## Seed 데이터 생성

- `generate_precedent_sources.py`
  - raw precedent 목록을 `topic / url / notes` 형태의 seed 데이터로 변환합니다.

- `generate_precedent_source_batches.py`
  - 변환된 precedent seed 데이터를 1000건 단위 배치 파일로 나눕니다.

## 정리 원칙

- 브라우저 자동화 실험용, 실패한 실행 경로, 중복 기능 스크립트는 유지하지 않습니다.
- precedent seed 경로는 `taxlaw` 기준만 사용합니다.
