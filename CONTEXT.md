# Context

Working notes for the team: what the hackathon asks for, what we researched, and why Thodar looks the way it does.

## Hackathon

- **Event:** Health-a-thon 2026 (Koita Foundation, IIT Bombay KCDH, FOGSI, National Cancer Grid, RSSDI) — https://healthathon.reskilll.com
- **Round 1:** "Your Solution Idea" — 7 items: track/user/use case, problem (≤150 words), solution + name (≤150 words) + scope confirmation, item 4 (TBD), existing work, 6–8 slide deck (PDF/PPT ≤25 MB), optional links.
- **Chosen:** Track *Maternal & Women's Health* · user *Doctor / Care Team* · use case *Patient Follow-up & Continuity of Care* (Use case 01 of 07).

### Use case brief (summary)
Long-term care (cancer, diabetes, maternal health) needs patients engaged for months or years. Patients miss follow-ups, investigations and milestones; information is fragmented across appointment systems, EMRs, labs, registers and spreadsheets; care teams spend a lot of time finding and prioritising who needs follow-up. Wanted: early identification of patients needing follow-up, better visibility across fragmented data, coordinated follow-up, simpler workflows inside existing settings.

### Scope guardrail (hard constraint)
Out of scope: diagnosis, treatment recommendations, clinical decision support, **clinical risk scoring**, interpretation of medical data, autonomous clinical advice.

Consequences for our design:
- No dropout/clinical risk score. Worklist is sorted by **days overdue and contact attempts** only.
- No flagging of abnormal lab values.
- Clinical tags (e.g. high-risk pregnancy) come from the doctor; Thodar only applies the follow-up interval the doctor set.

## Team

- Includes a **paediatrician** → we chose the mother–baby continuum (pregnancy → age 2), where the obstetric-to-paediatric handover is the weak point.
- Name rule from the team: **Tamil + English, no Hindi.**

## Decisions log

| Decision | Why |
|---|---|
| Maternal & child, not diabetes | Paediatrician on team; biggest fragmentation is at delivery handover |
| Facility-side (hospital/clinic), not field-worker app | JANANI (May 2026) already gives ANMs/VHNs due lists; hospitals and private clinics have nothing comparable |
| Complement PICME/JANANI/U-WIN, don't replace | Avoid duplicating government systems; link by RCH ID / ABHA |
| Read existing files, no new data entry | JANANI's main risk is data-entry burden (ARMMAN, Jun 2026) |
| Two-way WhatsApp/IVR in Tamil + English | Top reasons for missed vaccines are no reminder / forgetting; replies keep phone numbers valid (Kilkari lost reach on bad numbers) |
| Name: Thodar (தொடர்) | Tamil for "continue / follow through"; ≥5 chars; backups Inai (இணை), Thaai-Sei (தாய்-சேய்) |
| Earlier names dropped | NaalLink, Dhaaga (Hindi roots) |

## Best tool per AI job (researched 1 Oct 2026)

Sarvam is the event partner, but each job uses whatever works best on Tamil clinic data. Providers are swappable; `backend/scripts/eval_stt.py` compares speech-to-text on our own consented clips.

| Job | Evidence | Choice |
|---|---|---|
| Voice-note transcription | Vimarsha (AI4Bharat, arXiv 2609.24199): open-source IndicConformer leads both splits, Saaras close and robust in noise. BRIDGE (Humyn Labs, May 2026): ElevenLabs Scribe v2 lowest WER (10.6%), Saaras 3rd (20.2%), Deepgram best on code-switching. Vendor-reported numbers ignored. | Swappable: Saaras (default, India), IndicConformer (MIT, self-hosted in India), ElevenLabs (offshore, blocked unless opted in). Decide with our own eval in week 1. |
| Handwritten register OCR | Sarvam Vision 2.1 (Sept 2026) leads published Indic handwriting results; Gemini Pro falls to ~50 on Indic handwriting (Analytics Vidhya review). | Sarvam Vision, nurse verifies every row. |
| Tamil reminder voice | Reviewers: Bulbul clearer on Indian accents; ElevenLabs more expressive. Clarity matters for reminders. | Bulbul v3. |
| Reply understanding | Rules are auditable; LLM only as a constrained fallback. | Rules, then Sarvam-105B limited to scheduling labels. |

## Improvement research (1 Oct 2026) and what we built from it

