"""Offline tests for ATS keyword extraction + scoring."""
from tailor.ats import heuristic_keywords, score


def test_score_counts_whole_word_matches():
    resume = "Senior C++ engineer with caching and profiling experience."
    kws = ["c++", "caching", "kubernetes", "profiling"]
    s = score(resume, kws)
    assert s["total"] == 4
    assert set(s["matched"]) == {"c++", "caching", "profiling"}
    assert s["missing"] == ["kubernetes"]
    assert s["pct"] == 75


def test_score_no_substring_false_positive():
    # 'java' must not match 'javascript'
    s = score("I write JavaScript daily.", ["java"])
    assert s["missing"] == ["java"] and s["pct"] == 0


def test_heuristic_keywords_pulls_terms():
    jd = ("We need a C++ engineer for distributed systems. Distributed systems "
          "experience and C++ are required. Kubernetes a plus.")
    kws = heuristic_keywords(jd)
    assert any("c++" in k for k in kws)
    assert any("distributed" in k for k in kws)
