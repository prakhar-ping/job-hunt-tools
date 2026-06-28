"""LLM client with pluggable providers. Configured via config.yaml `llm:` block.

Providers:
  - ollama    : local, free, offline (default). Talks to the Ollama HTTP API.
  - anthropic : Claude API (needs ANTHROPIC_API_KEY).
"""
from __future__ import annotations

import os

import requests

from .env import is_placeholder, load_env

DEFAULT_OLLAMA_HOST = "http://localhost:11434"


class MissingAPIKey(RuntimeError):
    pass


class LLMUnavailable(RuntimeError):
    pass


def llm_available(llm: dict) -> bool:
    """True if the configured provider can be used right now."""
    provider = (llm or {}).get("provider", "ollama")
    if provider == "anthropic":
        load_env()
        return not is_placeholder(os.environ.get("ANTHROPIC_API_KEY"))
    if provider == "ollama":
        host = (llm or {}).get("ollama_host", DEFAULT_OLLAMA_HOST)
        try:
            return requests.get(f"{host}/api/tags", timeout=2).ok
        except requests.RequestException:
            return False
    return False


def _complete_ollama(system: str, user: str, model: str, host: str,
                     max_tokens: int) -> str:
    r = requests.post(
        f"{host}/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0.3},
        },
        timeout=300,
    )
    r.raise_for_status()
    return r.json()["message"]["content"]


def _complete_anthropic(system: str, user: str, model: str,
                        max_tokens: int) -> str:
    load_env()
    key = os.environ.get("ANTHROPIC_API_KEY")
    if is_placeholder(key):
        raise MissingAPIKey(
            "ANTHROPIC_API_KEY not set. Add it to .env "
            "(get one at console.anthropic.com)."
        )
    import anthropic

    client = anthropic.Anthropic(api_key=key)
    resp = client.messages.create(
        model=model, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if b.type == "text")


def complete(system: str, user: str, model: str, *, provider: str = "ollama",
             host: str | None = None, max_tokens: int = 2000) -> str:
    """Single-turn completion via the chosen provider. Returns assistant text."""
    if provider == "ollama":
        host = host or DEFAULT_OLLAMA_HOST
        try:
            return _complete_ollama(system, user, model, host, max_tokens)
        except requests.RequestException as e:
            raise LLMUnavailable(
                f"Ollama not reachable at {host} ({e}). Is it running? "
                "Start it with `ollama serve` and `ollama pull {model}`."
            ) from e
    if provider == "anthropic":
        return _complete_anthropic(system, user, model, max_tokens)
    raise LLMUnavailable(f"Unknown LLM provider: {provider!r}")


def complete_cfg(system: str, user: str, llm: dict, max_tokens: int = 2000) -> str:
    """Convenience: complete() using a config `llm:` dict."""
    return complete(system, user, llm["model"], provider=llm.get("provider",
                    "ollama"), host=llm.get("ollama_host"), max_tokens=max_tokens)
