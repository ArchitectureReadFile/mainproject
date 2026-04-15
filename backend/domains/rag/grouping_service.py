"""
domains/rag/grouping_service.py

chunk 단위 retrieval 결과를 precedent 단위로 그룹핑한다.

메타 전달 계약:
    vector_store.search() / hybrid_search() → chunk hit dict
    → group_chunks_by_precedent() → precedent-level grouped dict
    → answer_service._build_context() / citation

    _PRECEDENT_META_FIELDS에 선언된 필드는 모두 grouped dict 최상위에 올라온다.
    vector_store._RETRIEVAL_PAYLOAD_FIELDS와 일치해야 한다.
"""

TOP_CHUNKS_PER_PRECEDENT = 2
MIN_SCORE_GAP = 0.05  # 유사 chunk 중복 제거 임계값

# chunk hit에서 precedent 단위로 올릴 메타데이터 필드.
# chunk_builder.PrecedentChunk payload 계약 및
# vector_store._RETRIEVAL_PAYLOAD_FIELDS와 일치해야 한다.
_PRECEDENT_META_FIELDS = (
    "title",
    "source_url",
    "case_number",
    "case_name",
    "court_name",
    "judgment_date",
    "plaintiff",
    "defendant",
    "lower_court_case",
)


def group_chunks_by_precedent(chunk_hits: list[dict]) -> list[dict]:
    """
    chunk_hits: vector_store.search / hybrid_search 반환값
    [{chunk_id, precedent_id, score, text, section_title, element_type,
      title, source_url, case_number, case_name, court_name, judgment_date,
      plaintiff, defendant, lower_court_case, ...}, ...]

    Returns:
    [
      {
        "precedent_id":     int,
        "title":            str | None,
        "source_url":       str | None,
        "case_number":      str | None,
        "case_name":        str | None,
        "court_name":       str | None,
        "judgment_date":    str | None,
        "plaintiff":        str | None,
        "defendant":        str | None,
        "lower_court_case": str | None,
        "score":            float,
        "chunks": [
          {
            "chunk_id":      str,
            "text":          str,
            "section_title": str | None,
            "element_type":  str,
            "score":         float,
          },
          ...
        ]
      },
      ...
    ]
    """
    grouped: dict[int, dict] = {}

    for hit in chunk_hits:
        pid = hit.get("precedent_id")
        if pid is None:
            continue

        score = hit.get("score", 0.0)
        chunk_entry = {
            "chunk_id": hit.get("chunk_id"),
            "text": hit.get("text"),
            "section_title": hit.get("section_title"),
            "element_type": hit.get("element_type"),
            "score": score,
        }

        if pid not in grouped:
            grouped[pid] = {
                "precedent_id": pid,
                **{field: hit.get(field) for field in _PRECEDENT_META_FIELDS},
                "score": score,
                "chunks": [chunk_entry],
            }
        else:
            if score > grouped[pid]["score"]:
                grouped[pid]["score"] = score
            grouped[pid]["chunks"].append(chunk_entry)

    # 각 precedent에서 상위 chunk만 유지 + 중복 제거
    for group in grouped.values():
        chunks = sorted(group["chunks"], key=lambda c: c["score"], reverse=True)
        deduped: list[dict] = []
        for chunk in chunks:
            if len(deduped) >= TOP_CHUNKS_PER_PRECEDENT:
                break
            if deduped and abs(chunk["score"] - deduped[-1]["score"]) < MIN_SCORE_GAP:
                continue
            deduped.append(chunk)
        group["chunks"] = deduped

    return sorted(grouped.values(), key=lambda g: g["score"], reverse=True)
