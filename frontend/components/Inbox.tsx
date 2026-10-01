"use client";

import { useEffect, useState } from "react";
import { api, type FamilySummary, postJSON } from "@/lib/api";

interface InboxMsg {
  id: number;
  phone: string;
  kind: string;
  text: string | null;
  received_at: string;
}

/** Messages from numbers not on file (new SIM, a relative's phone). A person attaches them to a family. */
export default function Inbox() {
  const [msgs, setMsgs] = useState<InboxMsg[]>([]);
  const [families, setFamilies] = useState<FamilySummary[]>([]);
  const [pick, setPick] = useState<Record<number, string>>({});
  const [tick, setTick] = useState(0);

  useEffect(() => {
    api<InboxMsg[]>("/inbox").then(setMsgs).catch(() => setMsgs([]));
    api<FamilySummary[]>("/families").then(setFamilies).catch(() => setFamilies([]));
  }, [tick]);

  async function attach(m: InboxMsg, as: "mother" | "family") {
    const motherId = Number(pick[m.id]);
    if (!motherId) return;
    await postJSON(`/inbox/${m.id}/attach`, { mother_id: motherId, as });
    setTick((t) => t + 1);
  }

  return (
    <section className="card pad" style={{ marginTop: 18 }}>
      <p className="eyebrow">Messages from unknown numbers</p>
      <p className="sub">
        A new SIM or a relative&apos;s phone. Nothing is dropped: attach the number to the right family and its next
        messages are understood.
      </p>
      {msgs.length === 0 && <p className="empty">No unknown messages.</p>}
      {msgs.length > 0 && (
        <table className="plain" style={{ marginTop: 10 }}>
          <thead>
            <tr>
              <th>From</th>
              <th>Message</th>
              <th>Received</th>
              <th>Belongs to</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {msgs.map((m) => (
              <tr key={m.id}>
                <td>+91 {m.phone}</td>
                <td>
                  {m.kind === "audio" ? "🎤 " : ""}
                  {m.text ?? <span className="item-sub">(voice note, not transcribed)</span>}
                </td>
                <td className="item-sub">{new Date(m.received_at).toLocaleString("en-IN")}</td>
                <td>
                  <select
                    className="btn small"
                    value={pick[m.id] ?? ""}
                    onChange={(e) => setPick((p) => ({ ...p, [m.id]: e.target.value }))}
                  >
                    <option value="">Choose a family…</option>
                    {families.map((f) => (
                      <option key={f.mother_id} value={f.mother_id}>
                        {f.name} · {f.village ?? ""}
                      </option>
                    ))}
                  </select>
                </td>
                <td style={{ whiteSpace: "nowrap" }}>
                  <button className="btn small" disabled={!pick[m.id]} onClick={() => attach(m, "mother")}>
                    Mother&apos;s new number
                  </button>{" "}
                  <button className="btn small" disabled={!pick[m.id]} onClick={() => attach(m, "family")}>
                    Family contact
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
