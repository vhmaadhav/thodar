"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import Handovers from "@/components/Handovers";
import PhoneSimulator from "@/components/PhoneSimulator";
import {
  API,
  api,
  BUCKET_LABEL,
  type Bucket,
  fmtDate,
  type Metrics,
  pct,
  postJSON,
  type WorklistRow,
} from "@/lib/api";

type Owner = "all" | "obstetrics" | "paediatrics";

const FLAG_STEPS = ["Family asked a question", "Ask VHN to visit", "Find correct number", "Moved away"];

function bucketText(r: WorklistRow) {
  if (r.bucket === "overdue" || r.bucket === "unreachable") return `${r.days_overdue} days overdue`;
  if (r.bucket === "due_today") return "Due today";
  return `Due ${fmtDate(r.due)}`;
}

export default function WorklistPage() {
  const [rows, setRows] = useState<WorklistRow[] | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [owner, setOwner] = useState<Owner>("all");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [rescheduling, setRescheduling] = useState<number | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const q = owner === "all" ? "" : `?owner=${owner}`;
    Promise.all([api<WorklistRow[]>(`/worklist${q}`), api<Metrics>("/metrics")])
      .then(([w, m]) => {
        setRows(w);
        setMetrics(m);
        setError(null);
      })
      .catch((e) => setError(`Can't reach the Thodar API. Is the backend running? (${(e as Error).message})`));
  }, [owner, tick]);

  const refresh = () => setTick((t) => t + 1);

  // One card per family: a nurse calls a family once, about everything that is due.
  const families = useMemo(() => {
    const map = new Map<number, WorklistRow[]>();
    for (const r of rows ?? []) {
      const list = map.get(r.mother_id) ?? [];
      list.push(r);
      map.set(r.mother_id, list);
    }
    return [...map.values()];
  }, [rows]);

  async function act(itemId: number, action: string, on?: string) {
    setBusy(true);
    try {
      await postJSON(`/items/${itemId}/actions`, { action, on, actor: "nurse" });
      setRescheduling(null);
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function sendReminders() {
    setBusy(true);
    try {
      const r = await postJSON<{ sent: number; skipped_no_consent: number; dry_run: boolean }>("/reminders/run", {});
      setNotice(
        `${r.sent} WhatsApp reminder${r.sent === 1 ? "" : "s"} ${r.dry_run ? "queued (demo mode: shown on the phone)" : "sent"}` +
          (r.skipped_no_consent ? ` · ${r.skipped_no_consent} skipped, no consent on file` : ""),
      );
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <p className="eyebrow">Today · {metrics ? fmtDate(metrics.as_of) : ""}</p>
      <h1 className="page-title">Who needs follow-up</h1>
      <p className="sub">Sorted by days overdue, then by failed contact attempts. Nothing here is a clinical score.</p>

      {metrics && (
        <section className="tiles">
          <div className="card tile alert">
            <div className="tile-num">{metrics.overdue}</div>
            <div className="tile-label">Overdue visits</div>
          </div>
          <div className="card tile">
            <div className="tile-num">{metrics.due_today}</div>
            <div className="tile-label">Due today</div>
          </div>
          <div className="card tile">
            <div className="tile-num">{metrics.unreachable}</div>
            <div className="tile-label">Unreachable (2+ failed tries)</div>
          </div>
          <div className="card tile">
            <div className="tile-num">{pct(metrics.on_time_rate)}</div>
            <div className="tile-label">Completed visits done on time</div>
          </div>
          <div className="card tile">
            <div className="tile-num">{pct(metrics.missed_rate)}</div>
            <div className="tile-label">Missed for good ({metrics.missed} visits)</div>
          </div>
        </section>
      )}

      <div className="toolbar">
        <div className="seg" role="tablist" aria-label="Team">
          {(["all", "obstetrics", "paediatrics"] as Owner[]).map((o) => (
            <button key={o} className={owner === o ? "on" : ""} onClick={() => setOwner(o)}>
              {o === "all" ? "All teams" : o === "obstetrics" ? "Obstetrics" : "Paediatrics"}
            </button>
          ))}
        </div>
        <span className="meta">
          {families.length} families · {rows?.length ?? 0} visits
        </span>
        <span className="spacer" />
        <button className="btn primary" onClick={sendReminders} disabled={busy}>
          Send today&apos;s WhatsApp reminders
        </button>
      </div>

      {error && <p className="notice error">{error}</p>}
      {notice && <p className="notice">{notice}</p>}

      {owner !== "obstetrics" && <Handovers tick={tick} />}

      <div className="layout">
        <section className="card">
          {rows === null && !error && <p className="empty">Loading…</p>}
          {rows && families.length === 0 && <p className="empty">Nobody is due or overdue. A good day.</p>}
          {families.map((items) => {
            const first = items[0];
            return (
              <article key={first.mother_id} className="family">
                <div className="family-head">
                  <Link className="family-name" href={`/families/${first.mother_id}`}>
                    {first.who.startsWith("Baby of ") ? first.who.slice(8) : first.who}
                  </Link>
                  <span className="meta">
                    {first.phone ? `+91 ${first.phone}` : "no phone"} · {first.village ?? "village unknown"}
                  </span>
                </div>
                {items.map((r) => (
                  <div className="item" key={r.item_id}>
                    <div>
                      <span className={`pill ${r.bucket}`} title={BUCKET_LABEL[r.bucket as Bucket]}>
                        {bucketText(r)}
                      </span>
                    </div>
                    <div>
                      <div className="item-label">
                        {r.baby_id ? "Baby · " : ""}
                        {r.label}
                      </div>
                      <div className={`next-step ${FLAG_STEPS.some((f) => r.next_step.startsWith(f)) ? "flag" : ""}`}>
                        Next: {r.next_step}
                      </div>
                      {r.last_attempt && (
                        <div className="item-sub">
                          Last: {r.last_attempt.outcome.replace("_", " ")} via {r.last_attempt.channel}
                          {r.last_attempt.note ? ` · “${r.last_attempt.note}”` : ""}
                        </div>
                      )}
                    </div>
                    <div className="actions">
                      {rescheduling === r.item_id ? (
                        <form
                          onSubmit={(e) => {
                            e.preventDefault();
                            const v = new FormData(e.currentTarget).get("on") as string;
                            if (v) act(r.item_id, "reschedule", v);
                          }}
                          style={{ display: "flex", gap: 6 }}
                        >
                          <input type="date" name="on" required className="btn small" />
                          <button className="btn small primary" disabled={busy}>
                            Book
                          </button>
                          <button type="button" className="btn small" onClick={() => setRescheduling(null)}>
                            Cancel
                          </button>
                        </form>
                      ) : (
                        <>
                          {r.next_step === "Voice call" && (
                            <button
                              className="btn small"
                              title="Hear the Tamil reminder the voice call will speak (Bulbul v3)"
                              onClick={() => new Audio(`${API}/items/${r.item_id}/voice-preview`).play().catch(() => setError("Voice preview needs the Sarvam key on the server."))}
                            >
                              ▶ Hear call
                            </button>
                          )}
                          <button className="btn small" disabled={busy} onClick={() => act(r.item_id, "no_answer")}>
                            No answer
                          </button>
                          <button className="btn small" disabled={busy} onClick={() => act(r.item_id, "confirm")}>
                            Confirmed
                          </button>
                          <button className="btn small" disabled={busy} onClick={() => setRescheduling(r.item_id)}>
                            Reschedule
                          </button>
                          <button className="btn small" disabled={busy} onClick={() => act(r.item_id, "request_visit")}>
                            VHN visit
                          </button>
                          <button className="btn small primary" disabled={busy} onClick={() => act(r.item_id, "done")}>
                            Done
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </article>
            );
          })}
        </section>
        <PhoneSimulator onChange={refresh} tick={tick} />
      </div>
    </main>
  );
}
