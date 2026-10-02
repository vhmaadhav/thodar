"""Renders docs/rationale.html to docs/Thodar_Design_Rationale.pdf with the installed Edge/Chrome.

    uv run --with playwright python docs/build_rationale.py
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
SRC, OUT = HERE / "rationale.html", HERE / "Thodar_Design_Rationale.pdf"

with sync_playwright() as pw:
    browser = None
    for channel in ("msedge", "chrome", None):
        try:
            browser = pw.chromium.launch(channel=channel) if channel else pw.chromium.launch()
            break
        except Exception:  # noqa: BLE001 - try the next browser
            continue
    page = browser.new_page()
    page.goto(SRC.as_uri(), wait_until="networkidle")
    page.evaluate("document.fonts.ready")
    page.pdf(path=str(OUT), format="A4", print_background=True, prefer_css_page_size=True)
    browser.close()
print(f"{OUT} ({OUT.stat().st_size // 1024} KB)")
