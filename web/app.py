"""Localhost job dashboard — view current matched jobs in a browser.

Reads the monitor's snapshots (the current matched listings per source) and
renders them grouped, filterable, with a Refresh button that re-runs the
scrape (no email/notification).

Run:  ./.venv/bin/python -m web      then open http://127.0.0.1:5000
"""
from __future__ import annotations

import datetime as dt
import json
import threading
from pathlib import Path

import markdown as md
from flask import Flask, redirect, render_template_string, request, url_for

from monitor.monitor import SNAP_DIR, load_config
from monitor.monitor import run as run_monitor
from shared.profile import (
    clear_profile,
    derive_profile,
    extract_resume_text,
    load_profile,
    save_profile,
)
from tailor.tailor import run as tailor_run

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "shared" / "uploads"

app = Flask(__name__)

# Background scrape state — the scrape is slow (network), so it runs off the
# request thread and the page polls until it finishes.
_refresh = {"running": False}
_refresh_lock = threading.Lock()


def trigger_refresh() -> None:
    """Start a background scrape if one isn't already running."""
    with _refresh_lock:
        if _refresh["running"]:
            return
        _refresh["running"] = True

    def _work():
        try:
            run_monitor(dry_run=False, deliver=False)
        finally:
            _refresh["running"] = False

    threading.Thread(target=_work, daemon=True).start()


def load_jobs() -> dict[str, list[dict]]:
    """Read all snapshot files -> {source: [listings]}, sorted, biggest first."""
    data: dict[str, list[dict]] = {}
    if SNAP_DIR.exists():
        for f in sorted(SNAP_DIR.glob("*.json")):
            try:
                listings = json.loads(f.read_text())
            except (json.JSONDecodeError, OSError):
                listings = []
            if listings:
                name = listings[0].get("company") or f.stem.replace("_", " ")
                data[name] = listings
    return dict(sorted(data.items(), key=lambda kv: len(kv[1]), reverse=True))


TEMPLATE = """
<!doctype html>
<html><head><meta charset="utf-8"><title>Job Monitor</title>
{% if refreshing %}<meta http-equiv="refresh" content="4">{% endif %}
<style>
  :root { color-scheme: light dark; }
  body { font: 15px/1.5 -apple-system, system-ui, sans-serif; margin: 0;
         background: #0f1115; color: #e6e6e6; }
  header { position: sticky; top: 0; background: #171a21; padding: 16px 24px;
           border-bottom: 1px solid #2a2e37; display: flex; gap: 16px;
           align-items: center; flex-wrap: wrap; }
  h1 { font-size: 18px; margin: 0; }
  .muted { color: #8b93a1; }
  input[type=search] { flex: 1; min-width: 200px; padding: 8px 12px;
           border-radius: 8px; border: 1px solid #2a2e37; background: #0f1115;
           color: #e6e6e6; }
  button { padding: 8px 14px; border-radius: 8px; border: 0; cursor: pointer;
           background: #3b82f6; color: #fff; font-weight: 600; }
  main { padding: 16px 24px 64px; }
  section { margin-bottom: 24px; }
  h2 { font-size: 15px; border-bottom: 1px solid #2a2e37; padding-bottom: 6px; }
  .job { padding: 6px 0; border-bottom: 1px solid #1c2027; }
  .job a { color: #7dd3fc; text-decoration: none; }
  .job a:hover { text-decoration: underline; }
  .loc { color: #8b93a1; font-size: 13px; }
  .src { color: #a78bfa; font-size: 12px; }
  .hidden { display: none; }
  button.tailor { padding: 2px 8px; font-size: 12px; font-weight: 500;
                  background: #1f2937; color: #93c5fd; }
  button.tailor:hover { background: #374151; }
</style></head>
<body>
<header>
  <h1>Job Monitor</h1>
  <span class="muted">{{ total }} matches · {{ jobs|length }} sources · {{ today }}</span>
  <input type="search" id="q" placeholder="Filter title / company / location…"
         oninput="filt()" autofocus>
  <form method="post" action="{{ url_for('refresh') }}" style="margin:0">
    <button {% if refreshing %}disabled{% endif %}>↻ Refresh</button>
  </form>
</header>
{% if refreshing %}
<div style="padding:8px 24px;background:#1e2a16;border-bottom:1px solid #2a2e37;
            color:#a7f3a0">⟳ Refreshing jobs in the background… this page updates
   automatically.</div>
{% endif %}
<div style="padding:10px 24px;background:#12151c;border-bottom:1px solid #2a2e37;
            display:flex;gap:14px;align-items:center;flex-wrap:wrap">
  {% if profile %}
    <span class="src">▣ Searching from resume:
      <b>{{ profile.resume_name or 'uploaded' }}</b></span>
    <span class="muted">queries: {{ profile.queries|join(', ') }}</span>
    <form method="post" action="{{ url_for('clear_resume') }}" style="margin:0">
      <button style="background:#444">Use config instead</button>
    </form>
  {% else %}
    <span class="muted">▣ Searching from <b>config.yaml</b>.</span>
  {% endif %}
  <form method="post" action="{{ url_for('upload_resume') }}"
        enctype="multipart/form-data" style="margin:0;display:flex;gap:8px">
    <input type="file" name="resume" accept=".pdf,.md,.txt" required>
    <button>⬆ Upload resume{% if profile %} (replace){% endif %}</button>
  </form>
</div>
<main id="list">
{% for source, items in jobs.items() %}
  <section data-source="{{ source }}">
    <h2>{{ source }} <span class="muted">({{ items|length }})</span></h2>
    {% for j in items %}
      <div class="job">
        <a href="{{ j.url }}" target="_blank" rel="noopener">{{ j.title }}</a>
        {% if j.source %}<span class="src">@ {{ j.source }}</span>{% endif %}
        {% if j.location %}<span class="loc"> — {{ j.location }}</span>{% endif %}
        <form method="post" action="{{ url_for('tailor') }}" target="_blank"
              style="display:inline;margin-left:8px">
          <input type="hidden" name="url" value="{{ j.url }}">
          <input type="hidden" name="title" value="{{ j.title }}">
          <button class="tailor">✎ Tailor</button>
        </form>
      </div>
    {% endfor %}
  </section>
{% else %}
  <p class="muted">No jobs yet. Hit Refresh, or run <code>python -m monitor</code>.</p>
{% endfor %}
</main>
<script>
function filt() {
  const q = document.getElementById('q').value.toLowerCase();
  document.querySelectorAll('section').forEach(sec => {
    let shown = 0;
    sec.querySelectorAll('.job').forEach(j => {
      const hit = j.textContent.toLowerCase().includes(q);
      j.classList.toggle('hidden', !hit);
      if (hit) shown++;
    });
    sec.classList.toggle('hidden', shown === 0);
  });
}
</script>
</body></html>
"""


