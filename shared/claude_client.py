"""Thin wrapper over the Anthropic API. Reads ANTHROPIC_API_KEY from env."""
from __future__ import annotations

import os

from .env import is_placeholder, load_env


class MissingAPIKey(RuntimeError):
    pass


def complete(system: str, user: str, model: str, max_tokens: int = 2000) -> str:
    """Single-turn completion. Returns the assistant text."""
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
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in resp.content if block.type == "text")
