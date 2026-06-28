"""ATS keyword matching: extract a JD's key terms and score a resume's coverage.

Used both to fix tailoring (feed the JD's real keywords into the rewrite) and to
report an ATS match score back to the user.
"""
from __future__ import annotations

import json
import re

from shared.claude_client import complete_cfg

STOP = set("""a an the and or of to in for with on at by from as is are be this that
your you our we will work team role job company they it its their he she his her
including across using used use new etc per into out over under than then so if
not but who whom which what when where why how all any can may must should would
could have has had do does did been being more most other some such only own same
""".split())

_KW_SYSTEM = """Extract the ATS keywords a recruiter's system would scan for in this \
job description: hard skills, technologies, tools, languages, methodologies, and \
domain terms. Return ONLY a JSON array of 12-25 short lowercase keyword strings \
(1-3 words each), most important first. No commentary."""


def extract_jd_keywords(jd: str, llm: dict | None = None) -> list[str]:
    """Key ATS terms for a JD. Uses the LLM if given/available, else heuristic."""
    if llm:
        try:
            raw = complete_cfg(_KW_SYSTEM, jd[:4000], llm, max_tokens=600)
            arr = json.loads(re.search(r"\[.*\]", raw, re.DOTALL).group(0))
            kws = [str(k).strip().lower() for k in arr if str(k).strip()]
            if kws:
                return _dedupe(kws)[:25]
        except Exception:
            pass
    return heuristic_keywords(jd)


def heuristic_keywords(jd: str, top: int = 20) -> list[str]:
    """Frequency-based fallback: notable unigrams + bigrams from the JD."""
    words = re.findall(r"[a-zA-Z][a-zA-Z+#.]{1,}", jd.lower())
    words = [w for w in words if w not in STOP and len(w) > 2]
    freq: dict[str, int] = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    for a, b in zip(words, words[1:], strict=False):
        bg = f"{a} {b}"
        freq[bg] = freq.get(bg, 0) + 2  # weight phrases
    ranked = sorted(freq, key=lambda k: freq[k], reverse=True)
    return _dedupe(ranked)[:top]


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def score(resume_text: str, keywords: list[str]) -> dict:
    """Coverage of JD keywords in the resume text (whole-word, case-insensitive)."""
    low = resume_text.lower()
    matched, missing = [], []
    for kw in keywords:
        pat = rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])"
        (matched if re.search(pat, low) else missing).append(kw)
    pct = round(100 * len(matched) / len(keywords)) if keywords else 0
    return {"pct": pct, "matched": matched, "missing": missing,
            "total": len(keywords)}
