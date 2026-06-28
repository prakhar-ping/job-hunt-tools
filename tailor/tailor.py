"""Tailor: diff a JD against the master resume, surface gaps + bullet rewrites."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

import yaml

from shared.claude_client import complete_cfg
from shared.env import load_env

from .jd_fetch import fetch_jd
from .resume_model import parse_resume_md

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


SYSTEM_RESUME = """You are a resume editor. You rewrite a candidate's master \
resume into a complete resume tailored to one job. Use ONLY facts present in the \
master resume — same employers, titles, dates, projects, and numbers. You may \
reorder, reword, and re-emphasize to match the job's priorities and language, but \
you must NOT invent skills, tools, or achievements that are not already in the \
resume. Output the full resume in clean Markdown and nothing else (no commentary)."""


def build_resume_prompt(resume: str, jd: str) -> str:
    return f"""MASTER RESUME (the only source of truth — do not add facts):
{resume}

TARGET JOB DESCRIPTION:
{jd[:3500]}

Now output a COMPLETE resume in Markdown, tailored to the job above. Structure:
# Name
contact line (email · phone · location · links) — copy from the master resume
## Summary
3-4 lines reframed toward this role
## Skills
grouped, leading with the skills this job cares about most
## Experience
every role from the master resume, dates kept; bullets reworded to foreground the
experience this job values
## Projects
the relevant ones
## Education
Use ONLY real content from the master resume. No invented facts."""


SYSTEM_JSON = """You tailor a resume to a job. You are given the resume as JSON and \
a job description. Return the SAME JSON structure with text reworded to emphasize \
what THIS job values. RULES: keep every key and the same shape; keep every job, \
project, date, and number; do NOT invent skills, tools, or experience that are not \
already present; you MAY reorder the skills, reword the summary, and reword bullets \
to use the job's language. Return ONLY the JSON object, no commentary."""


def _validated(data: object, baseline: dict) -> dict:
    """Keep model output only where it matches the baseline's shape; else baseline."""
    if not isinstance(data, dict):
        return baseline
    out = dict(baseline)
    for key, base_val in baseline.items():
        val = data.get(key)
        if isinstance(val, type(base_val)) and val:
            if isinstance(base_val, list) and not all(
                    isinstance(a, type(base_val[0] if base_val else a)) for a in val):
                continue
            out[key] = val
    return out


def tailor_resume_structured(source: str) -> tuple[dict, str]:
    """Tailor the resume to a JD, returning a structured dict + company.
    The LLM only rewrites text; layout/fields stay fixed. Falls back to the
    untailored (but correctly structured) resume if the model output is unusable."""
    config = yaml.safe_load(CONFIG.read_text())
    resume = RESUME.read_text()
    if not is_resume_filled(resume):
        raise ValueError("shared/resume.md is still the template — fill it first.")
    baseline = parse_resume_md(resume)
    jd, company = fetch_jd(source)
    if not jd:
        raise ValueError("Empty job description.")
    user = (f"RESUME JSON:\n{json.dumps(baseline, ensure_ascii=False)}\n\n"
            f"JOB DESCRIPTION:\n{jd[:3000]}\n\nReturn the tailored JSON now.")
    try:
        raw = complete_cfg(SYSTEM_JSON, user, config["llm"], max_tokens=3500)
        data = json.loads(re.search(r"\{.*\}", raw, re.DOTALL).group(0))
        return _validated(data, baseline), company
    except Exception:
        return baseline, company


def tailor_resume(source: str) -> tuple[str, str]:
    """Generate a full tailored resume (markdown) for a JD. Returns (md, company)."""
    config = yaml.safe_load(CONFIG.read_text())
    resume = RESUME.read_text()
    if not is_resume_filled(resume):
        raise ValueError("shared/resume.md is still the template — fill it first.")
    jd, company = fetch_jd(source)
    if not jd:
        raise ValueError("Empty job description.")
    md = complete_cfg(SYSTEM_RESUME, build_resume_prompt(resume, jd),
                      config["llm"], max_tokens=3000)
    return md, company


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
