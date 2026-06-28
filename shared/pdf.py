"""Render a structured resume dict to a PDF that matches the user's own layout.

Pure-python (xhtml2pdf). A fixed template keeps every tailored PDF on the same
1-2 page design instead of whatever markdown the model emits.
"""
from __future__ import annotations

import io
import re
from html import escape

from xhtml2pdf import pisa

NAVY = "#1a2238"
GRAY = "#5a5f6b"
LINE = "#3a3f4b"
LINK = "#2156a5"

_CSS = f"""
@page {{ size: A4; margin: 1.05cm 1.35cm; }}
body {{ font-family: Times, "Times New Roman", serif; font-size: 9.4pt;
        color: #20242c; line-height: 1.32; }}
.name {{ font-family: Helvetica, Arial, sans-serif; font-size: 20pt;
         font-weight: bold; letter-spacing: 1.2pt; color: {NAVY}; }}
.tagline {{ font-family: Helvetica, Arial, sans-serif; font-size: 8.4pt;
            color: {GRAY}; margin-top: 2pt; }}
.contact {{ font-size: 8.6pt; color: #2b2f38; margin-top: 3pt; }}
.contact a, .link {{ color: {LINK}; }}
h2 {{ font-family: Helvetica, Arial, sans-serif; font-size: 9.5pt;
      font-weight: bold; letter-spacing: 1pt; color: {NAVY};
      border-bottom: 1px solid {LINE}; padding-bottom: 2pt;
      margin: 11pt 0 5pt 0; }}
.summary {{ text-align: justify; }}
table.skills {{ width: 100%; -pdf-keep-in-frame-mode: shrink; }}
td.k {{ font-family: Helvetica, Arial, sans-serif; font-weight: bold;
        width: 20%; vertical-align: top; padding: 1.6pt 8pt 1.6pt 0;
        color: {NAVY}; font-size: 8.8pt; }}
td.v {{ vertical-align: top; padding: 1.6pt 0; }}
.role {{ font-family: Helvetica, Arial, sans-serif; margin-top: 6pt;
         font-size: 9.4pt; }}
.role b {{ color: {NAVY}; }}
.meta {{ color: {GRAY}; }}
.bullet {{ padding-left: 11pt; text-indent: -10pt; margin: 1.8pt 0; }}
.pname {{ font-family: Helvetica, Arial, sans-serif; font-weight: bold;
          color: {NAVY}; margin-top: 6pt; }}
.stack {{ color: {GRAY}; font-style: italic; font-size: 8.6pt; margin: 1pt 0; }}
.footer {{ text-align: center; color: {GRAY}; font-style: italic;
           font-size: 8pt; margin-top: 10pt; }}
"""


def _link_contact(text: str) -> str:
    out = escape(text)
    return re.sub(r"(linkedin\.com/[^\s·]+)", r'<span class="link">\1</span>', out)


def _bullets_html(bullets: list[str]) -> str:
    return "".join(f'<div class="bullet">▸ {escape(b)}</div>' for b in bullets)


def build_resume_html(d: dict) -> str:
    parts = [f'<div class="name">{escape(d.get("name", "")).upper()}</div>']
    if d.get("tagline"):
        parts.append(f'<div class="tagline">{escape(d["tagline"])}</div>')
    if d.get("contact"):
        parts.append(f'<div class="contact">{_link_contact(d["contact"])}</div>')

    if d.get("summary"):
        parts.append("<h2>Profile</h2>"
                     f'<div class="summary">{escape(d["summary"])}</div>')

    if d.get("skills"):
        rows = "".join(
            f'<tr><td class="k">{escape(s.get("label", ""))}</td>'
            f'<td class="v">{escape(s.get("value", ""))}</td></tr>'
            for s in d["skills"])
        parts.append(f'<h2>Technical Skills</h2><table class="skills">{rows}</table>')

    if d.get("experience"):
        parts.append("<h2>Experience</h2>")
        for r in d["experience"]:
            meta = " · ".join(x for x in (r.get("dates"), r.get("location")) if x)
            head = f'<b>{escape(r.get("title", ""))}</b>'
            if r.get("company"):
                head += f' &nbsp;|&nbsp; {escape(r["company"])}'
            if meta:
                head += f' &nbsp;<span class="meta">| {escape(meta)}</span>'
            parts.append(f'<div class="role">{head}</div>')
            parts.append(_bullets_html(r.get("bullets", [])))

    if d.get("projects"):
        parts.append("<h2>Key Projects</h2>")
        for p in d["projects"]:
            parts.append(f'<div class="pname">{escape(p.get("name", ""))}</div>')
            if p.get("stack"):
                parts.append(f'<div class="stack">{escape(p["stack"])}</div>')
            parts.append(_bullets_html(p.get("bullets", [])))

    if d.get("education"):
        parts.append(f'<h2>Education</h2><div>{escape(d["education"])}</div>')
    if d.get("footer"):
        parts.append(f'<div class="footer">{escape(d["footer"])}</div>')

    return f"<html><head><style>{_CSS}</style></head><body>{''.join(parts)}</body></html>"


def resume_pdf(data: dict) -> bytes:
    """Structured resume dict -> styled PDF bytes."""
    buf = io.BytesIO()
    pisa.CreatePDF(src=build_resume_html(data), dest=buf, encoding="utf-8")
    return buf.getvalue()


# Kept for any plain-markdown rendering needs / fallback.
def markdown_to_pdf(markdown_text: str) -> bytes:
    import markdown as _md
    body = _md.markdown(markdown_text, extensions=["tables", "sane_lists"])
    html = (f"<html><head><style>{_CSS}</style></head>"
            f"<body>{body}</body></html>")
    buf = io.BytesIO()
    pisa.CreatePDF(src=html, dest=buf, encoding="utf-8")
    return buf.getvalue()
