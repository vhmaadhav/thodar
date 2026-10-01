"use client";

import { useEffect, useState } from "react";
import { api, type Metrics, pct } from "@/lib/api";

interface Step {
  code: string;
  label: string;
  schedule: string;
  due: number;
  done: number;
  done_on_time: number;
  missed: number;
  open: number;
}

const GROUP: Record<string, string> = {
  anc: "Pregnancy · antenatal care",
  pnc: "Birth to 6 weeks · postnatal care",
  uip: "First two years · immunisation",
};

const SEGMENTS = [
  { key: "on_time", label: "Done on time", color: "var(--ink-2)" },
  { key: "late", label: "Done late", color: "#8fa79f" },
  { key: "open", label: "Still open (being chased)", color: "var(--turmeric)" },
  { key: "missed", label: "Missed for good", color: "var(--madder)" },
] as const;

export default function InsightsPage() {
  const [steps, setSteps] = useState<Step[] | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api<Step[]>("/insights/funnel"), api<Metrics>("/metrics")])
      .then(([s, m]) => {
        setSteps(s);
        setMetrics(m);
      })
      .catch((e) => setError((e as Error).message));
  }, []);

  const groups = ["anc", "pnc", "uip"].map((g) => ({
    key: g,
    steps: (steps ?? []).filter((s) => s.schedule === g && s.due > 0),
  }));

  return (
    <main>
      <p className="eyebrow">Where families drop off</p>
      <h1 className="page-title">The journey, visit by visit</h1>
      <p className="sub">
        Of every visit that has fallen due at this clinic, how many happened, on time or late, how many are still being
        chased, and how many were missed for good. Counts only: no family is scored.
      </p>

      {error && <p className="notice error">{error}</p>}

      {metrics && (
        <section className="tiles">
          <div className="card tile">
            <div className="tile-num">{pct(metrics.on_time_rate)}</div>
            <div className="tile-label">Completed visits done on time</div>
          </div>
          <div className="card tile alert">
            <div className="tile-num">{pct(metrics.missed_rate)}</div>
            <div className="tile-label">Lost to follow-up (missed ÷ due and closed)</div>
          </div>
          <div className="card tile">
            <div className="tile-num">{metrics.median_days_overdue}</div>
            <div className="tile-label">Median days overdue, open visits</div>
          </div>
          <div className="card tile">
            <div className="tile-num">{pct(metrics.families_reached_rate)}</div>
            <div className="tile-label">Reminded families who replied</div>
          </div>
        </section>
      )}

      <div className="legend" style={{ display: "flex", gap: 16, flexWrap: "wrap", margin: "8px 0 14px" }}>
        {SEGMENTS.map((s) => (
          <span key={s.key} className="meta" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 12, height: 12, borderRadius: 3, background: s.color, display: "inline-block" }} />
            {s.label}
          </span>
        ))}
      </div>

      {groups.map((g) => (
        <section key={g.key} className="card pad" style={{ marginBottom: 14 }}>
          <p className="eyebrow" style={{ marginBottom: 10 }}>
            {GROUP[g.key]}
          </p>
          {g.steps.length === 0 && <p className="item-sub">No visits due yet.</p>}
          {g.steps.map((s) => {
            const late = s.done - s.done_on_time;
            const parts = { on_time: s.done_on_time, late, open: s.open, missed: s.missed };
            const reached = s.due ? s.done / s.due : 0;
            return (
              <div key={s.code} style={{ display: "grid", gridTemplateColumns: "230px 1fr 150px", gap: 14, alignItems: "center", padding: "6px 0" }}>
                <div>
                  <div className="item-label">{s.label}</div>
                  <div className="item-sub">{s.due} due so far</div>
                </div>
                <div
                  role="img"
                  aria-label={`${s.label}: ${s.done_on_time} on time, ${late} late, ${s.open} open, ${s.missed} missed of ${s.due}`}
                  style={{ display: "flex", height: 18, borderRadius: 6, overflow: "hidden", background: "var(--cotton-2)", gap: 2 }}
                >
                  {SEGMENTS.map((seg) => {
                    const n = parts[seg.key];
                    return n > 0 ? (
                      <div key={seg.key} title={`${seg.label}: ${n}`} style={{ width: `${(n / s.due) * 100}%`, background: seg.color }} />
                    ) : null;
                  })}
                </div>
                <div style={{ textAlign: "right" }}>
                  <span className="tile-num" style={{ fontSize: 20 }}>
                    {Math.round(reached * 100)}%
                  </span>{" "}
                  <span className="item-sub">attended</span>
                  {s.missed > 0 && <div className="item-sub" style={{ color: "var(--madder)" }}>{s.missed} missed</div>}
                </div>
              </div>
            );
          })}
        </section>
      ))}
    </main>
  );
}
