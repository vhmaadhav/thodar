"use client";

import { useState } from "react";
import { API, fmtDate, type Thread } from "@/lib/api";

const SCRIPT =
  "We would like to send you reminders about your visits and your baby's vaccinations by WhatsApp or a phone " +
  "call. We use only your name, phone number and visit dates. You can say no, and you can reply STOP at any time.";

/** Consent under the DPDP Act: recorded by a nurse after reading the script, withdrawable any time. */
export default function ConsentCard({ thread, onChange }: { thread: Thread; onChange: () => void }) {
  const [busy, setBusy] = useState(false);

  async function patch(body: object) {
    setBusy(true);
    await fetch(`${API}/mothers/${thread.mother_id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    setBusy(false);
    onChange();
  }

  const status = thread.consent_at
    ? { cls: "done", text: `Consent recorded ${fmtDate(thread.consent_at.slice(0, 10))}` }
    : thread.opted_out
      ? { cls: "overdue", text: "Opted out: no automated reminders" }
      : { cls: "due_today", text: "No consent yet: reminders paused" };

  return (
    <section className="card pad" style={{ marginTop: 14, display: "grid", gap: 10 }}>
      <div className="toolbar" style={{ margin: 0 }}>
        <span className={`pill ${status.cls}`}>{status.text}</span>
        <span className="spacer" />
        <div className="seg" aria-label="Reminder language">
          {[
            ["ta", "Tamil"],
            ["en", "English"],
          ].map(([code, label]) => (
            <button key={code} className={thread.language === code ? "on" : ""} disabled={busy}
              onClick={() => patch({ language: code })}>
              {label}
            </button>
          ))}
        </div>
        {thread.consent_at ? (
          <button className="btn small" disabled={busy} onClick={() => patch({ consent: false })}>
            Withdraw consent
          </button>
        ) : (
          <button className="btn small primary" disabled={busy} onClick={() => patch({ consent: true })}>
            Family agreed: record consent
          </button>
        )}
      </div>
      {!thread.consent_at && (
        <p className="item-sub" style={{ margin: 0 }}>
          Read to the family first: “{SCRIPT}”
        </p>
      )}
    </section>
  );
}
