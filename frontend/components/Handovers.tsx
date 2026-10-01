"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, fmtDate } from "@/lib/api";

interface Handover {
  baby_id: number;
  mother_id: number;
  name: string;
  dob: string;
  days_old: number;
  phone: string | null;
  items_created: number;
  done: number;
  next: { label: string; due: string } | null;
}

/** The obstetrics-to-paediatrics handover: babies born in the last two weeks and what paediatrics now owns. */
export default function Handovers({ tick }: { tick: number }) {
  const [rows, setRows] = useState<Handover[]>([]);

  useEffect(() => {
    api<Handover[]>("/handovers").then(setRows).catch(() => setRows([]));
  }, [tick]);

  if (rows.length === 0) return null;
  return (
    <section className="card pad" style={{ marginBottom: 14 }}>
      <p className="eyebrow">Handover · born in the last 14 days</p>
      <p className="sub" style={{ marginBottom: 10 }}>
        Each baby&apos;s newborn checks and vaccines were created from the delivery register, already owned by
        paediatrics. No one has to re-enter them.
      </p>
      <div style={{ display: "flex", gap: 10, overflowX: "auto", paddingBottom: 4 }}>
        {rows.map((h) => (
          <Link
            key={h.baby_id}
            href={`/families/${h.mother_id}`}
            className="card"
            style={{ minWidth: 220, padding: "10px 12px", textDecoration: "none", background: "var(--cotton)" }}
          >
            <div className="item-label">{h.name}</div>
            <div className="item-sub">
              Born {fmtDate(h.dob)} · {h.days_old} day{h.days_old === 1 ? "" : "s"} old
            </div>
            <div className="item-sub">
              {h.items_created} visits scheduled · {h.done} done
            </div>
            {h.next && (
              <div className="next-step" style={{ marginTop: 4 }}>
                Next: {h.next.label}, {fmtDate(h.next.due)}
              </div>
            )}
          </Link>
        ))}
      </div>
    </section>
  );
}
