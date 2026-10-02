"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, fmtDate, getStaff, postJSON } from "@/lib/api";

interface Visit {
  item_id: number;
  mother_id: number;
  mother: string;
  phone: string | null;
  family_phone: string | null;
  village: string;
  label: string;
  for_baby: boolean;
  due: string;
  days_overdue: number;
  requested_at: string;
  requested_by: string;
}

interface Outcome {
  item_id: number;
  action: "reschedule" | "confirm" | "no_answer" | "moved";
  on?: string;
  note: string;
  at: string;
}

const CACHE_KEY = "thodar.field.visits";
const QUEUE_KEY = "thodar.field.queue";

function load<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function save(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {}
}

function nextWednesday(): string {
  const d = new Date();
  d.setDate(d.getDate() + (((3 - d.getDay() + 7) % 7) || 7));
  return d.toISOString().slice(0, 10);
}

/** The village health nurse's home-visit list. Works with no signal: the list is cached on the phone
 * and outcomes queue up until the connection returns. */
export default function FieldPage() {
  const [visits, setVisits] = useState<Visit[]>(() => load<Visit[]>(CACHE_KEY, []));
  const [queue, setQueue] = useState<Outcome[]>(() => load<Outcome[]>(QUEUE_KEY, []));
  const [online, setOnline] = useState(true);
  const [status, setStatus] = useState<string | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [day, setDay] = useState(nextWednesday);
  const staff = typeof window === "undefined" ? null : getStaff();

  const sync = useCallback(async () => {
    const pending = load<Outcome[]>(QUEUE_KEY, []);
    let left = pending;
    for (const o of pending) {
      try {
        await postJSON(`/items/${o.item_id}/actions`, { action: o.action, on: o.on, note: o.note });
        left = left.filter((x) => x !== o);
      } catch (e) {
        if (!String((e as Error).message).startsWith("Failed")) left = left.filter((x) => x !== o); // rejected: drop
        else break; // still offline
      }
    }
    save(QUEUE_KEY, left);
    setQueue(left);
    try {
      const fresh = await api<Visit[]>("/field/visits");
      setVisits(fresh);
      save(CACHE_KEY, fresh);
      setOnline(true);
      if (pending.length && !left.length) setStatus(`${pending.length} visit outcome(s) synced`);
    } catch {
      setOnline(false);
    }
  }, []);

  useEffect(() => {
    const kick = () => {
      sync();
    };
    const t = setTimeout(kick, 0);
    window.addEventListener("online", kick);
    return () => {
      clearTimeout(t);
      window.removeEventListener("online", kick);
    };
  }, [sync]);

  /** One door, one outcome: applies to every visit this family has waiting. */
  function record(fam: Visit[], action: Outcome["action"], note: string, on?: string) {
    const at = new Date().toISOString();
    const q = [...load<Outcome[]>(QUEUE_KEY, []), ...fam.map((v) => ({ item_id: v.item_id, action, on, note, at }))];
    save(QUEUE_KEY, q);
    setQueue(q);
    const ids = new Set(fam.map((v) => v.item_id));
    const remaining = visits.filter((x) => !ids.has(x.item_id));
    setVisits(remaining);
    save(CACHE_KEY, remaining);
    setOpen(null);
    setStatus(`Saved: ${fam[0].mother} · ${note}`);
    sync();
  }

  // Village -> family -> that family's visits: one stop per family.
  const byVillage = useMemo(() => {
    const m = new Map<string, Map<number, Visit[]>>();
    for (const v of visits) {
      const fam = m.get(v.village) ?? new Map<number, Visit[]>();
      fam.set(v.mother_id, [...(fam.get(v.mother_id) ?? []), v]);
      m.set(v.village, fam);
    }
    return [...m.entries()].map(([village, fams]) => [village, [...fams.values()]] as const);
  }, [visits]);

  return (
    <main>
      <p className="eyebrow">Home visits{staff?.villages?.length ? ` · ${staff.villages.join(", ")}` : ""}</p>
      <h1 className="page-title">Families to visit</h1>
      <p className="sub">
        Families the clinic could not reach by phone. Record what happened at the door; the clinic&apos;s list updates.
      </p>
      <div className="toolbar">
        <span className={`pill ${online ? "done" : "overdue"}`}>{online ? "Online" : "Offline: saved on this phone"}</span>
        {queue.length > 0 && <span className="pill due_today">{queue.length} waiting to sync</span>}
        <span className="spacer" />
        <button className="btn small" onClick={sync}>
          Refresh
        </button>
      </div>
      {status && <p className="notice">{status}</p>}
      {visits.length === 0 && <p className="card empty">No home visits waiting. Thank you!</p>}

      {byVillage.map(([village, list]) => (
        <section key={village} className="card" style={{ marginBottom: 12 }}>
          <p className="eyebrow" style={{ padding: "12px 16px 0" }}>
            {village} · {list.length} famil{list.length === 1 ? "y" : "ies"}
          </p>
          {list.map((fam) => {
            const v = fam[0];
            return (
            <article key={v.mother_id} className="family">
              <div className="family-head">
                <span className="family-name">{v.mother}</span>
                <span className={`pill ${v.days_overdue ? "overdue" : "due_today"}`}>
                  {v.days_overdue ? `${Math.max(...fam.map((x) => x.days_overdue))} days overdue` : "Due"}
                </span>
              </div>
              {fam.map((x) => (
                <div key={x.item_id} className="item-sub">
                  {x.for_baby ? "Baby · " : "Mother · "}
                  {x.label} · due {fmtDate(x.due)}
                </div>
              ))}
              <div className="item-sub">Asked by {v.requested_by}</div>
              <div className="toolbar" style={{ margin: "8px 0 0" }}>
                {v.phone && (
                  <a className="btn small" href={`tel:+91${v.phone}`}>
                    Call mother
                  </a>
                )}
                {v.family_phone && (
                  <a className="btn small" href={`tel:+91${v.family_phone}`}>
                    Call family
                  </a>
                )}
                <button className="btn small primary" onClick={() => setOpen(open === v.mother_id ? null : v.mother_id)}>
                  Record visit
                </button>
              </div>
              {open === v.mother_id && (
                <div style={{ display: "grid", gap: 8, marginTop: 10 }}>
                  <div className="toolbar" style={{ margin: 0 }}>
                    <span className="item-sub">Met the family. They will come on</span>
                    <input type="date" className="btn small" value={day} onChange={(e) => setDay(e.target.value)} />
                    <button className="btn small primary"
                      onClick={() => record(fam, "reschedule", `met at home; will come ${day}`, day)}>
                      Save
                    </button>
                  </div>
                  <div className="toolbar" style={{ margin: 0 }}>
                    <button className="btn small" onClick={() => record(fam, "no_answer", "visited; nobody at home")}>
                      Nobody at home
                    </button>
                    <button className="btn small" onClick={() => record(fam, "moved", "visited; family has moved")}>
                      Family has moved
                    </button>
                  </div>
                  <p className="item-sub" style={{ margin: 0 }}>
                    If someone is unwell, follow your usual referral; Thodar only records the visit.
                  </p>
                </div>
              )}
            </article>
            );
          })}
        </section>
      ))}
    </main>
  );
}
