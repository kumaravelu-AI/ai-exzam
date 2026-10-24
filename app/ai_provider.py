from __future__ import annotations
from typing import Protocol
import asyncio
import os
import httpx
from openai import OpenAI, APIConnectionError, APIError, APITimeoutError, RateLimitError

from .config import (
    AI_PROVIDER,
    OPENAI_COMPAT_BASE_URL,
    OPENAI_COMPAT_API_KEY,
    OPENAI_COMPAT_MODEL,
    GROQ_BASE_URL,
    GROQ_API_KEY,
    GROQ_MODEL,
    GROQ_STREAM,
)

GEMMA_BASE_URL = os.getenv("GEMMA_BASE_URL", OPENAI_COMPAT_BASE_URL).strip()
GEMMA_API_KEY = os.getenv("GEMMA_API_KEY", OPENAI_COMPAT_API_KEY).strip()
GEMMA_MODEL = os.getenv("GEMMA_MODEL", OPENAI_COMPAT_MODEL or "gemma-3-12b-it").strip()
MODEL_TIMEOUT_SECONDS = 120.0
GROQ_TIMEOUT_SECONDS = float(os.getenv("GROQ_TIMEOUT_SECONDS", "20"))


def _new_groq_client() -> OpenAI:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set for the groq provider.")
    return OpenAI(
        api_key=GROQ_API_KEY,
        base_url=GROQ_BASE_URL,
        timeout=GROQ_TIMEOUT_SECONDS,
        max_retries=0,
    )


def _groq_completion_from_messages(messages: list[dict[str, str]], *, stream: bool = False) -> str:
    client = _new_groq_client()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.2,
        stream=stream,
    )
    if stream:
        chunks: list[str] = []
        for event in response:
            delta = event.choices[0].delta.content if event.choices else None
            if delta:
                chunks.append(delta)
        return "".join(chunks).strip()
    return (response.choices[0].message.content or "").strip()


def groq_chat(prompt: str) -> str:
    response = _groq_completion_from_messages(
        [{"role": "user", "content": prompt}],
        stream=GROQ_STREAM,
    )
    return response


class AIProvider(Protocol):
    base_url: str
    model: str

    async def chat(self, system_prompt: str, user_prompt: str) -> str:
        ...


class MockProvider:
    base_url = "mock"
    model = "mock"

    async def chat(self, system_prompt: str, user_prompt: str) -> str:
        raise RuntimeError("Mock provider does not call a model.")


class OpenAICompatibleProvider:
    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        if not base_url:
            raise RuntimeError("Base URL is not set for the configured provider.")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def chat(self, system_prompt: str, user_prompt: str) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        async with httpx.AsyncClient(timeout=MODEL_TIMEOUT_SECONDS) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]


class GemmaProvider(OpenAICompatibleProvider):
    def __init__(self) -> None:
        super().__init__(
            base_url=GEMMA_BASE_URL,
            api_key=GEMMA_API_KEY,
            model=GEMMA_MODEL,
        )


class GroqProvider(OpenAICompatibleProvider):
    def __init__(self) -> None:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set for the groq provider.")
        super().__init__(
            base_url=GROQ_BASE_URL,
            api_key=GROQ_API_KEY,
            model=GROQ_MODEL,
        )
        self.stream = GROQ_STREAM

    async def chat(self, system_prompt: str, user_prompt: str) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        for attempt in range(2):
            try:
                return await asyncio.to_thread(_groq_completion_from_messages, messages, stream=self.stream)
            except RateLimitError as exc:
                try:
                    delay = float(exc.response.headers.get("retry-after", "10"))
                except ValueError:
                    delay = 10
                if attempt == 0 and 0 <= delay <= 30:
                    await asyncio.sleep(max(1, delay))
                    continue
                raise RuntimeError("RateLimitError") from exc
            except (APITimeoutError, APIConnectionError, APIError) as exc:
                raise RuntimeError(type(exc).__name__) from exc


def get_provider() -> AIProvider:
    if AI_PROVIDER == "groq":
        return GroqProvider()
    if AI_PROVIDER == "gemma":
        return GemmaProvider()
    if AI_PROVIDER == "openai_compat":
        return OpenAICompatibleProvider(
            base_url=OPENAI_COMPAT_BASE_URL,
            api_key=OPENAI_COMPAT_API_KEY,
            model=OPENAI_COMPAT_MODEL,
        )
    return MockProvider()
