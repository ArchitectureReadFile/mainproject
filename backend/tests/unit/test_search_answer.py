from models.model import User
from routers.auth import get_current_user


def test_search_answer_success_with_citations(client):
    def override_get_current_user():
        return User(id=1, email="user@example.com", username="tester")

    client.app.dependency_overrides[get_current_user] = override_get_current_user

    from routers import search as search_router

    original_retrieve = search_router.retrieve_precedents
    original_generate = search_router.RagAnswerService.generate_answer

    hits = [
        {
            "precedent_id": 12,
            "score": 0.91,
            "title": "대법원 2021도1234",
            "source_url": "https://example.com/case/12",
            "text": "불법영득의사 판단이 문제된 판례다.",
        }
    ]

    def fake_retrieve(query, top_k, search_mode):
        return hits

    def fake_generate(self, query, results):
        return {
            "answer": "검색 결과에 따르면 불법영득의사는 처분 의사와 함께 판단됩니다.",
            "citations": [
                {
                    "precedent_id": 12,
                    "title": "대법원 2021도1234",
                    "source_url": "https://example.com/case/12",
                    "score": 0.91,
                }
            ],
        }

    search_router.retrieve_precedents = fake_retrieve
    search_router.RagAnswerService.generate_answer = fake_generate

    try:
        res = client.post(
            "/api/search/answer",
            json={
                "query": "횡령죄에서 불법영득의사",
                "top_k": 5,
                "search_mode": "hybrid",
            },
        )
    finally:
        search_router.retrieve_precedents = original_retrieve
        search_router.RagAnswerService.generate_answer = original_generate
        client.app.dependency_overrides.pop(get_current_user, None)

    assert res.status_code == 200
    data = res.json()
    assert data["query"] == "횡령죄에서 불법영득의사"
    assert data["search_mode"] == "hybrid"
    assert "불법영득의사" in data["answer"]
    assert len(data["citations"]) == 1
    assert data["citations"][0]["precedent_id"] == 12
    assert data["results"][0]["precedent_id"] == 12


def test_search_answer_empty_results_returns_fallback(client):
    def override_get_current_user():
        return User(id=1, email="user@example.com", username="tester")

    client.app.dependency_overrides[get_current_user] = override_get_current_user

    from routers import search as search_router

    original_retrieve = search_router.retrieve_precedents

    def fake_retrieve(query, top_k, search_mode):
        return []

    search_router.retrieve_precedents = fake_retrieve

    try:
        res = client.post(
            "/api/search/answer",
            json={"query": "없는 판례", "top_k": 5, "search_mode": "hybrid"},
        )
    finally:
        search_router.retrieve_precedents = original_retrieve
        client.app.dependency_overrides.pop(get_current_user, None)

    assert res.status_code == 200
    data = res.json()
    assert data["answer"] == "관련 판례를 찾지 못했습니다."
    assert data["citations"] == []
    assert data["results"] == []


def test_rag_answer_service_filters_unknown_citations():
    from services.rag.answer_service import RagAnswerService

    service = RagAnswerService()
    results = [
        {
            "precedent_id": 3,
            "score": 0.88,
            "title": "대법원 2020도9999",
            "source_url": "https://example.com/case/3",
            "text": "설시 내용",
        }
    ]

    citations = service._build_citations([999, 3], results)

    assert citations == [
        {
            "precedent_id": 3,
            "title": "대법원 2020도9999",
            "source_url": "https://example.com/case/3",
            "score": 0.88,
        }
    ]


def test_rag_answer_service_fallback_on_llm_error():
    from services.rag.answer_service import RagAnswerService

    service = RagAnswerService()

    class BoomClient:
        def call_json(self, prompt, num_predict):
            raise RuntimeError("llm down")

    service.client = BoomClient()

    results = [
        {
            "precedent_id": 7,
            "score": 0.77,
            "title": "대법원 2019도7777",
            "source_url": "https://example.com/case/7",
            "text": "관련 내용",
        }
    ]

    payload = service.generate_answer("질문", results)

    assert payload["answer"] == (
        "검색 결과를 바탕으로 답변을 생성하지 못했습니다. 아래 참고 판례를 확인해주세요."
    )
    assert payload["citations"] == [
        {
            "precedent_id": 7,
            "title": "대법원 2019도7777",
            "source_url": "https://example.com/case/7",
            "score": 0.77,
        }
    ]
