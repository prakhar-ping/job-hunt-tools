"""Offline tests for monitor logic — no network, no API key."""
import monitor.monitor as M
from monitor.monitor import collect_aggregator, dedup, diff_new, matches_keywords
from monitor.scrapers import (
    normalize_adzuna,
    normalize_greenhouse,
    normalize_lever,
)

MATCH = {
    "title": ["c++", "distributed", "kernel", "raft"],
    "desc_strong": ["raft", "lock-free", "mvcc"],
    "exclude": ["sales", "intern", "product manager"],
}


def L(title, desc=""):
    return {"title": title, "description": desc}


# --- matcher ---------------------------------------------------------------

def test_title_term_matches():
    assert matches_keywords(L("Senior C++ Engineer"), MATCH)
    assert matches_keywords(L("Distributed Systems Engineer"), MATCH)


def test_word_boundary_engine_not_engineer():
    # 'engine' must not match the substring inside 'engineer'.
    cfg = {"title": ["engine", "c++"], "desc_strong": [], "exclude": []}
    assert not matches_keywords(L("Sales Engineer"), cfg)   # 'engine' in 'Engineer'
    assert matches_keywords(L("Game Engine Programmer"), cfg)
    assert matches_keywords(L("Senior C++ Developer"), cfg)  # '+' survives boundary


def test_excluded_title_dropped_even_if_keyword_present():
    # "Sales Engineer, C++ Platform" has c++ but is excluded by 'sales'
    assert not matches_keywords(L("Sales Engineer, C++ Platform"), MATCH)
    assert not matches_keywords(L("C++ Engineer Intern"), MATCH)


def test_boilerplate_cpp_in_description_does_not_match():
    # C++ only counts in the title — description boilerplate must not match.
    assert not matches_keywords(L("Account Manager", "We build in C++"), MATCH)


def test_desc_strong_needs_engineering_title():
    assert matches_keywords(L("Backend Engineer", "uses raft consensus"), MATCH)
    assert not matches_keywords(L("Recruiter", "we use raft internally"), MATCH)


# --- diff ------------------------------------------------------------------

def test_diff_finds_only_new():
    prev = [{"company": "X", "id": "1"}, {"company": "X", "id": "2"}]
    cur = [{"company": "X", "id": "2"}, {"company": "X", "id": "3"}]
    new = diff_new(prev, cur)
    assert [n["id"] for n in new] == ["3"]


def test_diff_empty_when_unchanged():
    prev = [{"company": "X", "id": "1"}]
    assert diff_new(prev, prev) == []


# --- scraper normalizers ---------------------------------------------------

def test_normalize_greenhouse():
    payload = {"jobs": [{
        "id": 42, "title": " Core C++ Engineer ",
        "location": {"name": "Remote"},
        "absolute_url": "https://x/42", "content": "build a query engine",
    }]}
    out = normalize_greenhouse("ClickHouse", payload)
    assert out == [{
        "company": "ClickHouse", "id": "42", "title": "Core C++ Engineer",
        "location": "Remote", "url": "https://x/42",
        "description": "build a query engine",
    }]


def test_normalize_adzuna():
    payload = {"results": [{
        "id": 7, "title": "Gameplay Programmer",
        "company": {"display_name": "Indie Studio"},
        "location": {"display_name": "Remote"},
        "redirect_url": "https://a/7", "description": "C++ Unreal gameplay",
    }]}
    out = normalize_adzuna(payload)
    assert out[0]["company"] == "Indie Studio" and out[0]["id"] == "7"


# --- aggregator -----------------------------------------------------------

def test_dedup_by_company_title():
    rows = [
        {"company": "X", "title": "C++ Engineer", "id": "1"},
        {"company": "X", "title": "c++ engineer", "id": "2"},  # dup (case)
        {"company": "Y", "title": "C++ Engineer", "id": "3"},
    ]
    assert len(dedup(rows)) == 2


def test_collect_aggregator_filters_tags_and_dedups(monkeypatch):
    fake = [
        {"company": "Indie", "id": "1", "title": "Gameplay Programmer (C++)",
         "location": "Remote", "url": "u1", "description": ""},
        {"company": "Indie", "id": "1b", "title": "Gameplay Programmer (C++)",
         "location": "Remote", "url": "u1b", "description": ""},   # dup title
        {"company": "BankCorp", "id": "2", "title": "Sales Director",
         "location": "NY", "url": "u2", "description": ""},          # excluded
    ]
    monkeypatch.setattr(M, "fetch_adzuna", lambda *a, **k: fake)
    monkeypatch.setenv("ADZUNA_APP_ID", "realid")
    monkeypatch.setenv("ADZUNA_APP_KEY", "realkey")
    cfg = {
        "aggregator": {"enabled": True, "countries": ["us"],
                       "queries": ["c++"], "results_per_page": 5},
    }
    mc = {"title": ["c++", "gameplay"], "desc_strong": [], "exclude": ["sales"]}
    out = collect_aggregator(cfg, mc)
    assert len(out) == 1                               # dup + excluded gone
    assert out[0]["company"] == M.AGGREGATOR_NAME      # retagged
    assert out[0]["source"] == "Indie"                 # real company kept


def test_collect_aggregator_skips_without_keys(monkeypatch):
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    cfg = {"aggregator": {"enabled": True, "queries": ["x"]}}
    assert collect_aggregator(cfg, {"title": [], "exclude": []}) is None


def test_normalize_lever():
    payload = [{
        "id": "abc", "text": "Kernel Engineer",
        "categories": {"location": "SF"}, "hostedUrl": "https://l/abc",
        "descriptionPlain": "linux kernel work",
    }]
    out = normalize_lever("Acme", payload)
    assert out[0]["id"] == "abc" and out[0]["location"] == "SF"
