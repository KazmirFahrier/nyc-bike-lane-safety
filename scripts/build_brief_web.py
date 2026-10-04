"""Build the web brief from the same Markdown source as the PDF."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIEF = ROOT / "docs" / "brief"


def main() -> None:
    body = subprocess.run([
        "pandoc", str(BRIEF / "brief.md"),
        "--from", "markdown+pipe_tables+implicit_figures", "--to", "html5",
        "--wrap", "none",
    ], check=True, capture_output=True, text=True).stdout
    body = body.replace("../../analysis/output/", "../assets/")
    css = (BRIEF / "web.css").read_text()
    html = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Protected bike lanes and cyclist injuries in NYC</title>'
            f'<style>{css}</style></head><body><main class="wrap">{body}</main></body></html>')
    (BRIEF / "brief_web.html").write_text(html)
    print("wrote docs/brief/brief_web.html from brief.md")


if __name__ == "__main__":
    main()
