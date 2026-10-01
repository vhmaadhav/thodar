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

## Status

Idea stage (Round 1). No code yet.
