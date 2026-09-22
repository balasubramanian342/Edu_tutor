"""
OpenAI-compatible LLM client backed by the local openai-oauth CLI.

The application talks to a local OpenAI-compatible endpoint instead of
requiring an OpenAI API key. Start the proxy with:

    npx openai-oauth@latest

Default endpoint:
    http://127.0.0.1:10531/v1

The proxy authenticates with the user's ChatGPT account. This is intended
for local development/demo use; it is not a replacement for a production
OpenAI API deployment.
"""

import os
import re
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass


def _is_placeholder(value: str) -> bool:
    value = (value or "").strip().lower()
    return not value or value in {"placeholder", "changeme", "demo", "none"} or value.startswith("your_")


class OpenAILLMClient:
    """Thin provider-neutral wrapper used by the tutor/assessment modules."""

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "The OpenAI Python SDK is missing. Run: pip install openai"
            ) from exc

        self.base_url = (
            base_url
            or os.getenv("OPENAI_BASE_URL")
            or "http://127.0.0.1:10531/v1"
        ).rstrip("/")

        # The local OAuth proxy does not require an API key. The SDK still
        # expects one, so a harmless local placeholder is used.
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or "openai-oauth-local"

        self.model = (
            model
            or os.getenv("OPENAI_OAUTH_MODEL")
            or os.getenv("OPENAI_MODEL")
            or "gpt-5.6-terra"
        )

        self._client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 800,
    ) -> str:
        """Generate a grounded tutor response through the OAuth proxy."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }

        # Some newer reasoning models do not accept temperature. Try the
        # requested setting first and fall back without it if necessary.
        try:
            response = self._client.chat.completions.create(
                **kwargs, temperature=temperature
            )
        except Exception as first_error:
            try:
                response = self._client.chat.completions.create(**kwargs)
            except Exception:
                raise first_error

        text = ""
        if getattr(response, "choices", None):
            message = response.choices[0].message
            text = getattr(message, "content", "") or ""

        return _strip_markdown_fence(text.strip())


# Backward-compatible aliases used by older imports in this project.
GeminiLLMClient = OpenAILLMClient
AnthropicLLMClient = OpenAILLMClient


def build_llm_client():
    """
    Build the shared local OAuth-backed client.

    Unlike an API-key client, the proxy may be started after FastAPI starts.
    Therefore this function performs a lightweight local health/model check
    and returns None if the proxy is not running. The existing deterministic
    fallback remains available.
    """
    try:
        client = OpenAILLMClient()
        # Confirm that the local endpoint is reachable. This avoids claiming
        # the LLM is enabled when the OAuth proxy has not been started.
        client._client.models.list()
        print(
            f"[llm_client] openai-oauth enabled — "
            f"{client.base_url} — model: {client.model}"
        )
        return client
    except Exception as exc:
        print(
            "[llm_client] openai-oauth proxy is unavailable — "
            f"using template-based fallback. Start `npx openai-oauth@latest` "
            f"and verify OPENAI_OAUTH_MODEL. Details: {exc}"
        )
        return None


def _strip_markdown_fence(text: str) -> str:
    """Remove accidental ```json ... ``` / ``` ... ``` wrappers."""
    stripped = text.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, re.DOTALL)
    return match.group(1) if match else stripped
