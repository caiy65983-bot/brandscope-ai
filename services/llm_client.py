"""Small OpenAI-compatible Chat Completions client with bounded retries."""

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


class LLMError(RuntimeError):
    """Safe, user-facing model request error (never includes credentials)."""


@dataclass(frozen=True)
class LLMConfig:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: int = 90
    request_retries: int = 2

    @classmethod
    def from_env(cls) -> "LLMConfig":
        def bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
            try:
                value = int(os.getenv(name, str(default)))
            except (TypeError, ValueError):
                value = default
            return max(minimum, min(value, maximum))

        return cls(
            api_key=os.getenv("BRANDSCOPE_API_KEY", os.getenv("OPENAI_API_KEY", "")).strip(),
            base_url=os.getenv("BRANDSCOPE_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).strip().rstrip("/"),
            model=os.getenv("BRANDSCOPE_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini")).strip(),
            timeout_seconds=bounded_int("BRANDSCOPE_TIMEOUT", 90, 1, 600),
            request_retries=bounded_int("BRANDSCOPE_REQUEST_RETRIES", 2, 0, 5),
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)


class OpenAICompatibleClient:
    def __init__(self, config: LLMConfig):
        if not config.configured:
            raise LLMError("尚未配置模型 API。请在项目根目录的 .env 文件中填写 API Key 和模型名称。")
        self.config = config

    def complete_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        url = self.config.base_url
        if not url.endswith("/chat/completions"):
            url += "/chat/completions"
        body = {
            "model": self.config.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        last_error: Optional[Exception] = None
        for attempt in range(self.config.request_retries + 1):
            try:
                response = requests.post(
                    url,
                    headers={"Authorization": "Bearer " + self.config.api_key, "Content-Type": "application/json"},
                    json=body,
                    timeout=self.config.timeout_seconds,
                )
                if response.status_code in (408, 429, 500, 502, 503, 504):
                    if attempt < self.config.request_retries:
                        time.sleep(min(2 ** attempt, 4))
                        continue
                    raise LLMError("模型服务暂时不可用（HTTP {}）。请稍后重试。".format(response.status_code))
                if not response.ok:
                    if response.status_code in (401, 403):
                        raise LLMError("模型服务拒绝访问（HTTP {}）。请检查 API Key 和账户权限。".format(response.status_code))
                    if response.status_code == 404:
                        raise LLMError("模型接口返回 HTTP 404。请检查 BRANDSCOPE_BASE_URL 和模型名称。")
                    raise LLMError("模型服务返回 HTTP {}。请检查 API 地址、请求格式和账户权限。".format(response.status_code))
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                if not isinstance(content, str):
                    raise LLMError("模型未返回 JSON 文本，请检查所选模型是否支持 JSON 输出。")
                import json
                return {"data": json.loads(content), "usage": data.get("usage", {})}
            except LLMError:
                raise
            except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
                last_error = exc
                if attempt < self.config.request_retries:
                    time.sleep(min(2 ** attempt, 4))
        if isinstance(last_error, requests.Timeout):
            raise LLMError("模型请求超时。可稍后重试，或在 .env 中提高 BRANDSCOPE_TIMEOUT。")
        if isinstance(last_error, requests.RequestException):
            raise LLMError("无法连接模型服务。请检查网络、代理设置和 BRANDSCOPE_BASE_URL。")
        raise LLMError("模型响应格式无效。请确认接口兼容 Chat Completions JSON 模式。")
