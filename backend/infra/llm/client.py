import json
import logging
import os
import threading

import requests
from requests.adapters import HTTPAdapter

from errors import AppException, ErrorCode

logger = logging.getLogger(__name__)


class LLMClient:
    """Ollama HTTP 호출과 프로파일 fallback을 담당한다."""

    _session: requests.Session | None = None
    _session_lock = threading.Lock()

    def __init__(self):
        self._host = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
        self._model = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
        self._timeout = int(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "600"))
        self._initial_num_ctx = int(os.environ.get("OLLAMA_NUM_CTX", "8192"))
        self._pool_connections = int(
            os.environ.get("OLLAMA_HTTP_POOL_CONNECTIONS", "10")
        )
        self._pool_maxsize = int(os.environ.get("OLLAMA_HTTP_POOL_MAXSIZE", "20"))

    def _get_session(self) -> requests.Session:
        """프로세스 내에서 공유되는 requests.Session을 반환한다."""
        cls = type(self)
        if cls._session is not None:
            return cls._session

        with cls._session_lock:
            if cls._session is not None:
                return cls._session

            session = requests.Session()
            adapter = HTTPAdapter(
                pool_connections=self._pool_connections,
                pool_maxsize=self._pool_maxsize,
            )
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            cls._session = session
            return session

    def unload_model(self) -> None:
        """실패 후 Ollama keep-alive 세션을 해제한다."""
        try:
            self._get_session().post(
                f"{self._host}/api/generate",
                json={
                    "model": self._model,
                    "prompt": "",
                    "stream": False,
                    "keep_alive": 0,
                },
                timeout=15,
            )
        except requests.exceptions.RequestException as e:
            logger.warning(f"[OLLAMA_UNLOAD_FAILED] {e}")

    def call_json(self, prompt: str, num_predict: int) -> dict:
        endpoint = f"{self._host}/api/generate"
        fallback_profiles = list(
            dict.fromkeys(
                [
                    (self._initial_num_ctx, num_predict),
                    (6144, 2048),
                    (4096, 1536),
                ]
            )
        )

        last_error = None
        for num_ctx, num_predict in fallback_profiles:
            payload = {
                "model": self._model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.0,
                    "num_predict": num_predict,
                    "num_ctx": num_ctx,
                    # 문서 분류/요약 요청은 독립 실행이므로 KV 캐시를 재사용하지 않는다.
                    "num_keep": 0,
                },
            }
            try:
                response = self._get_session().post(
                    endpoint,
                    json=payload,
                    timeout=self._timeout,
                )
                response.raise_for_status()
                return json.loads(response.json().get("response", "{}"))
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                last_error = e
                logger.warning(
                    f"[OLLAMA_RETRY] failed (num_ctx={num_ctx}, num_predict={num_predict}): {e}"
                )

        self.unload_model()
        raise AppException(ErrorCode.LLM_ALL_PROFILES_FAILED) from last_error

    def stream_chat(self, messages: list, num_predict: int = 1024):
        endpoint = f"{self._host}/api/chat"
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": 0.1,
                "num_predict": num_predict,
                "num_ctx": self._initial_num_ctx,
                "num_keep": 0,
            },
        }

        try:
            with self._get_session().post(
                endpoint, json=payload, stream=True, timeout=self._timeout
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        yield chunk
        except Exception as e:
            logger.error(f"[OLLAMA_STREAM_FAILED] {e}")
            self.unload_model()
            raise AppException(ErrorCode.LLM_CONNECT_FAILED) from e

    def summarize_chat(self, messages: list, num_predict: int = 1024) -> str:
        endpoint = f"{self._host}/api/chat"
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": num_predict,
                "num_ctx": self._initial_num_ctx,
                "num_keep": 0,
            },
        }

        try:
            response = self._get_session().post(
                endpoint,
                json=payload,
                timeout=self._timeout,
            )
            response.raise_for_status()
            return response.json().get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.error(f"[OLLAMA_CHAT_FAILED] {e}")
            self.unload_model()
            raise AppException(ErrorCode.LLM_CONNECT_FAILED) from e
