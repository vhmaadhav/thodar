"use client";

import { useState } from "react";
import { API } from "@/lib/api";

const SOURCES = [
  { key: "anc", title: "ANC register", cols: "RCH ID, Name, Mobile, Village, LMP, ANC1–ANC4" },
  { key: "delivery", title: "Delivery register", cols: "Date, Mother name, Ph no, RCH no, Baby sex, Village, PNC dates" },
  { key: "immunisation", title: "Immunisation register", cols: "Child name, DOB, Mother mobile, Birth, 6 wk … 16 mo" },
];

interface Report {
  source: string;
  rows: number;
  created: number;
  linked: number;
  sent_to_review: number;
  skipped: string[];
}

export default function ImportPage() {
  const [reports, setReports] = useState<Record<string, Report | string>>({});

  async function upload(source: string, file: File) {
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await fetch(`${API}/import/${source}`, { method: "POST", body: fd });
      const body = await res.json();
      setReports((r) => ({ ...r, [source]: res.ok ? body : JSON.stringify(body) }));
    } catch (e) {
      setReports((r) => ({ ...r, [source]: (e as Error).message }));
    }
  }

  return (
    <main>
      <p className="eyebrow">No new data entry</p>
      <h1 className="page-title">Import the registers you already keep</h1>
      <p className="sub">
        CSV or Excel, column names as clinics write them. Import in order: ANC, then delivery, then immunisation.
      </p>
      <div className="tiles">
        {SOURCES.map((s) => {
          const rep = reports[s.key];
          return (
            <section key={s.key} className="card pad">
              <h3 style={{ fontSize: 18 }}>{s.title}</h3>
              <p className="item-sub">{s.cols}</p>
              <input
                type="file"
                accept=".csv,.xlsx,.xls"
                onChange={(e) => e.target.files?.[0] && upload(s.key, e.target.files[0])}
                style={{ marginTop: 10 }}
              />
              {typeof rep === "string" && <p className="notice error">{rep}</p>}
              {rep && typeof rep === "object" && (
                <p className="notice" style={{ marginTop: 10 }}>
                  {rep.rows} rows · {rep.created} new · {rep.linked} linked · {rep.sent_to_review} to review
                  {rep.skipped.length ? ` · ${rep.skipped.length} skipped` : ""}
                </p>
              )}
            </section>
          );
        })}
      </div>
      <p className="item-sub">
        Paper registers: photograph the page and Sarvam Vision turns it into rows for a nurse to check (coming in the
        build sprint).
      </p>
    </main>
  );
}
