"""Smoke tests for the Flask dashboard — no network."""
import json

import web.app as webapp


def test_index_renders(monkeypatch):
    fake = {
        "Riot": [{"company": "Riot", "title": "Gameplay Programmer (C++)",
                  "url": "https://x/1", "location": "LA", "source": ""}],
        "Web (Adzuna)": [{"company": "Web (Adzuna)", "title": "Engine Dev",
                          "url": "https://x/2", "location": "Remote",
                          "source": "2K"}],
    }
    monkeypatch.setattr(webapp, "load_jobs", lambda: fake)
    client = webapp.app.test_client()
    r = client.get("/")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Gameplay Programmer (C++)" in body
    assert "2 matches" in body
    assert "@ 2K" in body                 # aggregator source shown


def test_tailor_route_returns_pdf(monkeypatch):
    monkeypatch.setattr(webapp, "tailor_resume_structured",
                        lambda url: ({"name": "X"}, "ClickHouse"))
    monkeypatch.setattr(webapp, "resume_pdf", lambda data: b"%PDF-1.4 fake")
    client = webapp.app.test_client()
    r = client.post("/tailor", data={"url": "http://x/1", "title": "C++ Dev"})
    assert r.status_code == 200
    assert r.mimetype == "application/pdf"
    assert r.data.startswith(b"%PDF")
    assert "attachment" in r.headers["Content-Disposition"]
    assert "clickhouse" in r.headers["Content-Disposition"]


def test_tailor_route_handles_error(monkeypatch):
    def boom(url):
        raise RuntimeError("Ollama not reachable")
    monkeypatch.setattr(webapp, "tailor_resume_structured", boom)
    r = webapp.app.test_client().post("/tailor", data={"url": "u", "title": "t"})
    body = r.get_data(as_text=True)
    assert r.status_code == 200 and "Could not generate" in body


def test_load_jobs_reads_snapshots(tmp_path, monkeypatch):
    snap = tmp_path / "snaps"
    snap.mkdir()
    (snap / "Riot.json").write_text(json.dumps(
        [{"company": "Riot", "title": "T", "url": "u", "location": "L"}]))
    (snap / "Empty.json").write_text("[]")
    monkeypatch.setattr(webapp, "SNAP_DIR", snap)
    jobs = webapp.load_jobs()
    assert list(jobs) == ["Riot"]         # empty file skipped
    assert jobs["Riot"][0]["title"] == "T"
