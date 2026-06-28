"""Parse the master resume.md into a structured dict the PDF template renders.

Keeping a fixed structure (instead of free markdown) lets the tailored PDF match
the user's real resume layout exactly and stay 1-2 pages.
"""
from __future__ import annotations

import re


def _split_sections(md: str) -> dict[str, str]:
    """Return {section_title_lower: body} for each '## ' heading."""
    parts = re.split(r"^##\s+", md, flags=re.MULTILINE)
    out = {}
    for chunk in parts[1:]:
        title, _, body = chunk.partition("\n")
        out[title.strip().lower()] = body.strip()
    return out


def _bullets(body: str) -> list[str]:
    return [re.sub(r"^[-*]\s+", "", ln).strip()
            for ln in body.splitlines() if ln.lstrip().startswith(("- ", "* "))]


def _parse_experience(body: str) -> list[dict]:
    roles = []
    for chunk in re.split(r"^###\s+", body, flags=re.MULTILINE)[1:]:
        header, _, rest = chunk.partition("\n")
        header = header.strip()
        m = re.match(r"(.+?)\s+[—-]\s+(.+?)\s+\((.+)\)\s*$", header)
        if m:
            title, company, meta = m.group(1), m.group(2), m.group(3)
            dates, _, loc = meta.partition(", ")
            role = {"title": title, "company": company,
                    "dates": dates.strip(), "location": loc.strip()}
        else:
            role = {"title": header, "company": "", "dates": "", "location": ""}
        role["bullets"] = _bullets(rest)
        roles.append(role)
    return roles


def _parse_projects(body: str) -> list[dict]:
    projects = []
    for chunk in re.split(r"^###\s+", body, flags=re.MULTILINE)[1:]:
        lines = chunk.splitlines()
        name = lines[0].strip() if lines else ""
        stack = ""
        for ln in lines[1:]:
            s = ln.strip()
            if s.startswith("*") and s.endswith("*") and not s.startswith("**"):
                stack = s.strip("*").strip()
                break
        projects.append({"name": name, "stack": stack, "bullets": _bullets(chunk)})
    return projects


def parse_resume_md(md: str) -> dict:
    """Master resume markdown -> structured resume dict."""
    lines = [ln.rstrip() for ln in md.splitlines()]
    name = tagline = contact = footer = ""
    for ln in lines:
        s = ln.strip()
        if not name and s.startswith("# "):
            name = re.sub(r"\s*—\s*Master Resume\s*$", "", s[2:]).strip()
        elif not tagline and s.startswith("**") and s.endswith("**"):
            tagline = s.strip("*").strip()
        elif not contact and "·" in s and "@" in s:
            contact = s
        elif s.startswith("_") and s.endswith("_"):
            footer = s.strip("_").strip()

    sec = _split_sections(md)
    skills = []
    for b in _bullets(sec.get("technical skills", "")):
        m = re.match(r"\*\*(.+?):\*\*\s*(.+)", b)
        if m:
            skills.append({"label": m.group(1).strip(), "value": m.group(2).strip()})
        else:
            skills.append({"label": "", "value": b})

    education = "\n".join(
        ln for ln in sec.get("education", "").splitlines()
        if not ln.strip().startswith("_")).strip()

    projects_key = next((k for k in sec if "project" in k), "")
    return {
        "name": name,
        "tagline": tagline,
        "contact": contact,
        "summary": " ".join(sec.get("profile", "").split()),
        "skills": skills,
        "experience": _parse_experience(sec.get("experience", "")),
        "projects": _parse_projects(sec.get(projects_key, "")) if projects_key else [],
        "education": education,
        "footer": footer,
    }
