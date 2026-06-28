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

SYSTEM = """You are a resume-tailoring assistant for an experienced C++ / \
distributed-systems engineer. You are given a MASTER RESUME and a JOB DESCRIPTION.

Produce Markdown with exactly these sections:

## Keyword coverage
A score X/Y and a one-line read on overall fit.

## Gaps
Bullet list of concrete requirements in the JD that are NOT evidenced in the
resume. Be specific (skill, system, scale). If a gap is unfixable honestly, say so.

## Bullet rewrites
For 4-8 existing resume bullets, show `BEFORE:` then `AFTER:` rewrites that map the
candidate's REAL experience onto this JD's language and priorities.

HARD RULE: never invent experience, employers, numbers, or technologies the resume
does not support. Rewrites may reframe and re-emphasize only what is already true.
If the resume is empty or a template, say so and stop."""


def is_resume_filled(text: str) -> bool:
    stripped = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    return stripped.count("TODO") <= 2 and len(stripped.strip()) > 200


def build_prompt(resume: str, jd: str) -> str:
    return f"# MASTER RESUME\n\n{resume}\n\n---\n\n# JOB DESCRIPTION\n\n{jd}"


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
