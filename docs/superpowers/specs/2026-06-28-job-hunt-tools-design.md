# Job-Hunt Tools — Design Spec

**Date:** 2026-06-28
**Owner:** Prakhar Verma (jobhunter@example.com)
**Status:** Approved, pre-implementation

## Goal

Three independent CLI tools that automate a C++/distributed-systems job search,
sharing one config + master resume + Anthropic client. Turn manual
evening-per-job work into minutes-per-job.

## Non-Goals

- No LinkedIn crawling/automation (ToS). Referral tool drafts only; user supplies
  contacts and sends messages by hand.
- No headless browser. JS-only careers pages are logged as gaps, not rendered.
- No auto-sending of resumes or outreach. Tools produce artifacts; user submits.

## Runtime Decisions (locked)

| Fork | Choice |
|---|---|
| LLM runtime | **Anthropic API** (key in `.env`), model configurable, default `claude-sonnet-4-6` |
| Master resume | **Markdown** (`shared/resume.md`), user-filled |
| Monitor delivery | **All three**: Gmail SMTP digest + local `new_jobs_<date>.md` archive + macOS notification |
| Scraping | **ATS map first**, then lightweight: Greenhouse/Lever JSON APIs, best-effort HTML, log unscrapable + link |
| Referral input | **Paste contacts** (stdin/file) |

## Repository Layout

```
job-hunt-tools/
  shared/
    config.yaml        # companies + ATS map, keywords, model name, email cfg
    resume.md          # master resume (user fills)
    claude_client.py   # Anthropic API wrapper, reads ANTHROPIC_API_KEY
  tailor/
    __main__.py        # CLI entry: tailor "<url>"  |  pbpaste | tailor -
    tailor.py          # orchestration: fetch JD -> prompt -> render
    jd_fetch.py        # URL/stdin -> cleaned JD text
  monitor/
    __main__.py        # CLI entry
    monitor.py         # scrape all -> filter -> diff -> deliver
    scrapers.py        # greenhouse / lever / generic_html adapters
    deliver.py         # email + file archive + osascript notification
    snapshots/         # <company>.json, yesterday's listings (gitignored)
  referral/
    __main__.py        # CLI entry: pbpaste | referral --company X
    referral.py        # parse contacts -> filter -> draft
  tests/               # pytest: scraper fixtures, diff logic, parsing
  .env.example         # ANTHROPIC_API_KEY, GMAIL_USER, GMAIL_APP_PASSWORD
  requirements.txt
  README.md
  .gitignore           # .env, snapshots/, tailored/, referral_drafts/, new_jobs_*.md
```

## Module 1 — Tailor

**Input:** JD URL (arg) or pasted text (stdin via `-`).
**Flow:**
1. `jd_fetch` — if URL: `requests` GET + BeautifulSoup text extraction, strip nav/boilerplate. If `-`: read stdin.
2. Build prompt: `resume.md` + JD text.
3. Claude returns structured markdown:
   - keyword-coverage score (JD terms present in resume / total)
   - **Gaps** — JD requirements absent from resume
   - **Bullet rewrites** — concrete rewrites grounded in the user's real resume
     experience. Explicit instruction: no fabricated achievements.
4. Print to stdout + save `tailored/<company>-<date>.md` (company inferred from JD/URL, fallback prompt-asked or `job`).

**Errors:** fetch failure → message + fall back to stdin paste. Empty resume → warn.

## Module 2 — Monitor

**Companies:** Cohesity, Rubrik, Nutanix, NetApp, VMware, Confluent, MongoDB,
Couchbase, Druva, Arista, Pure Storage, ClickHouse, Playrix.

**ATS map:** `config.yaml` maps each company → `{type: greenhouse|lever|html|unsupported, token/url}`.
Built during implementation by inspecting each careers page (the "coverage map" step).

**Flow:**
1. For each company, dispatch to adapter in `scrapers.py`:
   - `greenhouse`: `GET https://boards-api.greenhouse.io/v1/boards/<token>/jobs?content=true`
   - `lever`: `GET https://api.lever.co/v0/postings/<token>?mode=json`
   - `html`: requests + BS4 best-effort
   - `unsupported`: skip, record gap with careers URL
2. Normalize each listing → `{company, id, title, location, url}`.
3. Filter by keyword list (case-insensitive substring on title; description when
   available): C++, distributed systems, storage engine, query engine, database
   internals, replication, consensus, Raft, Paxos, performance, kernel, systems.
   Keywords editable in `config.yaml`.
4. Diff vs `snapshots/<company>.json` (yesterday) → new matching listings.
5. Write current listings back to snapshot.
6. Deliver new matches via `deliver.py`:
   - Gmail SMTP (`smtplib`, STARTTLS, app password) digest email
   - `new_jobs_<date>.md` archive
   - `osascript -e 'display notification ...'`
7. Log unscrapable companies in the digest so user checks manually.

**Idempotent:** first run seeds snapshots, emails nothing new (or emails all as
baseline — decide in plan; default: seed silently, note "baseline established").

**Cron:** `0 9 * * * cd ~/Desktop/job-hunt-tools && /usr/bin/python3 -m monitor`

## Module 3 — Referral

**Input:** pasted LinkedIn contact text (stdin) + `--company <name>` arg.
**Flow:**
1. Parse blob → list of `{name, title, company}` (heuristic line parsing;
   tolerant of LinkedIn copy formatting).
2. Filter: company matches target AND title matches eng keywords
   (engineer, SWE, developer, architect, SRE, infra, platform, staff, principal).
3. For each kept contact, Claude drafts a short personalized outreach referencing
   the user's background + the contact's role. Drafting only.
4. Save `referral_drafts/<company>-<date>.md`, one draft per contact.

**No network calls to LinkedIn.** User reviews + sends manually.

## Shared

- `claude_client.py`: thin wrapper over `anthropic` SDK. Reads `ANTHROPIC_API_KEY`.
  Single `complete(system, user) -> str`. Model from `config.yaml`.
- `config.yaml`: companies/ATS map, keywords, model, sender email, recipient.
- Secrets only in `.env` (gitignored). `.env.example` documents required vars.

## Testing (TDD)

- `scrapers.py`: parse fixture Greenhouse/Lever JSON → normalized listings.
- diff logic: given old+new lists → correct new-set.
- referral parsing: messy paste → correct contact structs + filtering.
- Claude calls mocked in tests (no live API in CI).

## Security

- All secrets in `.env`, gitignored. `.env.example` holds placeholders only.
- Gmail uses an app password, not the account password.
- No credentials logged. Snapshots/artifacts gitignored (may contain JD text).

## Build Order

1. Repo scaffold + shared (config, claude_client, .env.example, requirements).
2. ATS coverage map — research all 13 careers pages, fill `config.yaml`.
3. Monitor (scrapers → diff → deliver) + tests.
4. Tailor + tests.
5. Referral + tests.
6. README with setup + cron + daily-use commands.
