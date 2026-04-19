from domains.chat.reference_payload import build_chat_reference_payloads
from domains.knowledge.schemas import RetrievedKnowledgeItem


def _item(
    knowledge_type: str,
    *,
    source_type: str,
    source_id: str | int,
    title: str,
    chunk_id: str,
    metadata: dict | None = None,
) -> RetrievedKnowledgeItem:
    return RetrievedKnowledgeItem(
        knowledge_type=knowledge_type,  # type: ignore[arg-type]
        source_type=source_type,
        source_id=source_id,
        title=title,
        chunk_text="내용",
        score=0.9,
        chunk_id=chunk_id,
        metadata=metadata or {},
    )


def test_build_chat_reference_payloads_keeps_citation_fields():
    payloads = build_chat_reference_payloads(
        [
            _item(
                "platform",
                source_type="precedent",
                source_id="p1",
                title="판례",
                chunk_id="platform:1:chunk:3",
                metadata={
                    "source_url": "https://example.com",
                    "case_number": "2024구합1",
                },
            ),
            _item(
                "session",
                source_type="session_document",
                source_id="session:1",
                title="첨부 문서",
                chunk_id="session:1:chunk:7",
                metadata={"chunk_order": 6},
            ),
        ]
    )

    assert payloads[0]["source_url"] == "https://example.com"
    assert payloads[0]["case_number"] == "2024구합1"
    assert payloads[1]["chunk_order"] == 6


def test_build_chat_reference_payloads_dedupes_same_chunk():
    item = _item(
        "workspace",
        source_type="workspace_document",
        source_id=10,
        title="문서.pdf",
        chunk_id="gdoc:10:chunk:0",
        metadata={"file_name": "문서.pdf"},
    )
    payloads = build_chat_reference_payloads([item, item])
    assert len(payloads) == 1
