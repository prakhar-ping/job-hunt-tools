"""Offline tests for tailor + referral logic — no network, no API key."""
from referral.referral import filter_contacts, parse_contacts
from tailor.jd_fetch import clean_html, company_from_url
from tailor.tailor import is_resume_filled, slugify

# --- tailor ---------------------------------------------------------------

def test_company_from_greenhouse_url():
    assert company_from_url(
        "https://job-boards.greenhouse.io/clickhouse/jobs/123") == "clickhouse"


def test_company_from_plain_url():
    assert company_from_url("https://careers.cohesity.com/job/55") == "cohesity"


def test_clean_html_strips_scripts():
    html = "<html><script>x()</script><p>C++ Engineer</p><style>a{}</style></html>"
    out = clean_html(html)
    assert "C++ Engineer" in out and "x()" not in out and "a{}" not in out


def test_is_resume_filled():
    assert not is_resume_filled("## Summary\nTODO\n## Skills\nTODO\n## Exp\nTODO")
    real = "## Summary\n" + "Senior C++ engineer. " * 30
    assert is_resume_filled(real)


def test_slugify():
    assert slugify("Pure Storage") == "pure-storage"


# --- referral -------------------------------------------------------------

PASTE = """\
Asha Rao
Staff Software Engineer at Rubrik
2nd
Bob Smith
Account Executive at Rubrik
2nd
Carol Lin
Distributed Systems Engineer at MongoDB
3rd
"""


def test_parse_contacts_pairs_name_and_title():
    c = parse_contacts(PASTE)
    names = {x["name"] for x in c}
    assert {"Asha Rao", "Bob Smith", "Carol Lin"} <= names
    asha = next(x for x in c if x["name"] == "Asha Rao")
    assert asha["title"] == "Staff Software Engineer" and asha["company"] == "Rubrik"


def test_filter_keeps_eng_at_target_drops_others():
    kept = filter_contacts(parse_contacts(PASTE), "Rubrik")
    names = {x["name"] for x in kept}
    assert "Asha Rao" in names           # eng at Rubrik
    assert "Bob Smith" not in names      # account exec -> dropped
    assert "Carol Lin" not in names      # right title, wrong company


def test_filter_word_boundary_not_substring():
    # 'cto' must not match 'direCTOr'; whole-word CTO must.
    c = [{"name": "A", "title": "Sales Director", "company": "Rubrik"},
         {"name": "B", "title": "CTO", "company": "Rubrik"}]
    kept = {x["name"] for x in filter_contacts(c, "Rubrik")}
    assert kept == {"B"}