| Evidence | Built |
|---|---|
| Haryana immunisation RCT (Banerjee, Duflo et al., Econometrica 2025; J-PAL): reminders about the *next* vaccine + community ambassadors + incentives that grow along the schedule raised measles vaccination ~55%; reminders + ambassadors alone were cheaper per child than status quo | Reminders name the doses (e.g. "OPV-2, Penta-2, RVV-2"); VHN escalation stays the ambassador path |
| TN PHCs run ANC clinic and immunisation on a fixed day, Wednesday (NHM TN; The Hindu) | Reminders propose the next clinic session day (`THODAR_SESSION_DAYS`, default `wed`) |
| Transport and time are top barriers to PNC/immunisation | **One trip**: one message per family covering the mother's and baby's next visits together |
| Fewer than a third of new mothers take part in care decisions; ~70% of decisions made by one person, often father or grandmother (PLOS One 2025, 551 dyads) | Optional **family contact** (with consent) gets the same reminders and can reply |
| Dr Muthulakshmi Reddy scheme: Rs 2,000 at registration, Rs 4,000 at the 7th-month ANC, Rs 12,000 after delivery + BCG | Reminders and worklist mention the instalment a visit helps unlock (factual, "helps you become eligible") |
| Catch-up dosing needs minimum intervals; planning it is clinical | A trip includes only the next visit of each sequence; the message says the doctor plans the rest |

Deadline note: Round 1 idea submission extended to 3 Oct 2026 (organiser post).

## Research notes

**India, NFHS-6 (2023-24)** — PIB, 29 May 2026
- Any ANC 95.9%; ANC in 1st trimester 76.2%; **≥4 ANC 65.2%** (58.5% in NFHS-5)
- Institutional delivery 90.6%; newborn PNC within 2 days 85.3%
- **Full immunisation (card) 87.1%**; any vaccine >96%; MCV2 71.8%
- Women with own mobile 63.6%; ever used internet 64.3%

**Tamil Nadu, NFHS-6** — The New Indian Express, 31 May 2026
- Any ANC 95.8 → 92.2%; **≥4 ANC 90.6 → 87.6%** (urban 86.2% < rural 88.6%)
- **Full vaccination 90.4 → 89.7%**
- Institutional births 99.7%; govt-hospital share of deliveries 66.9 → 63.6%
- C-section 46.9% (60.3% in private hospitals)

**Existing systems**
- **PICME** (TN): pregnancy & infant cohort monitoring; 12-digit RCH ID; needed for birth certificate and Dr. Muthulakshmi Reddy maternity scheme.
- **JANANI** (MoHFW, May 2026): upgrade of RCH portal — longitudinal record, QR MCH cards, high-risk alerts, due lists, U-WIN/POSHAN integration, ABHA/Aadhaar registration. 1.34 crore registrations at launch.
- **U-WIN**: national immunisation event registry.
- **Kilkari / mMitra** (ARMMAN): one-way weekly voice messages; reach limited by inaccurate phone data.

**Evidence that reminders/follow-up work**
- Missed vaccination reasons: no prior reminder 32.9%, mother's forgetfulness 26.6% (Patel & Pandit 2011, Gujarat).
- SMS reminders cut unvaccinated children by ~15% (GiveWell, meta-analysis of 16 RCTs in LMICs).
- Delayed vaccination in India: BCG 23.1%, DPT1 29.3%, measles 34.8% (Choudhary et al. 2019).

## Open items

- [ ] Real number from our paediatrician (e.g. staff hours/week chasing missed visits) for the deck
- [ ] Check name availability (Play Store / GitHub / web)
- [ ] Build 7-slide deck
- [ ] Optional clickable prototype for item 7

## Planned stack (Item 4)

**Principle: Sarvam AI at the edges, fixed rules at the core.** AI only reads paper and talks to families. Due dates, ordering and ownership are deterministic rules, so nothing clinical is ever decided by a model.

