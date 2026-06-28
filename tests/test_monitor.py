"""Offline tests for monitor logic — no network, no API key."""
from monitor.monitor import diff_new, matches_keywords
from monitor.scrapers import normalize_greenhouse, normalize_lever

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


def test_normalize_lever():
    payload = [{
        "id": "abc", "text": "Kernel Engineer",
        "categories": {"location": "SF"}, "hostedUrl": "https://l/abc",
        "descriptionPlain": "linux kernel work",
    }]
    out = normalize_lever("Acme", payload)
    assert out[0]["id"] == "abc" and out[0]["location"] == "SF"
