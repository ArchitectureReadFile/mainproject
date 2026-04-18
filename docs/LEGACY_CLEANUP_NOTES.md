# Legacy Cleanup Notes

## 기준

- source of truth가 하나로 수렴하지 않는 경로는 제거한다.
- 런타임에서 더 이상 생성되지 않는 타입/필드는 제거한다.
- 테스트만을 위해 남은 호환 분기는 실제 런타임 계약에 맞춰 축소한다.
- dead file은 참조가 없으면 삭제한다.

## 2026-04-18 점검 결과

### 제거 완료

- precedent legacy read/task/index path
- `Precedent` ORM model
- precedent 전용 BM25/Qdrant helper

### 즉시 제거 가능

- `ExtractedDocument.source_type="ocr"` 호환 분기
  - 현재 런타임 생성 경로는 `odl`뿐이다.
  - `ocr`는 normalize 테스트와 주석에만 남아 있다.

- `extractors/taxlaw_precedent.py`
  - repo 내 참조 없음
  - precedent source of truth를 platform corpus로 통합한 뒤 역할이 사라짐

### 유지

- platform knowledge 5-table 구조
  - raw / normalized / chunks / sync runs / sync failures
  - 테이블 수보다 책임 분리가 중요하고, 현재는 과분해가 아님

### 후속 검토

- 기존 로컬 DB에 남아 있을 수 있는 `precedents` 물리 테이블 수동 정리
- `DocumentSchema`/normalize 설명 문구에서 OCR 표현 전반 제거 여부 재점검
