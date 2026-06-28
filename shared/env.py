"""Load .env from repo root into os.environ. Call load_env() at entrypoints.

Minimal parser (no dependency): KEY=VALUE lines, ignores blanks and #comments.
Values already present in the real environment are NOT overwritten.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"


def load_env(path: Path = ENV_FILE) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


def is_placeholder(val: str | None) -> bool:
    """True if a secret is missing or still the .env.example placeholder."""
    if not val:
        return True
    v = val.lower()
    return v.startswith("sk-ant-...") or "xxxx" in v
