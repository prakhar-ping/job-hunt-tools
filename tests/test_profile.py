"""Offline tests for resume->profile derivation and its use by monitor/web."""
import io

import monitor.monitor as M
import shared.profile as P
import web.app as webapp

RESUME = """
Prakhar Verma — Senior C++ Game Developer
Skills: C++ (C++17), C#, Lua, Unity, Unreal, OpenGL, memory allocator, profiling.
Experience programming gameplay, engine architecture, graphics, mobile.
"""


def test_heuristic_profile_extracts_terms():
    p = P.heuristic_profile(RESUME)
    assert "c++" in p["match"]["title"]
    assert "game" in p["match"]["title"] or "gameplay" in p["match"]["title"]
    assert "unity" in p["match"]["desc_strong"]      # rare tech -> desc_strong
    assert "sales" in p["match"]["exclude"]          # default excludes present
    assert p["queries"] and any("c++" in q for q in p["queries"])


def test_heuristic_handles_unknown_domain():
    p = P.heuristic_profile("Frontend React TypeScript developer, 5 years.")
    assert "typescript" in p["match"]["title"] or "javascript" in p["match"]["title"]
    assert "react" in p["match"]["desc_strong"]
    assert p["queries"]                              # never empty


def test_derive_profile_falls_back_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    p = P.derive_profile(RESUME, "claude-sonnet-4-6")
    assert "match" in p and "queries" in p           # heuristic path


def test_save_load_clear_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "PROFILE_PATH", tmp_path / "rp.json")
    assert P.load_profile() is None
    P.save_profile({"match": {"title": ["c++"]}, "queries": ["c++ dev"]}, "cv.pdf")
    got = P.load_profile()
    assert got["resume_name"] == "cv.pdf"
    P.clear_profile()
    assert P.load_profile() is None


def test_monitor_uses_profile_match_when_present(monkeypatch):
    # profile keywords override config keywords in run()
    prof = {"match": {"title": ["rust"], "desc_strong": [], "exclude": []},
            "queries": ["rust dev"], "resume_name": "cv.pdf"}
    monkeypatch.setattr(M, "load_profile", lambda: prof)
    monkeypatch.setattr(M, "load_config",
                        lambda *a, **k: {"companies": {}, "match": {"title": ["c++"]},
                                         "aggregator": {"enabled": False}})
    monkeypatch.setattr(M, "load_env", lambda: None)
    monkeypatch.setattr(M, "collect_aggregator", lambda *a, **k: None)
    report = M.run(dry_run=True)
    assert "resume: cv.pdf" in report                # source line reflects profile


def test_upload_route_derives_and_saves(monkeypatch, tmp_path):
    monkeypatch.setattr(webapp, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(webapp, "extract_resume_text", lambda p: "C++ engineer")
    monkeypatch.setattr(webapp, "derive_profile",
                        lambda text, model: {"match": {"title": ["c++"]},
                                             "queries": ["c++ dev"]})
    saved = {}
    monkeypatch.setattr(webapp, "save_profile",
                        lambda prof, resume_name="": saved.update(name=resume_name))
    monkeypatch.setattr(webapp, "run_monitor", lambda **k: "")
    monkeypatch.setattr(webapp, "load_config", lambda: {"model": "m"})
    client = webapp.app.test_client()
    data = {"resume": (io.BytesIO(b"fake"), "cv.pdf")}
    r = client.post("/upload-resume", data=data, content_type="multipart/form-data")
    assert r.status_code == 302
    assert saved.get("name") == "cv.pdf"
