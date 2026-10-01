"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type FamilySummary } from "@/lib/api";

const STAGE = { pregnant: "Pregnant", postnatal: "Postnatal (≤ 6 weeks)", infant: "Baby under 2" } as const;

export default function FamiliesPage() {
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<FamilySummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => {
      api<FamilySummary[]>(`/families${q ? `?q=${encodeURIComponent(q)}` : ""}`)
        .then((r) => {
          setRows(r);
          setError(null);
        })
        .catch((e) => setError((e as Error).message));
    }, 200);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <main>
      <p className="eyebrow">Every thread</p>
      <h1 className="page-title">Families</h1>
      <div className="toolbar">
        <input
          className="btn"
          style={{ minWidth: 280 }}
          placeholder="Search by name or phone"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <span className="meta">{rows?.length ?? 0} mothers</span>
      </div>
      {error && <p className="notice error">{error}</p>}
      <section className="card">
        <table className="plain">
          <thead>
            <tr>
              <th>Mother</th>
              <th>Phone</th>
              <th>Village</th>
              <th>Stage</th>
              <th>Open visits</th>
              <th>Missed</th>
            </tr>
          </thead>
          <tbody>
            {rows?.map((f) => (
              <tr key={f.mother_id}>
                <td>
                  <Link className="family-name" href={`/families/${f.mother_id}`}>
                    {f.name}
                  </Link>
                </td>
                <td>{f.phone ? `+91 ${f.phone}` : "–"}</td>
                <td>{f.village ?? "–"}</td>
                <td>{STAGE[f.stage as keyof typeof STAGE] ?? f.stage}</td>
                <td>{f.open_items}</td>
                <td>{f.missed ? <span className="pill overdue">{f.missed}</span> : "0"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
