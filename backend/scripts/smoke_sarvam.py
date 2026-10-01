"""Live check of every Sarvam API Thodar uses. Costs a few rupees of credit.

    uv run python scripts/smoke_sarvam.py

1. Bulbul v3 speaks a Tamil reminder        -> ../data/generated/reminder_ta.wav
2. Bulbul speaks a family's Tamil reply, then Saaras v3 transcribes it back (round trip)
3. Sarvam-105B labels replies the rules could not place
"""

import base64
import time
from datetime import date
from pathlib import Path

from thodar.messaging.intents import classify
from thodar.messaging.sarvam import SarvamClient

OUT = Path(__file__).resolve().parents[2] / "data" / "generated"


def timed(label, fn):
    t = time.perf_counter()
    try:
        out = fn()
        print(f"  ok   {label} ({time.perf_counter() - t:.1f}s)")
        return out
    except Exception as e:  # noqa: BLE001
        print(f"  FAIL {label}: {e}")
        return None


def main() -> None:
    c = SarvamClient()
    if not c.enabled:
        raise SystemExit("Set THODAR_SARVAM_API_KEY in backend/.env")
    OUT.mkdir(parents=True, exist_ok=True)
    today = date.today()

    print("1. Text-to-speech (Bulbul v3)")
    reminder = "வணக்கம் மீனா! உங்கள் குழந்தையின் தடுப்பூசி வியாழன் அன்று மருத்துவமனையில் உள்ளது. வர முடியுமா?"
    audio = timed("Tamil reminder", lambda: c.speak(reminder, "ta-IN"))
    if audio:
        (OUT / "reminder_ta.wav").write_bytes(base64.b64decode(audio))
        print(f"       saved {OUT / 'reminder_ta.wav'}")

    print("2. Speech-to-text round trip (Bulbul -> Saaras v3)")
    reply = "இன்னைக்கு வர முடியாது, சனிக்கிழமை வரேன்"
    reply_audio = timed("speak the family's reply", lambda: c.speak(reply, "ta-IN"))
    if reply_audio:
        wav = base64.b64decode(reply_audio)
        (OUT / "reply_ta.wav").write_bytes(wav)
        text = timed("transcribe it", lambda: c.transcribe(wav, "reply_ta.wav", "ta-IN"))
        print(f"       said:  {reply}\n       heard: {text}")
        if text:
            print(f"       rules read it as: {classify(text, today).kind}")

    print("3. Sarvam-105B fallback for replies the rules cannot place")
    for msg in ["en ponnu ku udambu konjam sari illa, next week varalama", "Thursday morning possible ah?",
                "naan ippo Chennai la irukken"]:
        rule = classify(msg, today)
        llm = timed(f"label {msg!r}", lambda m=msg: c.classify(m, today.isoformat()))
        print(f"       rules: {rule.kind:<12} model: {llm}")


if __name__ == "__main__":
    main()
