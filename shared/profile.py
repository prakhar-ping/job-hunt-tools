"""Derive a job-search profile (keywords + web queries) from an uploaded resume.

Makes the tool generic: instead of hand-tuned config keywords, the search adapts
to whatever resume is uploaded. With ANTHROPIC_API_KEY, Claude derives a rich
profile; without it, a heuristic extractor scans for known tech/role terms.

The derived profile is saved to shared/resume_profile.json (gitignored). The
monitor uses it when present and falls back to config otherwise.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .claude_client import LLMUnavailable, complete_cfg, llm_available

ROOT = Path(__file__).resolve().parent.parent
PROFILE_PATH = ROOT / "shared" / "resume_profile.json"

# ---- heuristic vocabulary (domain-agnostic) -------------------------------

LANGS = [
    "c++", "c#", "python", "java", "javascript", "typescript", "go", "golang",
    "rust", "kotlin", "swift", "scala", "ruby", "php", "lua", "c",
]
DOMAINS = [
    "distributed", "storage engine", "query engine", "database", "kernel",
    "machine learning", "deep learning", "data engineering", "backend",
    "frontend", "full stack", "devops", "cloud", "security", "mobile", "ios",
    "android", "game", "gameplay", "graphics", "rendering", "embedded",
    "firmware", "compiler", "networking", "platform", "infrastructure",
    "site reliability", "performance", "low latency",
]
STRONG = [
    "kubernetes", "docker", "terraform", "kafka", "spark", "hadoop", "raft",
    "rocksdb", "opengl", "vulkan", "directx", "unreal", "unity", "tensorflow",
    "pytorch", "react", "django", "flask", "spring", "graphql", "grpc",
    "postgres", "mongodb", "redis", "memory allocator", "lock-free", "cuda",
]
DEFAULT_EXCLUDE = [
    "sales", "account executive", "account manager", "recruiter", "marketing",
    "legal", "intern", "designer", "artist", "producer", "product manager",
    "solutions architect", "pre-sales", "presales", "support engineer",
    "customer success", "scientist",
]


def extract_resume_text(path: str | Path) -> str:
    """Plain text from a resume file. PDF via pypdf; md/txt/other read directly."""
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    return path.read_text(errors="ignore")


def _present(text: str, terms: list[str]) -> list[str]:
    low = text.lower()
    out = []
    for t in terms:
        if re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", low):
            out.append(t)
    return out


def heuristic_profile(text: str) -> dict:
    """Keyword profile from a resume with no LLM — scans for known terms."""
    langs = _present(text, LANGS)
    domains = _present(text, DOMAINS)
    strong = _present(text, STRONG)
    title = langs + domains or ["engineer", "developer"]
    primary = langs[0] if langs else "software"
    queries = [f"{primary} developer", f"{primary} engineer"]
    queries += [f"{primary} {d}" for d in domains[:3]]
    # dedupe, keep order
    seen, q = set(), []
    for x in queries:
        if x not in seen:
            seen.add(x)
            q.append(x)
    return {
        "match": {"title": title, "desc_strong": strong,
                  "exclude": DEFAULT_EXCLUDE},
        "queries": q[:6],
    }


_SYSTEM = """You build a job-search keyword profile from a resume. Return ONLY a \
JSON object (no prose, no code fence) with this exact shape:
{
  "match": {
    "title": [lowercase skill/role terms that, if present in a job TITLE, mean
              the job fits this candidate],
    "desc_strong": [rarer technologies that signal fit even if only in the
                    job description (not generic words)],
    "exclude": [title terms that mean a job is NOT for this candidate, e.g.
                sales, recruiter, intern, designer]
  },
  "queries": [4-6 web search phrases to find jobs for this candidate, e.g.
              "senior c++ game developer"]
}
Keep terms lowercase. Base everything on the resume's real skills and seniority."""


def derive_profile(resume_text: str, llm: dict) -> dict:
    """LLM-derived profile when the configured provider is available, else a
    heuristic. Always returns a valid profile dict with 'match' and 'queries'."""
    if not llm_available(llm):
        return heuristic_profile(resume_text)
    try:
        raw = complete_cfg(_SYSTEM, resume_text[:12000], llm, max_tokens=1500)
        data = json.loads(re.search(r"\{.*\}", raw, re.DOTALL).group(0))
        m = data["match"]
        assert all(k in m for k in ("title", "desc_strong", "exclude"))
        assert isinstance(data["queries"], list) and data["queries"]
        return {"match": m, "queries": data["queries"]}
    except (LLMUnavailable, KeyError, AssertionError, AttributeError,
            json.JSONDecodeError, Exception):
        return heuristic_profile(resume_text)


def save_profile(profile: dict, resume_name: str = "") -> None:
    profile = {**profile, "resume_name": resume_name}
    PROFILE_PATH.write_text(json.dumps(profile, indent=2))


def load_profile() -> dict | None:
    if not PROFILE_PATH.exists():
        return None
    try:
        return json.loads(PROFILE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def clear_profile() -> None:
    PROFILE_PATH.unlink(missing_ok=True)
