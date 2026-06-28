"""Tests for resume parsing + PDF rendering (offline)."""
from shared.pdf import build_resume_html, resume_pdf
from tailor.resume_model import parse_resume_md
from tailor.tailor import _validated

RESUME_MD = """# Jane Doe — Master Resume

**C++ Engineer · Systems**

jane@example.com · +1-555 · linkedin.com/in/jane · Berlin

## Profile
Senior C++ engineer with 8 years building storage engines.

## Technical Skills
- **Languages:** C++, Rust, Python
- **Systems:** distributed systems, storage engines

## Experience

### Staff Engineer — Acme (2020 – Present, Berlin)
- Built a write-ahead log cutting recovery time 40%.
- Led a team of 5.

## Key Projects
### LSM Storage Engine
*C++ · RocksDB*
- Designed compaction strategy.

## Education
B.Sc Computer Science · TU Berlin · 2016

_References available on request_
"""


def test_parse_resume_md():
    d = parse_resume_md(RESUME_MD)
    assert d["name"] == "Jane Doe"
    assert d["tagline"] == "C++ Engineer · Systems"
    assert "jane@example.com" in d["contact"]
    assert d["skills"][0] == {"label": "Languages", "value": "C++, Rust, Python"}
    exp = d["experience"][0]
    assert exp["title"] == "Staff Engineer" and exp["company"] == "Acme"
    assert exp["dates"] == "2020 – Present" and exp["location"] == "Berlin"
    assert len(exp["bullets"]) == 2
    assert d["projects"][0]["name"] == "LSM Storage Engine"
    assert d["projects"][0]["stack"] == "C++ · RocksDB"
    assert "TU Berlin" in d["education"]
    assert d["footer"].startswith("References")


def test_build_html_has_sections():
    html = build_resume_html(parse_resume_md(RESUME_MD))
    assert "JANE DOE" in html                     # name upper-cased
    assert "Technical Skills" in html and "Experience" in html
    assert "▸" in html                            # bullet marker


def test_resume_pdf_bytes():
    pdf = resume_pdf(parse_resume_md(RESUME_MD))
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_validated_falls_back_on_bad_shape():
    baseline = parse_resume_md(RESUME_MD)
    # model returned a string instead of dict -> baseline
    assert _validated("garbage", baseline) == baseline
    # model dropped a key -> baseline value kept
    partial = {"summary": "new summary"}
    out = _validated(partial, baseline)
    assert out["summary"] == "new summary" and out["name"] == baseline["name"]
