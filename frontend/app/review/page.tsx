"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Inbox from "@/components/Inbox";
import { api, postJSON, type Review } from "@/lib/api";

const SOURCE = {
  anc_register: "ANC register",
  delivery_register: "Delivery register",
  immunisation_register: "Immunisation register",
} as const;

export default function ReviewPage() {
  const [rows, setRows] = useState<Review[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    api<Review[]>("/reviews").then(setRows).catch((e) => setError((e as Error).message));
  }, [tick]);

  async function dismiss(id: number) {
    await postJSON(`/reviews/${id}/dismiss`, {});
    setTick((t) => t + 1);
  }

  return (
    <main>
      <p className="eyebrow">Record linking</p>
      <h1 className="page-title">Needs a person to decide</h1>
      <p className="sub">
        These register rows look like a mother we already know, but not certainly enough to merge. Thodar never merges
        on a guess.
      </p>
      {error && <p className="notice error">{error}</p>}
      <section className="card" style={{ marginTop: 18 }}>
        {rows?.length === 0 && <p className="empty">Nothing to review.</p>}
        {rows && rows.length > 0 && (
          <table className="plain">
            <thead>
              <tr>
                <th>From</th>
                <th>Row as written</th>
                <th>Might be</th>
                <th>Why</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>{SOURCE[r.source as keyof typeof SOURCE] ?? r.source}</td>
                  <td>
                    {Object.entries(r.row)
                      .filter(([, v]) => v)
                      .slice(0, 5)
                      .map(([k, v]) => (
                        <div key={k} className="item-sub">
                          <b>{k}:</b> {v}
                        </div>
                      ))}
                  </td>
                  <td>
                    <Link className="family-name" href={`/families/${r.candidate_mother_id}`}>
                      {r.candidate_name}
                    </Link>
                    <div className="item-sub">match score {Math.round(r.score * 100)}%</div>
                  </td>
                  <td className="item-sub">{r.reason}</td>
                  <td>
                    <button className="btn small" onClick={() => dismiss(r.id)}>
                      Not the same person
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      <Inbox />
    </main>
  );
}
