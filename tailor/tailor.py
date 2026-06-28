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

from .ats import extract_jd_keywords, score
from .jd_fetch import fetch_jd
from .resume_model import parse_resume_md


def resume_to_text(d: dict) -> str:
    """Flatten a structured resume to plain text (for ATS scoring)."""
    parts = [d.get("summary", "")]
    parts += [f"{s.get('label', '')} {s.get('value', '')}" for s in d.get("skills", [])]
    for r in d.get("experience", []):
        parts += [r.get("title", "")] + r.get("bullets", [])
    for p in d.get("projects", []):
        parts += [p.get("name", ""), p.get("stack", "")] + p.get("bullets", [])
    return " ".join(parts)

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "shared" / "config.yaml"
RESUME = ROOT / "shared" / "resume.md"
RESUME_EXAMPLE = ROOT / "shared" / "resume.example.md"
OUT_DIR = ROOT / "tailored"


def read_resume() -> str:
    """The user's resume.md (gitignored) if present, else the bundled template."""
    return (RESUME if RESUME.exists() else RESUME_EXAMPLE).read_text()

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
    if "you@example.com" in text or "Your Name — Master Resume" in text:
        return False  # the bundled template, not a real resume
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


SYSTEM_JSON = """You are an expert resume writer optimizing for ATS keyword \
matching. You are given a resume as JSON, a job description, and the JD's ATS \
keywords. Return the SAME JSON structure, reworded so the resume naturally \
includes EVERY ATS keyword the candidate's REAL experience already supports, using \
the job's exact wording.

RULES:
- Keep every key and the same shape; keep every job, project, date, and number.
- For each ATS keyword: if the resume genuinely supports it (even under a different
  name, e.g. "cache-friendly data structures" supports "caching"), rewrite a bullet
  or skill to use the keyword's exact phrasing. If the candidate does NOT have it,
  do NOT add it — never fabricate.
- Reorder skills so the most JD-relevant come first; you may add a real skill to a
  skills value if the candidate clearly has it but it wasn't listed.
- Keep bullets truthful, specific, and quantified.
Return ONLY the JSON object, no commentary."""


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


def tailor_resume_structured(source: str) -> tuple[dict, str, dict]:
    """Tailor the resume to a JD. Returns (structured_resume, company, ats_report).
    The LLM only rewrites text within the parsed structure; on bad output it falls
    back to the untailored resume. ats_report = score of the result vs JD keywords."""
    config = yaml.safe_load(CONFIG.read_text())
    llm = config["llm"]
    resume = read_resume()
    if not is_resume_filled(resume):
        raise ValueError("shared/resume.md is still the template — fill it first.")
    baseline = parse_resume_md(resume)
    jd, company = fetch_jd(source)
    if not jd:
        raise ValueError("Empty job description.")
    keywords = extract_jd_keywords(jd, llm)
    user = (f"RESUME JSON:\n{json.dumps(baseline, ensure_ascii=False)}\n\n"
            f"JOB DESCRIPTION:\n{jd[:3000]}\n\n"
            f"JD ATS KEYWORDS (weave in every one the resume truly supports): "
            f"{', '.join(keywords)}\n\nReturn the tailored JSON now.")
    data = baseline
    try:
        raw = complete_cfg(SYSTEM_JSON, user, llm, max_tokens=3500)
        data = _validated(json.loads(re.search(r"\{.*\}", raw, re.DOTALL).group(0)),
                          baseline)
    except Exception:
        data = baseline
    ats = score(resume_to_text(data), keywords)
    return data, company, ats


def tailor_resume(source: str) -> tuple[str, str]:
    """Generate a full tailored resume (markdown) for a JD. Returns (md, company)."""
    config = yaml.safe_load(CONFIG.read_text())
    resume = read_resume()
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
    resume = read_resume()
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
