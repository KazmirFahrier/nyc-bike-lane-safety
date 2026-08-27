"""Inline the exported data into the dashboard template.

The page must be self-contained -- the artifact CSP blocks fetch to any external
host, and a local fetch() of data.json fails under file:// too. So the JSON is
substituted into the template at build time rather than loaded at runtime.

Usage:
    python scripts/build_dashboard.py
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "docs" / "dashboard"

SCRIPT_RE = re.compile(r"(<script\b[^>]*>)(.*?)(</script>)", re.S | re.I)


def _to_ascii(html: str) -> str:
    r"""Make the document pure ASCII, escaping correctly for each context.

    The page is published as a fragment wrapped in a host's own <head>, so it
    cannot declare a charset; served without one a browser falls back to
    Latin-1 and mangles every dash. But the two contexts need different
    escapes, and using one everywhere is a real bug rather than a cosmetic one:
    an HTML parser does NOT decode entities inside <script>, so an en dash
    written as &#8211; in a JS string literal reaches the page as the literal
    six characters. That shipped once and showed up as "2013&#8211;2024" in the
    KPI captions.

    Outside script: numeric character references.
    Inside script:  JavaScript \uXXXX escapes.
    """
    def js_escape(m: re.Match) -> str:
        open_tag, body, close_tag = m.groups()
        body = "".join(c if ord(c) < 128 else f"\\u{ord(c):04x}" for c in body)
        return open_tag + body + close_tag

    parts, last = [], 0
    for m in SCRIPT_RE.finditer(html):
        parts.append(html[last:m.start()].encode("ascii", "xmlcharrefreplace").decode("ascii"))
        parts.append(js_escape(m))
        last = m.end()
    parts.append(html[last:].encode("ascii", "xmlcharrefreplace").decode("ascii"))
    return "".join(parts)


def main() -> None:
    tpl = (D / "template.html").read_text()
    data = (D / "data.json").read_text()
    assert "/*DATA*/" in tpl, "template lost its data placeholder"
    html = tpl.replace("/*DATA*/", data)

    html = _to_ascii(html)

    out = D / "dashboard.html"
    out.write_text(html, encoding="ascii")
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size/1024:,.0f} KB)")


if __name__ == "__main__":
    main()
