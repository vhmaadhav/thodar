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

- [ ] Item 4 of the form — prompt not yet seen
- [ ] Real number from our paediatrician (e.g. staff hours/week chasing missed visits) for the deck
- [ ] Check name availability (Play Store / GitHub / web)
- [ ] Build 7-slide deck
- [ ] Optional clickable prototype for item 7

## Possible prototype stack (if we build one)

FastAPI + Postgres · schedule rules in YAML (ANC, PNC, UIP/IAP immunisation) · React/Next.js worklist + mother–baby timeline · WhatsApp sandbox (Twilio/Gupshup) or mocked chat · synthetic data (Synthea + messy CSVs to demo record linking).
