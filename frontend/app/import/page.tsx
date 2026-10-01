"use client";

import { useState } from "react";
import { API, postJSON } from "@/lib/api";

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

type Row = Record<string, string | null>;

function ReportLine({ rep }: { rep: Report }) {
  return (
    <p className="notice" style={{ marginTop: 10 }}>
      {rep.rows} rows · {rep.created} new · {rep.linked} linked · {rep.sent_to_review} to review
      {rep.skipped.length ? ` · ${rep.skipped.length} skipped` : ""}
    </p>
  );
}

export default function ImportPage() {
  const [reports, setReports] = useState<Record<string, Report | string>>({});
  const [drafts, setDrafts] = useState<Record<string, Row[]>>({});
  // Cells the server flagged as suspicious, keyed "row:col". Editing a cell clears its flag.
  const [flags, setFlags] = useState<Record<string, Record<string, string>>>({});
  const [reading, setReading] = useState<string | null>(null);

  async function upload(source: string, file: File) {
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await fetch(`${API}/import/${source}`, { method: "POST", body: fd });
      const body = await res.json();
      setReports((r) => ({ ...r, [source]: res.ok ? body : body.detail ?? JSON.stringify(body) }));
    } catch (e) {
      setReports((r) => ({ ...r, [source]: (e as Error).message }));
    }
  }

  async function readPhoto(source: string, file: File) {
    const fd = new FormData();
    fd.append("file", file);
    setReading(source);
    try {
      const res = await fetch(`${API}/import/${source}/photo`, { method: "POST", body: fd });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail ?? JSON.stringify(body));
      setDrafts((d) => ({ ...d, [source]: body.rows }));
      const f: Record<string, string> = {};
      for (const [row, cols] of Object.entries(body.issues ?? {}) as [string, Record<string, string>][]) {
        for (const [col, why] of Object.entries(cols)) f[`${row}:${col}`] = why;
      }
      setFlags((x) => ({ ...x, [source]: f }));
      setReports((r) => ({ ...r, [source]: "" }));
    } catch (e) {
      setReports((r) => ({ ...r, [source]: (e as Error).message }));
    } finally {
      setReading(null);
    }
  }

  async function saveDraft(source: string) {
    try {
      const rep = await postJSON<Report>(`/import/${source}/rows`, drafts[source]);
      setReports((r) => ({ ...r, [source]: rep }));
      setDrafts((d) => ({ ...d, [source]: [] }));
    } catch (e) {
      setReports((r) => ({ ...r, [source]: (e as Error).message }));
    }
  }

  function editCell(source: string, i: number, col: string, value: string) {
    setFlags((x) => {
      const f = { ...(x[source] ?? {}) };
      delete f[`${i}:${col}`];
      return { ...x, [source]: f };
    });
    setDrafts((d) => {
      const rows = [...(d[source] ?? [])];
      rows[i] = { ...rows[i], [col]: value || null };
      return { ...d, [source]: rows };
    });
  }

  return (
    <main>
      <p className="eyebrow">No new data entry</p>
      <h1 className="page-title">Import the registers you already keep</h1>
      <p className="sub">
        CSV or Excel with the column names clinics already use, or a photo of a paper page. Import in order: ANC, then
        delivery, then immunisation.
      </p>
      <div className="tiles">
        {SOURCES.map((s) => {
          const rep = reports[s.key];
          return (
            <section key={s.key} className="card pad">
              <h3 style={{ fontSize: 18 }}>{s.title}</h3>
              <p className="item-sub">{s.cols}</p>
              <label className="item-sub" style={{ display: "block", marginTop: 10 }}>
                Spreadsheet (CSV / Excel)
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  onChange={(e) => e.target.files?.[0] && upload(s.key, e.target.files[0])}
                  style={{ display: "block", marginTop: 4 }}
                />
              </label>
              <label className="item-sub" style={{ display: "block", marginTop: 10 }}>
                Photo of a paper page (read by Sarvam Vision)
                <input
                  type="file"
                  accept="image/png,image/jpeg,application/pdf"
                  onChange={(e) => e.target.files?.[0] && readPhoto(s.key, e.target.files[0])}
                  style={{ display: "block", marginTop: 4 }}
                />
              </label>
              {reading === s.key && <p className="notice">Reading the page…</p>}
              {typeof rep === "string" && rep && <p className="notice error">{rep}</p>}
              {rep && typeof rep === "object" && <ReportLine rep={rep} />}
            </section>
          );
        })}
      </div>

      {SOURCES.filter((s) => drafts[s.key]?.length).map((s) => {
        const rows = drafts[s.key];
        const cols = Object.keys(rows[0]);
        return (
          <section key={s.key} className="card pad" style={{ marginTop: 14 }}>
            <p className="eyebrow">Draft from photo · {s.title}</p>
            <p className="sub">Check every cell against the paper page and correct anything misread. Nothing is saved yet.</p>
            {Object.keys(flags[s.key] ?? {}).length > 0 && (
              <p className="notice error" style={{ marginTop: 8 }}>
                {Object.keys(flags[s.key]).length} cell{Object.keys(flags[s.key]).length > 1 ? "s" : ""} look wrong (red
                border). Hover for the reason, compare with the paper and correct.
              </p>
            )}
            <div style={{ overflowX: "auto", marginTop: 10 }}>
              <table className="plain">
                <thead>
                  <tr>
                    {cols.map((c) => (
                      <th key={c}>{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={i}>
                      {cols.map((c) => (
                        <td key={c}>
                          <input
                            className="btn small"
                            title={flags[s.key]?.[`${i}:${c}`]}
                            aria-invalid={Boolean(flags[s.key]?.[`${i}:${c}`])}
                            style={{
                              width: "100%",
                              minWidth: 90,
                              ...(flags[s.key]?.[`${i}:${c}`]
                                ? { borderColor: "var(--madder)", borderWidth: 2, background: "var(--madder-soft)" }
                                : {}),
                            }}
                            value={r[c] ?? ""}
                            onChange={(e) => editCell(s.key, i, c, e.target.value)}
                          />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="toolbar" style={{ marginTop: 12 }}>
              <button className="btn primary" onClick={() => saveDraft(s.key)}>
                I have checked these {rows.length} rows: import
              </button>
              <button className="btn" onClick={() => setDrafts((d) => ({ ...d, [s.key]: [] }))}>
                Discard
              </button>
            </div>
          </section>
        );
      })}
    </main>
  );
}
