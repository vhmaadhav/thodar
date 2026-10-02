"""Records a ~1-minute captioned walkthrough of the live Thodar demo.

    uv run --with playwright python demo/record_demo.py [--url https://thodar.onrender.com]

Drives the installed Edge (or Chrome) with Playwright, captures lossless 1920x1080 frames and encodes
demo/thodar-demo.mp4 (H.264, high quality) with ffmpeg. Uses one live Sarvam voice-note call.
"""

import argparse
import base64
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE / "thodar-demo.mp4"
W, H = 1280, 720
SPEED = 1.17  # play back slightly faster so the walkthrough lands at about one minute

CAPTION_JS = """(text) => {
  let el = document.getElementById('demo-caption');
  if (!el) {
    el = document.createElement('div');
    el.id = 'demo-caption';
    Object.assign(el.style, {position: 'fixed', left: '50%', bottom: '28px', transform: 'translateX(-50%)',
      maxWidth: '1060px', padding: '14px 22px', borderRadius: '14px', background: 'rgba(30,43,42,0.94)',
      color: '#F4EFE4', font: '600 21px/1.35 "IBM Plex Sans", Arial, sans-serif', zIndex: 99999,
      boxShadow: '0 8px 28px rgba(0,0,0,0.25)', textAlign: 'center', transition: 'opacity .25s'});
    document.body.appendChild(el);
  }
  el.style.opacity = text ? '1' : '0';
  el.innerHTML = text;
}"""


def caption(page: Page, text: str, hold: float) -> None:
    page.evaluate(CAPTION_JS, text)
    page.wait_for_timeout(int(hold * 1000))


def run(url: str) -> None:
    raw_dir = Path(tempfile.mkdtemp(prefix="thodar-video-"))
    with sync_playwright() as pw:
        browser = None
        for channel in ("msedge", "chrome", None):
            try:
                browser = pw.chromium.launch(channel=channel) if channel else pw.chromium.launch()
                break
            except Exception:  # noqa: BLE001 - try the next browser
                continue
        # 1280x720 layout rendered at 1.5x = 1920x1080 real pixels; frames are lossless PNGs from the
        # DevTools screencast (Playwright's built-in recorder is low-bitrate VP8 and looks soft).
        ctx = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=1.5)
        page = ctx.new_page()
        frames: list[tuple[float, Path]] = []
        cdp = ctx.new_cdp_session(page)

        def on_frame(ev: dict) -> None:
            path = raw_dir / f"f{len(frames):05d}.png"
            path.write_bytes(base64.b64decode(ev["data"]))
            frames.append((ev["metadata"]["timestamp"], path))
            cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})

        cdp.on("Page.screencastFrame", on_frame)
        cdp.send("Page.startScreencast", {"format": "png", "maxWidth": 1920, "maxHeight": 1080, "everyNthFrame": 1})

        # 1. Sign in as the nurse
        page.goto(f"{url}/login", wait_until="networkidle")
        caption(page, "Thodar · one follow-up thread for every mother and baby<br>"
                      "<span style='font-weight:400'>Care-team sign-in · synthetic demo data</span>", 2.5)
        page.get_by_text("Revathi (nurse)").click()
        page.wait_for_url(f"{url}/", timeout=30000)
        page.get_by_text("Who needs follow-up").wait_for()
        page.get_by_text("Overdue visits").wait_for()
        page.wait_for_timeout(600)

        # 2. The morning worklist
        caption(page, "The nurse's morning: who is due, overdue or unreachable,<br>"
                      "sorted by days overdue. No clinical scores.", 3.8)
        page.mouse.wheel(0, 380)
        caption(page, "Handover: babies born this fortnight already have their<br>"
                      "newborn checks and vaccines scheduled for paediatrics", 3.3)

        # 3. One-trip reminders
        page.mouse.wheel(0, -380)
        page.get_by_role("button", name="Send today's WhatsApp reminders").click()
        page.wait_for_timeout(900)
        page.mouse.wheel(0, 300)
        caption(page, "One WhatsApp per family, in Tamil: the clinic's next Wednesday,<br>"
                      "mother's and baby's visits in one trip", 4.2)

        # 4. A real Tamil voice note, transcribed live by Sarvam Saaras
        page.get_by_text("Can't come today, Saturday").click()
        caption(page, "The family replies with a Tamil voice note…", 1.0)
        page.get_by_text("Heard", exact=False).wait_for(timeout=45000)
        caption(page, "Sarvam Saaras transcribes it live → both visits move to Saturday", 4.0)

        # 5. Safety: any health mention goes to a nurse
        page.get_by_text("Baby has fever 2 days").click()
        page.wait_for_function("() => document.body.innerText.includes('needs staff')", timeout=45000)
        page.wait_for_timeout(1200)
        page.mouse.wheel(0, -2000)
        caption(page, "“Baby has fever” → never answered by a bot: the family is told a nurse<br>"
                      "will call, and they jump to the top of the list", 4.2)

        # 6. The mother–baby thread
        caption(page, "", 0.2)
        page.get_by_role("link", name="Families").click()
        page.get_by_text("Anitha K").first.click()
        page.get_by_text("Delivered").wait_for(timeout=20000)
        page.wait_for_timeout(800)
        caption(page, "One thread per mother and baby: antenatal visits, the delivery<br>"
                      "handover, postnatal checks and the baby's vaccines", 3.8)

        # 7. Insights
        caption(page, "", 0.2)
        page.get_by_role("link", name="Insights").click()
        page.get_by_text("The journey, visit by visit").wait_for()
        page.wait_for_timeout(800)
        caption(page, "Where families drop off, visit by visit: the pilot's baseline,<br>"
                      "including families brought back into care", 3.5)

        # 8. Village health nurse field mode
        caption(page, "", 0.2)
        page.get_by_role("button", name="Sign out").click()
        page.get_by_text("Selvi (village health nurse)").click()
        page.get_by_text("Families to visit").wait_for(timeout=30000)
        page.wait_for_timeout(800)
        caption(page, "The village health nurse sees only her villages' home visits,<br>"
                      "and it keeps working offline", 3.5)
        caption(page, "Thodar · Doctors set the plan. Thodar makes sure it happens.<br>"
                      "<span style='font-weight:400'>Team Highest in the Room · Health-a-thon 2026</span>", 3.0)

        page.wait_for_timeout(300)
        cdp.send("Page.stopScreencast")
        end_ts = time.time()
        ctx.close()
        browser.close()

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is needed to encode the video")
    # The screencast only sends a frame when the screen changes: hold each frame until the next one.
    lines = []
    for i, (ts, path) in enumerate(frames):
        nxt = frames[i + 1][0] if i + 1 < len(frames) else end_ts
        lines.append(f"file '{path.as_posix()}'")
        lines.append(f"duration {max(nxt - ts, 1 / 30):.4f}")
    lines.append(f"file '{frames[-1][1].as_posix()}'")
    concat = raw_dir / "frames.txt"
    concat.write_text("\n".join(lines), encoding="utf-8")
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat),
                    "-vf", f"setpts=PTS/{SPEED},fps=30,scale=1920:1080:flags=lanczos,format=yuv420p", "-c:v", "libx264",
                    "-preset", "slow", "-crf", "16", "-tune", "stillimage", "-movflags", "+faststart", "-an",
                    str(OUT)], check=True)
    shutil.rmtree(raw_dir, ignore_errors=True)
    print(f"{OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="https://thodar.onrender.com")
    run(ap.parse_args().url.rstrip("/"))