| Layer | Choice | Why |
|---|---|---|
| Paper → data | **Sarvam Vision** (Document AI, `doc_ai.extract`) | Digitises photos of ANC/immunisation registers and MCP cards in Tamil + English into rows (name, RCH ID, phone, visit dates). Nurse verifies before saving. Clerical, not clinical |
| Reminder calls | **Sarvam Voice Agents** (Saaras v3 STT → Sarvam-105B → Bulbul v3 TTS) on **Exotel** or a Sarvam-rented number | Outbound Tamil/English calls; tool calls write `confirmed / reschedule(date) / moved / wrong number` back to our API. Any health question → "the nurse will call you" handoff |
| WhatsApp | **WhatsApp Cloud API** (Meta) with utility templates + quick-reply buttons | Sarvam's WhatsApp text agents are enterprise-only, so we run WhatsApp ourselves |
| Voice-note replies | **Saaras v3** (STT, code-mixed Tamil-English) + Sarvam-105B intent label | Families often reply by voice note; we turn it into a non-clinical intent + one-line summary for the nurse |
| Frontend | Next.js PWA | Nurse worklist + mother–baby timeline; installable, works on low-end phones |
| Backend | FastAPI (Python) + `sarvamai` SDK | Same language as import, linking and Sarvam SDK |
| Database | PostgreSQL | Mothers, babies, schedule items, contact attempts, audit log |
| Import | pandas (Excel/CSV); HAPI FHIR where available | PICME/JANANI have no open API → CSV/Excel exports |
| Record linking | Splink (probabilistic matching) | RCH ID, ABHA, phone, name, DOB; non-clinical |
| Schedules | Versioned YAML rules | ANC, PNC, UIP (+ IAP if the doctor chooses); doctor-set intervals |
| Identity | ABHA stored as a field; ABDM sandbox = stretch goal | Sandbox needs an HIP application/approval; not on the critical path |
| Hosting | AWS Mumbai (ap-south-1) | Data in India; Sarvam models are self-hosted in India and can run in our own AWS VPC |

Dropped from the earlier draft: Bhashini (Sarvam covers TTS/STT and is the official partner); fine-tuned Whisper (Saaras v3 already handles Tamil/code-mixed speech).

## Feasibility

**Hackathon facts** (healthathon.reskilll.com, checked 1 Oct 2026)
- **Sarvam AI is the official technology partner**; prizes include technology credits.
- Design bar: "Leverage existing AI capabilities – agents, orchestration frameworks, APIs and open-source tools"; work with existing workflows; assistive, human-centred, **measurable within 60–90 days**.
- Use only fake or fully anonymised data.
- Build sprint: 5 weeks online, 5 Oct – 8 Nov 2026. Top 30 by 14 Nov. Finale 28 Nov 2026, IIT Bombay.

**Cost per family (estimate, Oct 2026 list prices)**
| Item | Rate | Source |
|---|---|---|
| WhatsApp utility message (India) | ~₹0.12–0.15 / delivered msg (Meta now charges in-window utility too from 1 Oct 2026) | Meta rate cards via BSP blogs |
| Saaras v3 STT | ₹30 / hour (₹0.50 / min) | docs.sarvam.ai/pricing |
| Bulbul v3 TTS | ₹30 / 10K chars | docs.sarvam.ai/pricing |
| Sarvam-105B | ₹29 in / ₹73 out per 1M tokens | docs.sarvam.ai/pricing |
| Sarvam Vision extract | ₹1 / page (10 pages/job, 10 req/min) | docs.sarvam.ai/pricing |
| AI voice call, all-in | ~₹1–1.5 / min incl. telephony | third-party Sarvam call estimates |
| Free credits | ₹100 per new Sarvam account | docs.sarvam.ai/pricing |

Rough total: 2–3 WhatsApp nudges + one ~1.5-min call for non-responders ≈ **₹2–3 per due visit**, far below a staff phone call's time cost. Verify before quoting on slides.

**Risks and mitigations**
| Risk | Mitigation |
|---|---|
| WhatsApp template approval / business verification takes time | Start Meta verification in week 1; demo with Meta test number |
| Handwriting OCR errors on registers | Nurse confirm screen; never auto-save; Excel import as primary path |
| LLM says something clinical on a call | Narrow prompt + tool-only actions; health questions always hand off; transcripts logged for audit |
| No open API for PICME/JANANI/U-WIN | Import their CSV/Excel exports; no write-back in the prototype |
| Families without smartphones (~36% of women lack own phone) | Voice call path; shared family number allowed |
| DPDP Act consent | Consent captured at registration; opt-out keyword on every message |

## 5-week build plan (5 Oct – 8 Nov)

| Week | Deliverable |
|---|---|
| 1 | Synthetic data (mothers + babies, messy CSVs), schema, YAML schedules (ANC, PNC, UIP), Meta + Sarvam accounts |
| 2 | Import + Splink linking + delivery event creates baby schedule; worklist API |
| 3 | Next.js worklist + timeline; WhatsApp templates and quick-reply webhook |
| 4 | Sarvam Voice Agent (Tamil/English) with tool calls; Saaras voice-note intent; Sarvam Vision register import |
| 5 | Dashboard (on-time %, days overdue, reach rate), guardrail tests, pilot playbook, demo video |

Demo data: synthetic (Synthea + deliberately messy CSVs to show record linking).
