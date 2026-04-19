from unittest.mock import MagicMock, patch


def test_llm_client_reuses_shared_session():
    from infra.llm.client import LLMClient

    first_session = MagicMock()

    with patch("infra.llm.client.requests.Session", return_value=first_session) as mock:
        client = LLMClient()
        session_a = client._get_session()
        session_b = LLMClient()._get_session()

    assert session_a is first_session
    assert session_b is first_session
    assert mock.call_count == 1
    assert first_session.mount.call_count == 2
