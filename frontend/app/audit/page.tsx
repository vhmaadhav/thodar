"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface Event {
  at: string;
  staff: string;
  action: string;
  target_type: string | null;
  target_id: number | null;
  detail: string | null;
}

const LABEL: Record<string, string> = {
  sign_in: "Signed in",
  family_exported: "Exported a family's data",
  family_erased: "Erased a family's data",
  family_updated: "Updated family details",
  register_imported: "Imported a register",
  number_attached: "Attached a number to a family",
  link_review_dismissed: "Dismissed a record match",
  reminders_sent: "Sent WhatsApp reminders",
  staff_created: "Created a staff account",
  staff_deactivated: "Deactivated a staff account",
};

function label(action: string) {
  if (LABEL[action]) return LABEL[action];
  if (action.startsWith("visit_")) return `Visit: ${action.slice(6).replace("_", " ")}`;
  return action;
}

export default function AuditPage() {
  const [events, setEvents] = useState<Event[] | null>(null);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Event[]>("/audit?limit=500").then(setEvents).catch((e) => setError((e as Error).message));
  }, []);

  const shown = (events ?? []).filter(
    (e) => !filter || `${e.staff} ${label(e.action)} ${e.detail ?? ""}`.toLowerCase().includes(filter.toLowerCase()),
  );

  return (
    <main>
      <p className="eyebrow">Accountability</p>
      <h1 className="page-title">Audit trail</h1>
      <p className="sub">
        Every change to family data, who made it and when. Erasures keep only a count, never the erased details.
      </p>
      <div className="toolbar">
        <input className="btn" style={{ minWidth: 260 }} placeholder="Filter by person or action"
          value={filter} onChange={(e) => setFilter(e.target.value)} />
        <span className="meta">{shown.length} events</span>
      </div>
      {error && <p className="notice error">{error}</p>}
      <section className="card">
        <table className="plain">
          <thead>
            <tr>
              <th>When</th>
              <th>Who</th>
              <th>What</th>
              <th>Record</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((e, i) => (
              <tr key={i}>
                <td className="item-sub">{new Date(e.at).toLocaleString("en-IN")}</td>
                <td>{e.staff}</td>
                <td>{label(e.action)}</td>
                <td className="item-sub">{e.target_type ? `${e.target_type} #${e.target_id}` : "–"}</td>
                <td className="item-sub" style={{ maxWidth: 360, wordBreak: "break-word" }}>{e.detail ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
