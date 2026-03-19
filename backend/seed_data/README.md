# Seed Data Guide

## 현재 사용하는 파일

- `taxlaw_precedent_urls_10000.json`
  - precedent 원본 raw 데이터 저장본
- `precedent_batch_config.py`
  - 현재 활성 precedent 배치 번호 설정
- `precedent_sources.py`
  - 활성 배치를 import 하는 진입점
- `batches/precedent_sources_batch_*.py`
  - 1000건 단위 precedent seed 데이터

## 사용 흐름

1. `taxlaw_precedent_urls_10000.json` 수집
2. `generate_precedent_sources.py` 로 seed 형태 변환
3. `generate_precedent_source_batches.py` 로 1000건 배치 생성
4. `precedent_batch_config.py` 의 `ACTIVE_PRECEDENT_BATCH` 값을 바꿔가며 seed 실행
