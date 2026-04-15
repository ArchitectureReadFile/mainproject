import json
import logging
import os

import requests

from errors import AppException, ErrorCode

logger = logging.getLogger(__name__)


class LLMClient:
    """Ollama HTTP 통신 및 fallback 재시도를 담당합니다."""

    def __init__(self):
        self._host = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
        self._model = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
        self._timeout = int(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "600"))
        self._initial_num_ctx = int(os.environ.get("OLLAMA_NUM_CTX", "8192"))

    def unload_model(self) -> None:
        """실패 후 잔여 세션/모델 점유를 줄이기 위해 모델을 언로드합니다."""
        try:
            requests.post(
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
                    # 이전 요청의 KV 캐시를 재사용하지 않도록 강제한다.
                    # Ollama는 기본적으로 동일 모델 연속 요청 시 KV 캐시를 유지하는데,
                    # 문서 요약처럼 매 요청이 독립적이어야 하는 경우 이전 컨텍스트가
                    # 다음 요청에 섞이는 문제가 생긴다.
                    "num_keep": 0,
                },
            }
            try:
                response = requests.post(endpoint, json=payload, timeout=self._timeout)
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
            with requests.post(
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
            response = requests.post(endpoint, json=payload, timeout=self._timeout)
            response.raise_for_status()
            return response.json().get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.error(f"[OLLAMA_CHAT_FAILED] {e}")
            self.unload_model()
            raise AppException(ErrorCode.LLM_CONNECT_FAILED) from e
