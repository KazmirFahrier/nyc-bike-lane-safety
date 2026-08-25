"""Render the policy brief to PDF.

Markdown is the source of truth so the brief lives in version control and
diffs like anything else. pandoc converts it to HTML, WeasyPrint applies the
print stylesheet and paginates. No LaTeX toolchain required, which keeps the
whole project reproducible from a clean macOS checkout.

Usage:
    python scripts/build_brief.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# WeasyPrint reaches Pango/cairo/GObject through cffi, which uses the dynamic
# loader rather than Python's import path. Homebrew installs those dylibs into
# a prefix the loader does not search by default on Apple silicon, so set the
# fallback path here rather than requiring every caller to remember it.
# Needs: brew install pango gdk-pixbuf
for _prefix in ("/opt/homebrew/lib", "/usr/local/lib"):
    if os.path.isdir(_prefix):
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = (
            _prefix + os.pathsep + os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
        )

ROOT = Path(__file__).resolve().parents[1]
BRIEF = ROOT / "docs" / "brief"


def main() -> None:
    md = BRIEF / "brief.md"
    html = BRIEF / "brief.html"
    pdf = BRIEF / "protected-bike-lanes-brief.pdf"

    # --standalone gives a full document; --embed-resources inlines the figures
    # so the HTML is portable on its own as well.
    subprocess.run([
        "pandoc", str(md),
        "--from", "markdown+pipe_tables+implicit_figures",
        "--to", "html5", "--standalone", "--embed-resources",
        # `pagetitle`, not `title`: `title` makes pandoc's html5 template emit a
        # title block in the body, which duplicates the H1 already in the
        # markdown. `pagetitle` sets only the <title> element.
        "--metadata", "pagetitle=Did New York's protected bike lanes make cycling safer?",
        "--css", "brief.css",
        "--resource-path", f"{BRIEF}:{ROOT}",
        "-o", str(html),
    ], check=True, cwd=BRIEF)

    from weasyprint import HTML
    HTML(filename=str(html), base_url=str(BRIEF)).write_pdf(str(pdf))

    kb = pdf.stat().st_size / 1024
    print(f"wrote {pdf.relative_to(ROOT)} ({kb:,.0f} KB)")

    try:
        import pypdf
        n = len(pypdf.PdfReader(str(pdf)).pages)
        print(f"pages: {n}")
    except ImportError:
        pass


if __name__ == "__main__":
    main()