@app.route("/")
def index():
    jobs = load_jobs()
    total = sum(len(v) for v in jobs.values())
    return render_template_string(TEMPLATE, jobs=jobs, total=total,
                                  profile=load_profile(),
                                  refreshing=_refresh["running"],
                                  today=dt.date.today().isoformat())


RESULT_TEMPLATE = """
<!doctype html>
<html><head><meta charset="utf-8"><title>Tailored — {{ title }}</title>
<style>
  body { font: 16px/1.6 -apple-system, system-ui, sans-serif;
         background: #0f1115; color: #e6e6e6; max-width: 820px;
         margin: 0 auto; padding: 24px; }
  a { color: #7dd3fc; }
  h1 { font-size: 20px; } h2 { font-size: 16px; border-bottom: 1px solid #2a2e37;
       padding-bottom: 4px; margin-top: 28px; }
  code, pre { background: #171a21; border-radius: 6px; padding: 1px 5px; }
  .back { color: #93c5fd; text-decoration: none; }
</style></head>
<body>
  <a class="back" href="{{ url_for('index') }}">← back to jobs</a>
  <h1>Tailored resume — {{ title }}</h1>
  {{ body|safe }}
</body></html>
"""


@app.route("/tailor", methods=["POST"])
def tailor():
    """Tailor the master resume to one job's JD. Needs ANTHROPIC_API_KEY."""
    url = request.form.get("url", "")
    title = request.form.get("title", "job")
    if not url:
        return redirect(url_for("index"))
    try:
        result = tailor_run(url)
    except Exception as e:  # missing key, fetch failure, etc.
        result = (f"**Could not tailor.** {e}\n\n"
                  "If this is about the API key, add `ANTHROPIC_API_KEY` to "
                  "`.env` (console.anthropic.com) and try again.")
    body = md.markdown(result, extensions=["fenced_code", "tables"])
    return render_template_string(RESULT_TEMPLATE, title=title, body=body)


@app.route("/refresh", methods=["POST"])
def refresh():
    trigger_refresh()                       # background; returns immediately
    return redirect(url_for("index"))


@app.route("/upload-resume", methods=["POST"])
def upload_resume():
    f = request.files.get("resume")
    if not f or not f.filename:
        return redirect(url_for("index"))
    UPLOAD_DIR.mkdir(exist_ok=True)
    dest = UPLOAD_DIR / Path(f.filename).name
    f.save(dest)
    text = extract_resume_text(dest)
    model = load_config().get("model", "claude-sonnet-4-6")
    profile = derive_profile(text, model)
    save_profile(profile, resume_name=dest.name)
    trigger_refresh()                       # re-scrape with resume keywords
    return redirect(url_for("index"))


@app.route("/clear-resume", methods=["POST"])
def clear_resume():
    clear_profile()
    trigger_refresh()                       # back to config keywords
    return redirect(url_for("index"))


def main():
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)


if __name__ == "__main__":
    main()
