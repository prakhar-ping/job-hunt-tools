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
import uuid
from pathlib import Path

from flask import (
    Flask,
    Response,
    redirect,
    render_template_string,
    request,
    url_for,
)

from monitor.monitor import SNAP_DIR, load_config
from monitor.monitor import run as run_monitor
from shared.pdf import resume_pdf
from shared.profile import (
    clear_profile,
    derive_profile,
    extract_resume_text,
    load_profile,
    save_profile,
)
from tailor.tailor import slugify, tailor_resume_structured

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "shared" / "uploads"

app = Flask(__name__)

# Background work state — slow steps (LLM keyword derivation, the network
# scrape) run off the request thread; the page polls until they finish.
_refresh = {"running": False}
_refresh_lock = threading.Lock()


def _start_background(work) -> bool:
    """Run work() in a daemon thread if nothing is already running.
    Returns False if busy (the caller's work is skipped)."""
    with _refresh_lock:
        if _refresh["running"]:
            return False
        _refresh["running"] = True

    def _run():
        try:
            work()
        finally:
            _refresh["running"] = False

    threading.Thread(target=_run, daemon=True).start()
    return True


def trigger_refresh() -> None:
    """Scrape in the background (Refresh button / clearing the resume)."""
    _start_background(lambda: run_monitor(dry_run=False, deliver=False))


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
            color:#a7f3a0">⟳ Working in the background (reading resume / refreshing
   jobs)… this page updates automatically.</div>
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
          <button class="tailor">✎ Tailor + ATS</button>
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


_tailor_cache: dict[str, dict] = {}  # tid -> {data, company}

RESULT_TEMPLATE = """
<!doctype html>
<html><head><meta charset="utf-8"><title>Tailored — {{ title }}</title>
<style>
  body { font: 15px/1.6 -apple-system, system-ui, sans-serif;
         background: #0f1115; color: #e6e6e6; max-width: 860px;
         margin: 0 auto; padding: 24px; }
  a { color: #7dd3fc; }
  .back { color: #93c5fd; text-decoration: none; }
  h1 { font-size: 20px; margin: 8px 0 4px; }
  .score { font-size: 40px; font-weight: 800; }
  .bar { height: 10px; background: #20242c; border-radius: 6px; overflow: hidden;
         margin: 8px 0 4px; }
  .bar > div { height: 100%; }
  .kw { display: inline-block; padding: 2px 9px; margin: 3px 4px 0 0;
        border-radius: 12px; font-size: 12.5px; }
  .hit { background: #14351f; color: #86efac; }
  .miss { background: #3a1d1d; color: #fca5a5; }
  .dl { display: inline-block; margin: 18px 0 4px; padding: 11px 18px;
        background: #3b82f6; color: #fff; font-weight: 700; border-radius: 8px;
        text-decoration: none; }
  .note { color: #8b93a1; font-size: 13px; margin-top: 14px; }
  {% if error %}.err { background:#3a1d1d; padding:14px; border-radius:8px; }{% endif %}
</style></head>
<body>
  <a class="back" href="{{ url_for('index') }}">← back to jobs</a>
  <h1>Tailored resume — {{ title }}</h1>
  {% if error %}
    <div class="err">{{ error }}</div>
  {% else %}
    {% set c = '#22c55e' if ats.pct >= 70
       else '#eab308' if ats.pct >= 45 else '#ef4444' %}
    <div class="score" style="color:{{ c }}">{{ ats.pct }}% ATS match</div>
    <div class="bar"><div style="width:{{ ats.pct }}%;background:{{ c }}"></div></div>
    <div class="note">{{ ats.matched|length }} of {{ ats.total }} JD keywords present
      in your tailored resume.</div>

    <p style="margin-top:16px"><b>Matched</b> (in your resume):</p>
    {% for k in ats.matched %}<span class="kw hit">{{ k }}</span>{% endfor %}

    <p style="margin-top:14px"><b>Missing</b> (the JD wants these, your resume
      doesn't show them):</p>
    {% for k in ats.missing %}<span class="kw miss">{{ k }}</span>{% endfor %}

    <div><a class="dl"
      href="{{ url_for('tailor_pdf', tid=tid) }}">⬇ Download tailored PDF</a></div>

    <div class="note">Missing keywords are genuine gaps — the tool will not invent
      them (fabricated skills get you auto-rejected and burn the referral). A score
      under ~45% usually means this role doesn't fit your profile; aim your energy
      at higher-scoring postings.</div>
  {% endif %}
</body></html>
"""


@app.route("/tailor", methods=["POST"])
def tailor():
    """Tailor the resume to a job: show the ATS score, then offer the PDF."""
    url = request.form.get("url", "")
    title = request.form.get("title", "job")
    if not url:
        return redirect(url_for("index"))
    try:
        data, company, ats = tailor_resume_structured(url)
    except Exception as e:  # LLM down, fetch failure, template resume, etc.
        err = (f"Could not tailor: {e}. Check that Ollama is running "
               "(brew services start ollama) or that the configured provider works.")
        return render_template_string(RESULT_TEMPLATE, title=title, error=err)
    tid = uuid.uuid4().hex
    _tailor_cache[tid] = {"data": data, "company": company}
    return render_template_string(RESULT_TEMPLATE, title=title, ats=ats, tid=tid,
                                  error=None)


@app.route("/tailor-pdf/<tid>")
def tailor_pdf(tid):
    """Download the PDF for an already-tailored result (no re-run)."""
    entry = _tailor_cache.get(tid)
    if not entry:
        return redirect(url_for("index"))
    pdf = resume_pdf(entry["data"])
    fname = f"resume-{slugify(entry['company'])}-{dt.date.today().isoformat()}.pdf"
    return Response(pdf, mimetype="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


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
    f.save(dest)                              # fast: just write the file
    text = extract_resume_text(dest)         # fast: ~0.1s
    llm = load_config()["llm"]
    name = dest.name

    def work():                              # slow: LLM derivation + scrape
        save_profile(derive_profile(text, llm), resume_name=name)
        run_monitor(dry_run=False, deliver=False)

    _start_background(work)                   # returns immediately
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
