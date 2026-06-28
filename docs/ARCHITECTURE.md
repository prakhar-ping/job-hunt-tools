# Architecture

A small, modular Python toolkit. Each tool is an independent package that shares
one config, one master resume, and one Anthropic client. No shared mutable state
between tools — they communicate only through files (config, snapshots, outputs).

```
                         shared/config.yaml ── one source of truth
                         shared/resume.md   ── master resume
                         shared/claude_client.py ── Anthropic wrapper
                         shared/env.py      ── .env loader
                                 │
        ┌────────────────────────┼─────────────────────────┐
        │                        │                          │
   monitor/                 tailor/                    referral/
   scrape → filter →        JD → gaps +                paste → filter →
   diff → deliver           bullet rewrites            draft outreach
        │
   snapshots/*.json ──────► web/  (Flask dashboard, reads snapshots)
```

## Modules

| Package | Responsibility | Depends on | Entry point |
|---------|----------------|-----------|-------------|
| `shared` | config, resume, Anthropic client, `.env` loader | — | — |
| `monitor` | scrape ATS + Adzuna → keyword filter → diff vs yesterday → email/notify/archive | `shared` | `jht-monitor` |
| `tailor` | fetch JD → diff vs resume → gaps + bullet rewrites | `shared` | `jht-tailor` |
| `referral` | parse pasted contacts → filter eng → draft outreach | `shared` | `jht-referral` |
| `web` | localhost dashboard over the monitor snapshots | `monitor` | `jht-web` |

## Data flow — monitor (the core)

1. **Fetch.** `scrapers.py` adapters: Greenhouse/Lever JSON APIs per company, plus
   the Adzuna aggregator for web-wide search. Each returns a normalized
   `{company, id, title, location, url, description}`.
2. **Filter.** `matches_keywords` — whole-word matching: drop on excluded title;
   keep on a `title` term in the title, or a rare `desc_strong` term in the
   description of an engineering role. Config-driven (`shared/config.yaml`).
3. **Diff.** Compare against `snapshots/<source>.json` (yesterday) keyed by
   `(company, id)` → the set new since last run.
4. **Deliver.** Gmail SMTP digest + `new_jobs_<date>.md` archive + macOS
   notification. The web dashboard's Refresh runs steps 1–3 with delivery off.

## Design choices

- **Adapters isolate the network.** Pure `normalize_*` functions are unit-tested
  against fixtures; only the thin `fetch_*` wrappers touch HTTP.
- **Config over code.** Companies, keywords, queries, and the aggregator all live
  in `config.yaml`; tuning the search never requires editing Python.
- **Graceful degradation.** Missing API keys (Anthropic, Gmail, Adzuna) disable
  the dependent feature with a clear message instead of crashing.
- **Secrets stay out of git.** All credentials in `.env` (gitignored); only
  placeholders in `.env.example`.

## Testing

`tests/` is fully offline — Claude, careers pages, and Adzuna are mocked or fed
fixtures. The suite covers normalizers, the keyword matcher (incl. word-boundary
edge cases), the diff, contact parsing/filtering, the aggregator, and the web
routes. CI (GitHub Actions) runs `ruff` + `pytest` on every push.
