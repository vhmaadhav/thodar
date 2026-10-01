# Sarvam Voice Agent setup

Thodar's reminder calls run on **Sarvam Voice Agents** (Saaras v3 speech-to-text → Sarvam-105B → Bulbul v3 text-to-speech), over Exotel or a Sarvam-rented number. The agent is configured in the Sarvam dashboard; Thodar only exposes two tools.

## Tools

Both need the header `X-Thodar-Tool-Key: <THODAR_VOICE_TOOL_KEY>`.

| Tool | Endpoint | Input | Returns |
|---|---|---|---|
| `lookup_due_visit` | `POST /voice/tools/lookup` | `{ "phone": "<caller number>" }` | `{ found, name, language, due: { item_id, what, date } }` |
| `record_outcome` | `POST /voice/tools/update` | `{ item_id, outcome, new_date?, note? }` | `{ ok }` |

`outcome` is one of `confirmed`, `reschedule`, `moved`, `wrong_number`, `no_answer`, `needs_staff`.

## Agent prompt

```
You are a scheduling assistant calling on behalf of {clinic}. You speak Tamil by default and
switch to English if the caller does.

At the start of the call, use lookup_due_visit with the caller's number. Greet the person by
name and tell them what is due and on which date, in one short sentence.

You may only do these things:
- confirm they will come on that date        -> record_outcome(confirmed)
- agree a different date they ask for        -> record_outcome(reschedule, new_date)
- note that they have moved or it is the wrong number
- note that nobody answered                 -> record_outcome(no_answer)

If the caller mentions any health problem, symptom, medicine, test result, or asks for advice
about the mother or baby: do not answer or reassure. Say: "I will ask the nurse to call you
today. In an emergency, please call 108." Then record_outcome(needs_staff, note=<their words>)
and end the call politely.

Never give medical information. Never guess dates the caller did not agree to. Keep the call
under two minutes.
```

## Why this stays in scope

- The agent never sees clinical data: `lookup` returns only a plain-language visit name and a date.
- It can write only scheduling outcomes, each logged as a contact attempt with `actor = voice-agent`.
- Health questions always end in a handoff to a person.
