"""Builds Thodar_Pitch_Deck.pdf from the slide sources using the installed Microsoft Edge (or Chrome).

    uv run --with playwright python deck/build_pdf.py

Each <section> becomes one 1920x1080 page. The deck format's custom elements are translated to plain
HTML/SVG; speaker notes (<aside>) are left out of the PDF.
"""

import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "Thodar_Pitch_Deck.pdf"

LINK_ICON = ('<svg viewBox="0 0 24 24" style="{style}" fill="none" stroke="currentColor" stroke-width="2" '
             'stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.07 0l3-3a5 5 0 0 0-7.07-7.07l-1 1"/>'
             '<path d="M14 11a5 5 0 0 0-7.07 0l-3 3a5 5 0 0 0 7.07 7.07l1-1"/></svg>')


def style_value(style: str, prop: str) -> str | None:
    m = re.search(rf"(?:^|;)\s*{prop}\s*:\s*([^;]+)", style)
    return m.group(1).strip() if m else None


def translate(html: str) -> str:
    html = re.sub(r"<aside>.*?</aside>", "", html, flags=re.S)

    def shape(m: re.Match) -> str:
        attrs = m.group(1)
        kind = re.search(r'kind="([a-z-]+)"', attrs).group(1)
        style = re.search(r'style="([^"]*)"', attrs).group(1)
        if kind == "ellipse":
            return f'<div style="{style};border-radius:50%"></div>'
        if kind == "arrow-right":
            color = style_value(style, "background") or "#000"
            rest = re.sub(r"background\s*:[^;]+;?", "", style)
            return (f'<svg viewBox="0 0 10 5" preserveAspectRatio="none" style="{rest};flex:none">'
                    f'<polygon points="0,1.5 6,1.5 6,0 10,2.5 6,5 6,3.5 0,3.5" fill="{color}"/></svg>')
        return f'<div style="{style}"></div>'

    html = re.sub(r"<x-shape([^>]*)></x-shape>", shape, html)
    html = re.sub(r'<x-icon name="Link" style="([^"]*)"></x-icon>', lambda m: LINK_ICON.format(style=m.group(1)), html)
    return html


def main() -> None:
    deck = json.loads((HERE / "deck.json").read_text(encoding="utf-8"))
    fonts = "".join(f'<link rel="stylesheet" href="{f["href"]}">' for f in deck["faces"].values() if "href" in f)
    slides = [translate((HERE / "slides" / f"{sid}.html").read_text(encoding="utf-8")) for sid in deck["order"]]
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>{deck['title']}</title>{fonts}
<style>
@page {{ size: 1920px 1080px; margin: 0; }}
html, body {{ margin: 0; padding: 0; }}
section {{ position: relative; width: 1920px; height: 1080px; box-sizing: border-box; overflow: hidden;
          page-break-after: always; break-after: page; }}
section *, section *::before, section *::after {{ box-sizing: border-box; }}
h1, h2, h3, p, ul, ol {{ margin: 0; }}
ul {{ padding-left: 1.2em; }}
table {{ border-collapse: collapse; }}
th, td {{ border-bottom: 1px solid rgba(30,43,42,0.15); vertical-align: top; }}
</style></head><body>{''.join(slides)}</body></html>"""
    src = HERE / "_print.html"
    src.write_text(page, encoding="utf-8")

    # Playwright drives the installed Edge (channel "msedge") or Chrome: no browser download needed.
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = None
        for channel in ("msedge", "chrome", None):
            try:
                browser = pw.chromium.launch(channel=channel) if channel else pw.chromium.launch()
                break
            except Exception:  # noqa: BLE001 - try the next browser
                continue
        if browser is None:
            sys.exit("No Edge or Chrome found for Playwright")
        page_ = browser.new_page(viewport={"width": 1920, "height": 1080})
        page_.goto(src.as_uri(), wait_until="networkidle")
        page_.evaluate("document.fonts.ready")
        page_.pdf(path=str(OUT), width="1920px", height="1080px", print_background=True,
                  margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
        browser.close()
    src.unlink()
    print(f"{OUT} ({OUT.stat().st_size // 1024} KB, {len(slides)} slides)")


if __name__ == "__main__":
    main()
