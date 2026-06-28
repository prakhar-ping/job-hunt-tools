"""Localhost job dashboard — view current matched jobs in a browser.

Reads the monitor's snapshots (the current matched listings per source) and
renders them grouped, filterable, with a Refresh button that re-runs the
scrape (no email/notification).

Run:  ./.venv/bin/python -m web      then open http://127.0.0.1:5000
"""
from __future__ import annotations

import datetime as dt
import json

from flask import Flask, redirect, render_template_string, url_for

from monitor.monitor import SNAP_DIR
from monitor.monitor import run as run_monitor

app = Flask(__name__)


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
</style></head>
<body>
<header>
  <h1>Job Monitor</h1>
  <span class="muted">{{ total }} matches · {{ jobs|length }} sources · {{ today }}</span>
  <input type="search" id="q" placeholder="Filter title / company / location…"
         oninput="filt()" autofocus>
  <form method="post" action="{{ url_for('refresh') }}" style="margin:0">
    <button>↻ Refresh</button>
  </form>
</header>
<main id="list">
{% for source, items in jobs.items() %}
  <section data-source="{{ source }}">
    <h2>{{ source }} <span class="muted">({{ items|length }})</span></h2>
    {% for j in items %}
      <div class="job">
        <a href="{{ j.url }}" target="_blank" rel="noopener">{{ j.title }}</a>
        {% if j.source %}<span class="src">@ {{ j.source }}</span>{% endif %}
        {% if j.location %}<span class="loc"> — {{ j.location }}</span>{% endif %}
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
                                  today=dt.date.today().isoformat())


@app.route("/refresh", methods=["POST"])
def refresh():
    run_monitor(dry_run=False, deliver=False)  # update snapshots, no email/notif
    return redirect(url_for("index"))


def main():
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
