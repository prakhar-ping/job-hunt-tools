"""Referral helper: parse pasted LinkedIn contacts -> filter eng -> draft outreach.

No LinkedIn network calls. You paste what you already see in the browser; the tool
only parses, filters, and drafts. You review and send by hand.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

import yaml

from shared.claude_client import complete_cfg
from shared.env import load_env

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "shared" / "config.yaml"
RESUME = ROOT / "shared" / "resume.md"
OUT_DIR = ROOT / "referral_drafts"

ENG_TERMS = [
    "engineer", "developer", "swe", "sde", "architect", "sre", "infrastructure",
    "infra", "platform", "staff", "principal", "systems", "backend", "distributed",
    "database", "storage", "kernel", "tech lead", "technical lead", "cto", "vp eng",
]

# A LinkedIn search-result block usually looks like:
#   Name Surname
#   Engineering Manager at Rubrik
#   2nd
# This parser is tolerant: it pairs a name line with a following title/company line.
TITLE_AT = re.compile(r"^(?P<title>.+?)\s+at\s+(?P<company>.+)$", re.IGNORECASE)
DEGREE = re.compile(r"^\s*(1st|2nd|3rd)\b", re.IGNORECASE)
NAME = re.compile(r"^[A-Z][\w.'-]+(?:\s+[A-Z][\w.'-]+){0,3}$")


def parse_contacts(text: str) -> list[dict]:
    """Parse pasted blob into [{name, title, company}]. Tolerant of noise."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    contacts: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = TITLE_AT.match(line)
        if m and contacts and not contacts[-1].get("title"):
            contacts[-1]["title"] = m.group("title").strip()
            contacts[-1]["company"] = m.group("company").strip()
            i += 1
            continue
        if DEGREE.match(line):
            i += 1
            continue
        if NAME.match(line) and "at " not in line.lower():
            contacts.append({"name": line, "title": "", "company": ""})
            i += 1
            continue
        # standalone "Title at Company" with no preceding name
        if m:
            contacts.append({"name": "", "title": m.group("title").strip(),
                             "company": m.group("company").strip()})
        i += 1
    return [c for c in contacts if c.get("title")]


_ENG_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in ENG_TERMS) + r")\b", re.IGNORECASE)


def filter_contacts(contacts: list[dict], company: str) -> list[dict]:
    comp = company.lower()
    out = []
    for c in contacts:
        if comp not in c.get("company", "").lower():
            continue
        if _ENG_RE.search(c.get("title", "")):
            out.append(c)
    return out


def draft_system(company: str) -> str:
    return f"""You draft SHORT, warm, specific LinkedIn outreach messages asking \
about referrals at {company}. The sender is an experienced C++ / distributed-\
systems engineer (resume provided). For each contact, write 4-6 sentences:
- open with a genuine, specific reason for reaching out to THIS person/role
- one line on the sender's relevant background
- a soft, low-pressure ask about the team / a referral
- no flattery clichés, no "I hope this finds you well", under 120 words.
Output one message per contact, headed by the contact's name."""


def run(company: str, text: str) -> str:
    load_env()
    config = yaml.safe_load(CONFIG.read_text())
    resume = RESUME.read_text()
    contacts = filter_contacts(parse_contacts(text), company)
    if not contacts:
        return (f"No engineering contacts at {company} found in the pasted text. "
                "Paste LinkedIn search results (name + 'Title at Company' lines).")
    roster = "\n".join(
        f"- {c['name'] or '(name?)'} — {c['title']} at {c['company']}"
        for c in contacts)
    user = f"# SENDER RESUME\n\n{resume}\n\n# CONTACTS\n{roster}"
    drafts = complete_cfg(draft_system(company), user, config["llm"],
                          max_tokens=3000)
    OUT_DIR.mkdir(exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-")
    out = OUT_DIR / f"{slug}-{dt.date.today().isoformat()}.md"
    out.write_text(drafts)
    return (f"Drafted outreach for {len(contacts)} contact(s) at {company}.\n\n"
            f"{drafts}\n\n---\nSaved to {out.relative_to(ROOT)} (review before sending)")


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="referral",
        description="Draft referral outreach from pasted LinkedIn contacts (stdin)")
    ap.add_argument("--company", required=True, help="target company to filter for")
    args = ap.parse_args(argv)
    print(run(args.company, sys.stdin.read()))


if __name__ == "__main__":
    main()
