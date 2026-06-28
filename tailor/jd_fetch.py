"""Get a job description from a URL or stdin, return cleaned text + a company guess."""
from __future__ import annotations

import re
import sys
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "job-hunt-tools/0.1 (personal job search)"}
TIMEOUT = 20


def clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "svg"]):
        tag.decompose()
    text = soup.get_text("\n")
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def company_from_url(url: str) -> str:
    host = urlparse(url).hostname or ""
    host = re.sub(r"^(www|boards|jobs|careers|job-boards)\.", "", host)
    # greenhouse/lever style: boards.greenhouse.io/<company>/...
    if "greenhouse.io" in host or "lever.co" in host:
        parts = [p for p in urlparse(url).path.split("/") if p]
        if parts:
            return parts[0]
    return host.split(".")[0] if host else "job"


def fetch_jd(source: str) -> tuple[str, str]:
    """source = URL or '-' for stdin. Returns (jd_text, company_guess)."""
    if source == "-":
        return sys.stdin.read().strip(), "job"
    r = requests.get(source, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return clean_html(r.text), company_from_url(source)
