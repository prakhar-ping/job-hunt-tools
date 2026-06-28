"""Render markdown (a tailored resume) to a PDF byte string. Pure-python."""
from __future__ import annotations

import io

import markdown as _md
from xhtml2pdf import pisa

# Print-friendly resume styling for xhtml2pdf (a subset of CSS).
_CSS = """
@page { size: A4; margin: 1.6cm 1.8cm; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 10.5pt;
       color: #1a1a1a; line-height: 1.35; }
h1 { font-size: 19pt; margin: 0 0 2pt 0; }
h2 { font-size: 12pt; margin: 14pt 0 4pt 0; border-bottom: 1px solid #888;
     padding-bottom: 2pt; text-transform: uppercase; letter-spacing: 0.5pt; }
h3 { font-size: 11pt; margin: 8pt 0 1pt 0; }
ul { margin: 2pt 0 6pt 0; }
li { margin-bottom: 2pt; }
p { margin: 2pt 0; }
a { color: #1a1a1a; text-decoration: none; }
"""


def markdown_to_pdf(markdown_text: str) -> bytes:
    """Convert markdown to a styled PDF, returned as bytes."""
    body = _md.markdown(markdown_text, extensions=["tables", "sane_lists"])
    html = f"<html><head><style>{_CSS}</style></head><body>{body}</body></html>"
    buf = io.BytesIO()
    pisa.CreatePDF(src=html, dest=buf, encoding="utf-8")
    return buf.getvalue()
