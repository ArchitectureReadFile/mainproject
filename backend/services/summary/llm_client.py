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
