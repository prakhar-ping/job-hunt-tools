# Keyword Search Expansion — Design Spec

**Date:** 2026-06-28
**Owner:** Prakhar Verma
**Status:** Pre-implementation
**Builds on:** [2026-06-28-job-hunt-tools-design.md](2026-06-28-job-hunt-tools-design.md) (Module 2, Monitor)

## Goal

Let the job monitor filter and present listings across three axes the user cares
about — **skill**, **seniority**, **work mode** — without losing relevance or
adding latency.

## Decisions (locked)

| Axis | Role | Source |
|------|------|--------|
| **Skill** (C++, distributed, storage engine, kernel, …) | **Required filter** — a job shows only if it matches | existing `title` / `desc_strong` / `exclude` logic, unchanged |
| **Seniority** (Senior, SDE, Staff, Principal, Lead, MTS) | **Tag only** — labeled, never excludes | job title |
| **Work mode** (Remote / Hybrid / Onsite) | **Tag + sort key** — labeled; remote floats to top | location string + description |

- Combination = **skill-required, rest optional tags** (not AND across axes).
- Work-mode sort priority: **Remote → Hybrid → Onsite**. Onsite = default when no
  remote/hybrid signal found; nothing is dropped for work mode.

## Non-Goals

- Seniority and work mode do NOT filter out jobs. (A C++ role with no stated mode
  still shows, tagged Onsite.)
- No new network calls, no headless browser, no new dependencies.

## Changes

### 1. `shared/config.yaml` — new `match` keys
```yaml
match:
  title: [...]        # unchanged — the SKILL filter
  desc_strong: [...]  # unchanged
  exclude: [...]      # unchanged
  seniority:          # NEW — detected in title, shown as tag (does not filter)
    - principal
    - staff
    - senior
    - "sr."
    - sr
    - lead
    - sde
    - sde ii
    - sde iii
    - member of technical staff
  # work_mode priority is fixed in code: remote > hybrid > onsite
```
Editing `title:` remains how the user adds/removes skill keywords.

### 2. `monitor/monitor.py` — annotate + sort
- `detect_seniority(title, seniority_terms) -> str` — first matching term, title-cased, else `""`.
- `detect_work_mode(listing) -> str` — `"Remote"` if "remote" in location/description,
  else `"Hybrid"` if "hybrid", else `"Onsite"`.
- `annotate(listing, match_cfg) -> listing` — adds `seniority` and `work_mode` fields.
- In `run()`: after keyword filtering, annotate each kept listing, then sort by
  work-mode priority (`{Remote:0, Hybrid:1, Onsite:2}`) then company then title.

### 3. `render_report()` — labeled line
From:
```
- [Title](url) — location
```
To:
```
- [Remote · Senior] Title — location
  (url)
```
Label = work mode, then seniority if present. Remote jobs grouped at the top of
each company section.

## Performance / safety

- All annotation is in-memory substring matching over already-fetched listings:
  O(listings × terms) ≈ a few hundred × ~15 = trivial. No measurable slowdown.
- Skill filter unchanged → every job that matches today still matches. Backward
  compatible. Snapshots/diff keyed by (company, id) as before; tags are derived,
  not stored in the diff key, so they don't affect new-vs-seen detection.

## Testing (offline, no network)

- `detect_seniority`: "Senior C++ Engineer" → "Senior"; "Software Engineer" → "".
- `detect_work_mode`: location "US (Remote)" → "Remote"; "Hybrid - Austin" →
  "Hybrid"; "Bangalore" → "Onsite".
- sort: mixed list orders Remote before Hybrid before Onsite.
- regression: existing matcher/diff tests still pass (skill filter untouched).
