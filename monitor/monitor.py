"""Job board monitor: scrape -> keyword filter -> diff vs yesterday -> deliver."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

from .scrapers import UnsupportedCompany, fetch_company

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "shared" / "config.yaml"
SNAP_DIR = Path(__file__).resolve().parent / "snapshots"


def load_config(path: Path = CONFIG) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def matches_keywords(listing: dict, match_cfg: dict) -> bool:
    """Tight match: drop on excluded title; keep on a title term in the title,
    or a rare desc_strong term in the description of an engineering role."""
    title = listing.get("title", "").lower()
    desc = listing.get("description", "").lower()
    if any(x in title for x in match_cfg.get("exclude", [])):
        return False
    if any(t in title for t in match_cfg.get("title", [])):
        return True
    is_eng = "engineer" in title or "developer" in title
    return is_eng and any(s in desc for s in match_cfg.get("desc_strong", []))


def diff_new(previous: list[dict], current: list[dict]) -> list[dict]:
    """Listings present in current but not previous, keyed by (company, id)."""
    seen = {(p["company"], p["id"]) for p in previous}
    return [c for c in current if (c["company"], c["id"]) not in seen]


def _snap_path(company: str) -> Path:
    safe = company.replace(" ", "_").replace("/", "_")
    return SNAP_DIR / f"{safe}.json"


def load_snapshot(company: str) -> list[dict] | None:
    p = _snap_path(company)
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)


def save_snapshot(company: str, listings: list[dict]) -> None:
    SNAP_DIR.mkdir(exist_ok=True)
    with open(_snap_path(company), "w") as f:
        json.dump(listings, f, indent=2)


def render_report(new_by_company, unsupported, seeded: set[str]) -> str:
    today = dt.date.today().isoformat()
    lines = [f"# New matching jobs — {today}", ""]
    total = sum(len(v) for v in new_by_company.values())
    if total == 0:
        lines.append("_No new matching listings since last run._")
    for company, jobs in new_by_company.items():
        if not jobs:
            continue
        lines.append(f"## {company} ({len(jobs)})")
        for j in jobs:
            loc = f" — {j['location']}" if j["location"] else ""
            lines.append(f"- [{j['title']}]({j['url']}){loc}")
        lines.append("")
    if seeded:
        lines.append(f"\n_Baseline established for: {', '.join(sorted(seeded))}._")
    if unsupported:
        lines.append("\n## Check manually (no ATS adapter)")
        for name, info in unsupported:
            lines.append(f"- **{name}** — {info}")
    return "\n".join(lines)


def notify_macos(summary: str) -> None:
    try:
        subprocess.run(
            ["osascript", "-e",
             f'display notification "{summary}" with title "Job Monitor"'],
            check=False, capture_output=True,
        )
    except FileNotFoundError:
        pass


def send_email(config: dict, report: str) -> None:
    import smtplib
    from email.mime.text import MIMEText

    user = os.environ.get("GMAIL_USER")
    pw = os.environ.get("GMAIL_APP_PASSWORD")
    if not (user and pw):
        print("[email] GMAIL_USER / GMAIL_APP_PASSWORD not set — skipping email.",
              file=sys.stderr)
        return
    msg = MIMEText(report, "plain")
    msg["Subject"] = f"Job Monitor — {dt.date.today().isoformat()}"
    msg["From"] = config["email"]["sender"]
    msg["To"] = config["email"]["recipient"]
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(user, pw)
        s.send_message(msg)
    print("[email] sent.", file=sys.stderr)


def run(dry_run: bool = False) -> str:
    config = load_config()
    match_cfg = config["match"]
    new_by_company: dict[str, list[dict]] = {}
    unsupported: list[tuple[str, str]] = []
    seeded: set[str] = set()

    for company, cfg in config["companies"].items():
        try:
            listings = fetch_company(company, cfg)
        except UnsupportedCompany as e:
            unsupported.append((company, str(e) or cfg.get("careers", "")))
            continue
        except Exception as e:
            unsupported.append((company, f"fetch error: {e}"))
            continue

        matched = [x for x in listings if matches_keywords(x, match_cfg)]
        previous = load_snapshot(company)
        if previous is None:
            new_by_company[company] = []
            seeded.add(company)
        else:
            new_by_company[company] = diff_new(previous, matched)
        if not dry_run:
            save_snapshot(company, matched)

    report = render_report(new_by_company, unsupported, seeded)
    total = sum(len(v) for v in new_by_company.values())

    if dry_run:
        report += "\n\n_(dry run — no email, no notification, snapshots unchanged)_"
    else:
        out = ROOT / f"new_jobs_{dt.date.today().isoformat()}.md"
        out.write_text(report)
        if total:
            notify_macos(f"{total} new matching job(s)")
            send_email(config, report)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(prog="monitor", description="Daily job board monitor")
    ap.add_argument("--dry-run", action="store_true",
                    help="scrape + diff + print; send nothing, leave snapshots untouched")
    args = ap.parse_args(argv)
    print(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
