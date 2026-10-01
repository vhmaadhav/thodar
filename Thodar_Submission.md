# Thodar (தொடர்) — Round 1 submission answers
*Health-a-thon 2026 · Highest in the Room*

**Thodar** (Tamil: தொடர்) = "continue / follow through".
**Tagline:** *Bump to booster, no one lost.*
**One line:** One follow-up thread for every mother and baby — from first ANC visit to the child's second birthday.

---

## Item 1 · Track, user and use case
- **Track:** Maternal & Women's Health
- **Primary user:** Doctor / Care Team
- **Use case:** Patient Follow-up & Continuity of Care

## Item 2 · The problem (145 words · 906 chars)
From pregnancy to a child's second birthday, a mother and baby need more than a dozen scheduled visits, and families drop off along the way. Nationally, 95.9% of women start antenatal care but only 65.2% complete four visits, and only 87.1% of children are fully immunised (NFHS-6, 2023-24). Even Tamil Nadu is slipping: four-visit ANC fell from 90.6% to 87.6% and full vaccination from 90.4% to 89.7%, with urban women doing worse than rural. PICME, JANANI and U-WIN give field nurses due lists, but in hospitals and paediatric clinics, especially private ones, follow-up still runs on registers, spreadsheets and phone calls. At delivery the mother's file stays with obstetrics and the baby's starts in paediatrics; nobody owns the whole journey. Misses are noticed late, yet are often preventable: in one Indian study, no reminder (32.9%) and forgetting (26.6%) were the top reasons for missed vaccines.

## Item 3 · Solution (146 words · 912 chars)
**Solution name:** Thodar

Thodar is a follow-up desk for hospital and clinic care teams that ties mother and baby into one thread, from first ANC visit to the child's second birthday. It reads the registers, spreadsheets and HIS exports teams already keep, links records by PICME/RCH ID, ABHA or phone, and at delivery auto-creates the baby's visit and vaccine schedule alongside the mother's postnatal plan. Doctor-set plans and national schedules become due dates. Nurses see who is due, overdue or unreachable, sorted by days overdue, with one-tap actions: call, reschedule, request a village health nurse visit, or notify the doctor. Families get WhatsApp or voice reminders in Tamil or English and reply to confirm or reschedule, which updates the list and keeps phone numbers verified. Thodar complements PICME and JANANI, needs no new data entry, and makes no clinical judgement: doctors set the plan; Thodar makes sure it happens.

**Scope checkbox:** ✅ Tick. Sorting is by days overdue and contact attempts (scheduling, not clinical risk). No risk scores, no lab interpretation, no advice. If a doctor tags a case, Thodar only applies the follow-up interval the doctor set.

## Item 4 · How you will build it (72 words · 522 chars)
Sarvam AI at the edges, fixed rules at the core. Sarvam Vision digitises paper registers and MCP cards; nurses verify. Sarvam Voice Agents (Saaras v3, Sarvam-105B, Bulbul v3) on Exotel make Tamil/English reminder calls, logging confirm/reschedule via tool calls; any health question goes to staff. WhatsApp Cloud API quick-replies; Saaras transcribes voice-note replies. Next.js PWA, FastAPI, PostgreSQL; ANC/PNC/UIP schedules as versioned YAML rules; Splink record linking. India-hosted (AWS Mumbai), synthetic data only.

## Item 5 · Existing work
**No — we are building a new solution.** (Switch to "Yes" only if a teammate is reusing prior code/product, and name it.)

## Item 6 · Pitch deck (7 slides)
1. **Title** — Thodar · தொடர் · tagline · team (paediatrician first)
2. **The leak** — funnel: 95.9% start ANC → 65.2% complete 4; 96% any vaccine → 87.1% full. TN slipping (ANC4 90.6→87.6%, urban 86.2% < rural 88.6%)
3. **Why it happens** — records split at delivery; hospital/clinic follow-up on paper; no reminder 32.9% + forgot 26.6%; 34.8% measles doses delayed
4. **Thodar flow** — existing files → linked mother–baby thread → due dates → morning worklist → Tamil/English WhatsApp/IVR → reply updates list
5. **Product** — mockups: thread timeline, nurse worklist, WhatsApp chat
6. **Fit & trust** — complements PICME/JANANI/U-WIN (comparison table); no clinical judgement; consent + DPDP Act; ABHA/RCH ID
7. **Impact & pilot** — metrics: on-time ANC/PNC, vaccine series on time, days-overdue, staff hours saved; 3-month pilot at our paediatrician's site

### Positioning table (slide 6)
| | PICME / JANANI / U-WIN | Kilkari / mMitra | **Thodar** |
|---|---|---|---|
| Who uses it | Field nurses (VHN/ANM), ASHAs | Mothers (one-way voice) | **Hospital & clinic care teams, incl. private** |
| Mother–baby linked at birth | Separate modules | No | **Yes — baby schedule auto-created** |
| Extra data entry | High | None | **None — reads existing files** |
| Two-way family reply | No | Mostly no | **Yes — confirm / reschedule** |

## Item 7 · Links (optional)
Team LinkedIn profiles, GitHub repo, clickable prototype link.

---

## Evidence & sources
- NFHS-6 India (2023-24): ANC any 95.9%, ANC4 65.2%, full immunisation (card) 87.1%, MCV2 71.8%, newborn PNC ≤2 days 85.3%; women with own mobile 63.6% — PIB, 29 May 2026 (Release ID 2266600)
- NFHS-6 Tamil Nadu: ANC any 95.8→92.2%, ANC4 90.6→87.6% (urban 86.2%, rural 88.6%), full vaccination 90.4→89.7%, govt-hospital delivery share 66.9→63.6% — The New Indian Express, 31 May 2026
- JANANI launched May 2026 (RCH portal upgrade: due lists, alerts, U-WIN integration) — PIB Release ID 2258625; adoption/data-entry burden risk — ARMMAN, 26 Jun 2026
- Reasons for missed vaccination: no reminder 32.9%, forgetfulness 26.6% — Patel & Pandit 2011, Anand district, Gujarat (cited in GiveWell / PMC6598255)
- SMS reminders reduce unvaccinated children by ~15% (meta-analysis of 16 RCTs in LMICs) — GiveWell
- Delayed vaccination in India: BCG 23.1%, DPT1 29.3%, measles 34.8% — Choudhary et al. 2019 (PMC6996155)
- Kilkari listenership loss from inaccurate phone data — ARMMAN; Google (participation drop ~23%)
