"""Careers-page adapters. Each returns a list of normalized listings:
    {company, id, title, location, url, description}
Network-touching functions are isolated here so monitor logic stays testable.
"""
from __future__ import annotations

import requests

TIMEOUT = 15
HEADERS = {"User-Agent": "job-hunt-tools/0.1 (personal job search)"}


def normalize_greenhouse(company: str, payload: dict) -> list[dict]:
    """Pure transform: Greenhouse /jobs JSON -> normalized listings. No network."""
    out = []
    for j in payload.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        out.append({
            "company": company,
            "id": str(j.get("id", "")),
            "title": j.get("title", "").strip(),
            "location": loc,
            "url": j.get("absolute_url", ""),
            "description": j.get("content", "") or "",
        })
    return out


def fetch_greenhouse(company: str, token: str) -> list[dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return normalize_greenhouse(company, r.json())


def normalize_lever(company: str, payload: list) -> list[dict]:
    out = []
    for j in payload:
        cats = j.get("categories") or {}
        out.append({
            "company": company,
            "id": str(j.get("id", "")),
            "title": (j.get("text") or "").strip(),
            "location": cats.get("location", ""),
            "url": j.get("hostedUrl", ""),
            "description": j.get("descriptionPlain", "") or "",
        })
    return out


def fetch_lever(company: str, token: str) -> list[dict]:
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return normalize_lever(company, r.json())


class UnsupportedCompany(Exception):
    """Raised for companies with no supported ATS adapter."""


def fetch_company(company: str, cfg: dict) -> list[dict]:
    """Dispatch to the right adapter. Raises UnsupportedCompany for unmapped ATS."""
    kind = cfg.get("type")
    if kind == "greenhouse":
        return fetch_greenhouse(company, cfg["token"])
    if kind == "lever":
        return fetch_lever(company, cfg["token"])
    raise UnsupportedCompany(cfg.get("careers", ""))
