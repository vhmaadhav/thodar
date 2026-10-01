# Thodar (தொடர்)

**Bump to booster, no one lost.**

Thodar ("continue / follow through" in Tamil) is a follow-up desk for hospital and clinic care teams that ties mother and baby into one care thread — from the first antenatal visit to the child's second birthday.

> Health-a-thon 2026 · Round 1 · Track: Maternal & Women's Health · Use case: Patient Follow-up & Continuity of Care

## The problem

Families start care but don't stay in it. Nationally, 95.9% of women start antenatal care but only 65.2% complete four visits, and 87.1% of children are fully immunised (NFHS-6, 2023-24). Tamil Nadu is slipping on both. In hospitals and paediatric clinics, follow-up still runs on registers, spreadsheets and phone calls, and at delivery the mother's and baby's records split between obstetrics and paediatrics.

## What Thodar does

1. **Reads what teams already keep** — registers, Excel/CSV, HIS exports, FHIR where available. No new data entry.
2. **Links mother and baby** — by PICME/RCH ID, ABHA or phone; at delivery it auto-creates the baby's visit and vaccine schedule next to the mother's postnatal plan.
3. **Turns plans into due dates** — doctor-set follow-up plans plus national ANC, PNC and immunisation schedules.
4. **Morning worklist** — who is due, overdue or unreachable, sorted by days overdue, with one-tap actions: call, reschedule, request a village health nurse visit, notify the doctor.
5. **Two-way reminders** — WhatsApp or voice (IVR) in Tamil or English; families reply to confirm or reschedule, which updates the worklist and keeps phone numbers verified.

## Scope

Thodar makes **no clinical judgement**: no diagnosis, no treatment recommendations, no risk scoring, no interpretation of medical data. Doctors set the plan; Thodar makes sure it happens.

## How it fits

| | PICME / JANANI / U-WIN | Kilkari / mMitra | **Thodar** |
|---|---|---|---|
| Who uses it | Field nurses (VHN/ANM), ASHAs | Mothers (one-way voice) | **Hospital & clinic care teams, incl. private** |
| Mother–baby linked at birth | Separate modules | No | **Yes** |
| Extra data entry | High | None | **None** |
| Two-way family reply | No | Mostly no | **Yes** |

## Repo contents

- [`CONTEXT.md`](CONTEXT.md) — background, research, decisions and constraints behind the idea
- [`Thodar_Submission.md`](Thodar_Submission.md) — Round 1 form answers, deck outline and sources

## Run it locally

Needs Python 3.11+ with [uv](https://docs.astral.sh/uv/), and Node 20+.

```bash
# 1. Backend: generate synthetic registers, load them, start the API on :8000
cd backend
uv sync
uv run python scripts/generate_synthetic.py
uv run python scripts/seed_demo.py
uv run uvicorn thodar.api.main:app --port 8000
```

```bash
# 2. Front end on :3000 (in a second terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. API docs are at http://localhost:8000/docs.

**Demo in two minutes:** on the Worklist, press *Send today's WhatsApp reminders*. The phone panel shows the Tamil reminder; tap a sample reply such as *"இன்னைக்கு வர முடியாது, சனிக்கிழமை வரேன்"* (can't come today, will come Saturday) and watch the visit move to Saturday. Try *"குழந்தைக்கு காய்ச்சல்"* (baby has fever): it goes to staff and the family is told a nurse will call. Open a family to see the mother–baby thread, and *Insights* for the drop-off funnel.

With a Sarvam key in `backend/.env` (`THODAR_SARVAM_API_KEY=...`), the phone panel's 🎤 buttons send real Tamil voice notes: Saaras v3 transcribes them live, then the rules and Sarvam-105B (two safety locks) decide what happens. `uv run python scripts/smoke_sarvam.py` checks every Sarvam API.

Without API keys everything runs offline: WhatsApp messages land in the demo phone, and Sarvam calls fall back to rules or a person.

**One container:** `docker build -t thodar . && docker run -p 7860:7860 thodar` serves the whole demo on http://localhost:7860 (see [docs/deploy.md](docs/deploy.md), including Hugging Face Spaces).

### Configuration (`backend/.env`, all optional)

| Variable | Purpose |
|---|---|
| `THODAR_DATABASE_URL` | Defaults to SQLite; use `postgresql+psycopg://…` in production (`uv sync --extra postgres`) |
| `THODAR_SARVAM_API_KEY` | Enables Saaras v3 transcription of voice notes and the Sarvam-105B reply fallback |
| `THODAR_WHATSAPP_TOKEN`, `THODAR_WHATSAPP_PHONE_NUMBER_ID` | Send real WhatsApp messages via the Cloud API |
| `THODAR_WHATSAPP_VERIFY_TOKEN` | Webhook verification token |
| `THODAR_VOICE_TOOL_KEY` | Shared secret for the Sarvam voice agent's tool calls ([docs/voice-agent.md](docs/voice-agent.md)) |
| `THODAR_CLINIC_NAME` | Clinic name used in reminders |
| `THODAR_SESSION_DAYS` | Clinic ANC/immunisation days reminders propose (default `wed`) |
| `THODAR_AUTO_REMINDERS_AT` | Send reminders automatically each day at this IST time, e.g. `09:00` |
| `THODAR_STT_PROVIDER` | `sarvam` (default), `indicconformer` (self-hosted) or `elevenlabs` (needs `THODAR_ALLOW_OFFSHORE_PROCESSING=true`) |

### Tests

```bash
cd backend && uv run pytest
```

## How it is built

```
registers (CSV/Excel)   ─┐
paper photos (Sarvam Vision, nurse verifies) ─┤──► importer ──► record linking ──► one thread per mother–baby pair
                         ┘                       (IDs, phone, fuzzy name; unsure → review queue)
                                                         │
                         YAML schedules (ANC, PNC, UIP) ─┴─► schedule engine ──► dated visits
                                                                                   │ (missed after catch-up period)
                                                                                   ▼
                     nurse worklist (sorted by days overdue) ◄──── actions & replies ────► WhatsApp / Sarvam voice agent
                                                                                   │
                                                                                   ▼
                                                                    insights: drop-off funnel, on-time %, missed %
```

| Path | What it is |
|---|---|
| `backend/thodar/schedules/*.yaml` | ANC, PNC and immunisation schedules with windows and catch-up periods (clinical lead signs off) |
| `backend/thodar/schedule_engine.py` | Turns schedules into dated visits; delivery creates the baby's schedule; expiry marks missed visits |
| `backend/thodar/linking.py`, `importer.py` | Record linking and register import |
| `backend/thodar/worklist.py` | The morning worklist and nurse actions |
| `backend/thodar/messaging/` | WhatsApp, reply understanding (Tamil/English/Tanglish), Sarvam client, reminder runs |
| `backend/thodar/api/` | FastAPI app |
| `frontend/` | Next.js web app |
| `deck/` | Round 1 pitch deck source |

## Status

Working prototype on synthetic data, live-tested against Sarvam's APIs (Saaras v3, Bulbul v3, Sarvam-105B, Sarvam Vision). 63 automated tests; CI builds and runs the demo container. Ready to host on Hugging Face Spaces (`sh deploy/prepare_hf_space.sh`, see [docs/deploy.md](docs/deploy.md)); not deployed yet.

Before a pilot: clinical sign-off of schedules, catch-up periods and Tamil wording; a verified WhatsApp Business number; live Sarvam voice-agent calls; Postgres hosted in India.
