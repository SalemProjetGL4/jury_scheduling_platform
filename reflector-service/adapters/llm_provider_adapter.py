from __future__ import annotations

from typing import Protocol

from config import settings


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
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0,
        )
        return response.choices[0].message.content or ""


class OpenAIAdapter:
    def complete(self, system_prompt: str, user_message: str, **kwargs: object) -> str:
        # Support both new `openai` (>=1.0.0) and legacy module APIs
        if not settings.openai_api_key:
            raise ValueError("Missing openai_api_key")

        import openai

        ver = getattr(openai, "__version__", "0")
        try:
            major = int(str(ver).split(".")[0])
        except Exception:
            major = 0

        if major >= 1:
            # Use the new OpenAI client
            try:
                from openai import OpenAI as OpenAIClient

                try:
                    client = OpenAIClient(api_key=settings.openai_api_key)
                except TypeError as te:
                    msg = str(te)
                    if "proxies" in msg:
                        raise RuntimeError(
                            "OpenAI client initialization failed due to an SDK/runtime mismatch (unexpected 'proxies' argument). "
                            "Either pin the old OpenAI SDK (`pip install openai==0.28`) or upgrade/downgrade the client per your environment."
                        ) from te
                    raise

                if getattr(settings, "openai_api_base", None):
                    import os

                    os.environ.setdefault("OPENAI_API_BASE", settings.openai_api_base)

                response = client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0,
                )

                usage = getattr(response, "usage", None)
                self.last_token_usage: dict | None = None
                if usage is not None:
                    self.last_token_usage = {
                        "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                        "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
                        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
                    }

                try:
                    return response.choices[0].message.content
                except Exception:
                    return str(response)
            except Exception:
                # Surface the error for visibility upstream
                raise
        else:
            # legacy openai module
            legacy_openai = openai
            legacy_openai.api_key = settings.openai_api_key
            if getattr(settings, "openai_api_base", None):
                legacy_openai.api_base = settings.openai_api_base

            response = legacy_openai.ChatCompletion.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0,
                request_timeout=settings.llm_timeout_seconds,
            )

            try:
                return response.choices[0].message["content"]
            except Exception:
                try:
                    return response.choices[0].text
                except Exception:
                    return str(response)


class LocalAdapter:
    def complete(self, system_prompt: str, user_message: str, **kwargs: object) -> str:
        # Detect installed openai version
        import openai

        ver = getattr(openai, "__version__", "0")
        try:
            major = int(str(ver).split(".")[0])
        except Exception:
            major = 0

        if major >= 1:
            try:
                from openai import OpenAI as OpenAIClient

                try:
                    client = OpenAIClient(api_key=settings.local_llm_api_key or settings.openai_api_key)
                except TypeError as te:
                    msg = str(te)
                    if "proxies" in msg:
                        raise RuntimeError(
                            "OpenAI client initialization failed due to an SDK/runtime mismatch (unexpected 'proxies' argument). "
                            "Either pin the old OpenAI SDK (`pip install openai==0.28`) or upgrade/downgrade the client per your environment."
                        ) from te
                    raise

                if getattr(settings, "local_llm_base_url", None):
                    import os

                    os.environ.setdefault("OPENAI_API_BASE", settings.local_llm_base_url)

                response = client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0,
                )

                try:
                    return response.choices[0].message.content
                except Exception:
                    return str(response)
            except Exception:
                raise
        else:
            legacy_openai = openai
            if getattr(settings, "local_llm_api_key", None):
                legacy_openai.api_key = settings.local_llm_api_key
            elif getattr(settings, "openai_api_key", None):
                legacy_openai.api_key = settings.openai_api_key
            if getattr(settings, "local_llm_base_url", None):
                legacy_openai.api_base = settings.local_llm_base_url

            response = legacy_openai.ChatCompletion.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0,
                request_timeout=settings.llm_timeout_seconds,
            )

            try:
                return response.choices[0].message["content"]
            except Exception:
                try:
                    return response.choices[0].text
                except Exception:
                    return str(response)


def get_provider() -> LLMProvider:
    if settings.llm_provider == "gemini":
        return GeminiAdapter()
    if settings.llm_provider == "groq":
        return GroqAdapter()
    if settings.llm_provider == "openai":
        return OpenAIAdapter()
    if settings.llm_provider == "local":
        return LocalAdapter()

    raise ValueError(f"Unsupported provider: {settings.llm_provider}")
