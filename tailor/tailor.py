"""Tailor: diff a JD against the master resume, surface gaps + bullet rewrites."""
from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path

import yaml

from shared.claude_client import complete_cfg
from shared.env import load_env

from .jd_fetch import fetch_jd

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "shared" / "config.yaml"
RESUME = ROOT / "shared" / "resume.md"
OUT_DIR = ROOT / "tailored"

SYSTEM = """You are a precise resume-tailoring tool. You output ONLY the three \
requested markdown sections. No greetings, no interview tips, no closing remarks. \
Never invent experience, employers, numbers, or technologies that are not in the \
resume — you may only reframe what is already there."""


def build_prompt(resume: str, jd: str) -> str:
    """Resume + JD, then the format spec LAST (recency helps smaller models)."""
    return f"""MASTER RESUME:
{resume}

JOB DESCRIPTION (for the role you are tailoring to):
{jd[:3500]}

Now output EXACTLY these three markdown sections and NOTHING else:

## Keyword coverage
One line: a score like "7/12" (JD must-have skills the resume already shows) plus a
short read on fit.

## Gaps
Bullet list. Each bullet = a concrete requirement in the JD that the resume does NOT
evidence. Be specific. If a gap can't honestly be closed, say so.

## Bullet rewrites
4-6 items. Each item is two lines:
BEFORE: <an existing bullet copied from the resume>
AFTER: <that bullet rewritten to match this JD's language and priorities>
Do not invent anything — only reframe real resume content."""


def is_resume_filled(text: str) -> bool:
    stripped = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    return stripped.count("TODO") <= 2 and len(stripped.strip()) > 200


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "job"


def run(source: str) -> str:
    load_env()
    config = yaml.safe_load(CONFIG.read_text())
    resume = RESUME.read_text()
    if not is_resume_filled(resume):
        return ("shared/resume.md is still the template — fill it with your real "
                "experience first, then re-run.")
    jd, company = fetch_jd(source)
    if not jd:
        return "Empty job description. Paste JD text or pass a URL."
    result = complete_cfg(SYSTEM, build_prompt(resume, jd),
                          config["llm"], max_tokens=3000)
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / f"{slugify(company)}-{dt.date.today().isoformat()}.md"
    out.write_text(result)
    return f"{result}\n\n---\nSaved to {out.relative_to(ROOT)}"


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="tailor", description="Tailor resume to a JD (URL or '-' for stdin)")
    ap.add_argument("source", help="JD URL, or '-' to read pasted JD from stdin")
    args = ap.parse_args(argv)
    print(run(args.source))


if __name__ == "__main__":
    main()
