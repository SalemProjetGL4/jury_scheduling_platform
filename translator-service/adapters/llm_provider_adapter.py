from __future__ import annotations

import logging
from typing import Protocol

from config import settings

logger = logging.getLogger("translator")


class LLMProvider(Protocol):
    def complete(self, system_prompt: str, user_message: str, **kwargs: object) -> str: ...


class GeminiAdapter:
    def complete(self, system_prompt: str, user_message: str, **kwargs: object) -> str:
        import google.generativeai as genai

        if not settings.gemini_api_key:
            raise ValueError("Missing gemini_api_key")

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(settings.llm_model)
        response = model.generate_content(
            [system_prompt, user_message],
            generation_config={"temperature": 0},
            request_options={"timeout": settings.llm_timeout_seconds},
        )
        return response.text or ""


class GroqAdapter:
    def complete(self, system_prompt: str, user_message: str, **kwargs: object) -> str:
        from groq import Groq

        if not settings.groq_api_key:
            raise ValueError("Missing groq_api_key")

        client = Groq(api_key=settings.groq_api_key)
        self.last_token_usage: dict | None = None
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0,
        )
        usage = response.usage
        logger.info(f"[TOKEN DEBUG] Groq raw response.usage: {response.usage}")
        if usage is not None:
            self.last_token_usage = {
                "prompt_tokens": usage.prompt_tokens or 0,
                "completion_tokens": usage.completion_tokens or 0,
                "total_tokens": usage.total_tokens or 0,
            }
        logger.info(f"[TOKEN DEBUG] self.last_token_usage set to: {self.last_token_usage}")
        return response.choices[0].message.content or ""


class LocalAdapter:
    def complete(self, system_prompt: str, user_message: str, **kwargs: object) -> str:
        from openai import OpenAI

        client = OpenAI(base_url=settings.local_llm_base_url, api_key=settings.local_llm_api_key)
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0,
            timeout=settings.llm_timeout_seconds,
        )
        return response.choices[0].message.content or ""


def get_provider() -> LLMProvider:
    if settings.llm_provider == "gemini":
        return GeminiAdapter()
    if settings.llm_provider == "groq":
        return GroqAdapter()
    if settings.llm_provider == "local":
        return LocalAdapter()

    raise ValueError(f"Unsupported provider: {settings.llm_provider}")
