"""Compares speech-to-text providers on OUR audio, not vendor leaderboards.

Put consented, de-identified voice notes in a folder as pairs: `001.ogg` + `001.txt` (the correct
transcript, typed by a Tamil speaker on the team). Then:

    uv run python scripts/eval_stt.py --data ../data/stt-eval --providers sarvam indicconformer

Prints word and character error rates per provider. Pick the provider with THODAR_STT_PROVIDER.
Also scores what matters to Thodar: whether the reply's meaning (confirm / reschedule / needs
staff ...) survives transcription.
"""

import argparse
import unicodedata
from datetime import date
from pathlib import Path

from rapidfuzz.distance import Levenshtein

from thodar.ai.stt import get_stt
from thodar.messaging.intents import classify

AUDIO = {".ogg", ".opus", ".mp3", ".wav", ".m4a", ".aac", ".amr"}


def norm(text: str) -> str:
    text = unicodedata.normalize("NFC", text.lower())
    # Keep letters, numbers AND combining marks: Tamil vowel signs (e.g. ி, ை) are marks, not letters.
    keep = ("L", "M", "N")
    return " ".join("".join(c if unicodedata.category(c)[0] in keep else " " for c in text).split())


def error_rates(ref: str, hyp: str) -> tuple[float, float]:
    r, h = norm(ref), norm(hyp)
    wer = Levenshtein.distance(r.split(), h.split()) / max(len(r.split()), 1)
    cer = Levenshtein.distance(r, h) / max(len(r), 1)
    return wer, cer


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--providers", nargs="+", default=["sarvam", "indicconformer"])
    ap.add_argument("--language", default="ta")
    args = ap.parse_args()

    pairs = [(a, a.with_suffix(".txt")) for a in sorted(Path(args.data).iterdir())
             if a.suffix.lower() in AUDIO and a.with_suffix(".txt").exists()]
    if not pairs:
        raise SystemExit("No audio + .txt pairs found.")
    today = date.today()

    print(f"{len(pairs)} clips\n{'provider':<42}{'WER':>8}{'CER':>8}{'intent kept':>14}{'failed':>8}")
    for name in args.providers:
        stt = get_stt(provider=name)
        wers, cers, kept, failed = [], [], 0, 0
        for audio, ref_path in pairs:
            ref = ref_path.read_text(encoding="utf-8").strip()
            try:
                hyp = stt.transcribe(audio.read_bytes(), audio.name, args.language) or ""
            except Exception:  # noqa: BLE001 - a provider error counts as a failed clip
                hyp = ""
            if not hyp:
                failed += 1
            w, c = error_rates(ref, hyp)
            wers.append(w)
            cers.append(c)
            kept += classify(ref, today).kind == classify(hyp, today).kind
        n = len(pairs)
        print(f"{stt.name:<42}{sum(wers) / n:>8.1%}{sum(cers) / n:>8.1%}{kept / n:>14.0%}{failed:>8}")


if __name__ == "__main__":
    main()
