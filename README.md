# job-hunt-tools

[![CI](https://github.com/prakhar-ping/job-hunt-tools/actions/workflows/ci.yml/badge.svg)](https://github.com/prakhar-ping/job-hunt-tools/actions/workflows/ci.yml)

Job-search automation for a C++ / game-dev engineer: a web-wide job **monitor**,
a resume **tailor**, a referral **drafter**, and a localhost **dashboard** —
sharing one config + master resume + Anthropic client.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design. Common tasks via
`make install` / `make test` / `make lint` / `make web`.

| Tool | Command | Needs |
|------|---------|-------|
| **Monitor** — daily new-listing digest | `python -m monitor` | nothing (email optional) |
| **Tailor** — JD → gaps + bullet rewrites | `python -m tailor "<url>"` | `ANTHROPIC_API_KEY`, filled `resume.md` |
| **Referral** — paste contacts → drafts | `pbpaste \| python -m referral --company X` | `ANTHROPIC_API_KEY` |

All commands run from the repo root using the venv interpreter:
`/Users/prakharverma/Desktop/job-hunt-tools/.venv/bin/python`.

## Setup

```bash
cd ~/Desktop/job-hunt-tools
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env        # then edit .env
```

Fill `.env`:
- `ANTHROPIC_API_KEY` — console.anthropic.com (tailor + referral)
- `GMAIL_USER` / `GMAIL_APP_PASSWORD` — Google Account → Security → 2-Step
  Verification → App passwords (monitor email digest; optional)

Create your resume: `cp shared/resume.example.md shared/resume.md` and fill it
with your real experience. `shared/resume.md` is gitignored, so your resume and
contact details stay local and never get committed.

### LLM provider (tailor / referral / resume keywords)
Set in `config.yaml` under `llm:`. Two providers:
- **`ollama`** (default) — local, free, offline. Install Ollama, then
  `ollama pull llama3.1:8b`. No API key, nothing leaves your machine.
- **`anthropic`** — Claude API, needs `ANTHROPIC_API_KEY` in `.env` (paid).

If the configured provider is unreachable, resume-keyword derivation falls back
to a heuristic; tailor/referral report a clear error instead of crashing.

Tune the job filter anytime in `shared/config.yaml` (`match:` block).

## Monitor

```bash
./.venv/bin/python -m monitor --dry-run   # scrape + diff + print, send nothing
./.venv/bin/python -m monitor             # + email + macOS notif + new_jobs_<date>.md
```

Coverage: 6 companies via Greenhouse JSON APIs (Rubrik, MongoDB, Druva,
Pure Storage, ClickHouse, Couchbase). The other 7 (Cohesity, Nutanix, NetApp,
VMware, Confluent, Arista, Playrix) have no public ATS API wired yet — each run
lists them with a careers link to check by hand.

First run seeds a baseline (emails nothing). Each later run reports only listings
new since the previous run.

### Web-wide search (Adzuna)
Beyond the fixed company list, the monitor can search the whole web via the free
Adzuna aggregator. Sign up at developer.adzuna.com, create an app, and put the
keys in `.env`:
```
ADZUNA_APP_ID=...
ADZUNA_APP_KEY=...
```
It then searches the queries/countries in `config.yaml` (`aggregator:` block),
dedupes, applies the same `match:` filter, and reports new hits under
**"Web (Adzuna)"** with each job's real company shown. Disabled automatically
when the keys are absent. Edit `aggregator.queries` / `aggregator.countries` to
tune the web search.

### Daily cron (installed)
```
0 9 * * *  cd <repo> && <repo>/.venv/bin/python -m monitor >> <repo>/monitor/cron.log 2>&1
```
Edit/remove with `crontab -e`. macOS may prompt for Full Disk Access for `cron`
the first time — grant it in System Settings → Privacy & Security.

## Tailor

```bash
./.venv/bin/python -m tailor "https://job-boards.greenhouse.io/clickhouse/jobs/123"
pbpaste | ./.venv/bin/python -m tailor -    # paste a JD instead
```
Outputs keyword coverage, gaps, and BEFORE/AFTER bullet rewrites. Refuses to
invent experience. Saves `tailored/<company>-<date>.md`.

## Referral

```bash
# copy LinkedIn search results (name + "Title at Company" lines), then:
pbpaste | ./.venv/bin/python -m referral --company Rubrik
```
Parses contacts, keeps engineering titles at the target company, drafts a
personalized message each. Drafting only — no LinkedIn calls, no sending.
Saves `referral_drafts/<company>-<date>.md`.

## Web dashboard (localhost)

```bash
./.venv/bin/python -m web      # then open http://127.0.0.1:5000
```
One page: all current matched jobs grouped by source (companies + Web (Adzuna)),
clickable links, a live filter box, and a **Refresh** button that re-runs the
scrape (updates snapshots, no email). Reads the same snapshot data the monitor
writes. Bound to localhost only.

**Tailor a resume to any job from the dashboard.** Every job row has a
**✎ Tailor → PDF** button — it fetches that posting's JD, rewrites your
`shared/resume.md` into a complete resume tailored to that role (using only your
real experience), renders it to a PDF, and downloads it as
`resume-<company>-<date>.pdf`. Uses the configured LLM (free local Ollama by
default).

**Upload a resume to make the search generic.** The dashboard has a resume
upload (PDF / md / txt). On upload, the resume is parsed into search keywords +
web queries — with `ANTHROPIC_API_KEY` set, Claude derives them; otherwise a
built-in heuristic scans for known tech/role terms. The monitor then searches
from *your resume* instead of `config.yaml` (config stays as the fallback;
"Use config instead" clears the resume). The derived profile is saved to
`shared/resume_profile.json` (gitignored).

## Tests

```bash
./.venv/bin/python -m pytest    # offline: matcher, diff, normalizers, parsing
```

## Layout

```
shared/    config.yaml, resume.md, claude_client.py, env.py
monitor/   scrapers.py, monitor.py        (module 2)
tailor/    jd_fetch.py, tailor.py         (module 1)
referral/  referral.py                    (module 3)
tests/     offline pytest suite
```
