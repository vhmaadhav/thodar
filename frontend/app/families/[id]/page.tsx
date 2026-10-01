"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, fmtDate, type Item, type Thread } from "@/lib/api";

function statusText(i: Item) {
  if (i.status === "done") return `Done ${fmtDate(i.completed_on)}`;
  if (i.status === "missed") return "Missed";
  if (i.status === "cancelled") return "No longer applies";
  if (i.status === "confirmed") return "Confirmed";
  if (i.rescheduled_to) return `Booked ${fmtDate(i.rescheduled_to)}`;
  const days = Math.floor((Date.now() - new Date(i.due + "T00:00:00").getTime()) / 86_400_000);
  if (days > 0) return `Overdue ${days} day${days > 1 ? "s" : ""}`;
  return days === 0 ? "Due today" : "Upcoming";
}

function statusClass(i: Item) {
  if (i.status !== "pending" || i.rescheduled_to) return i.status;
  return new Date(i.due + "T00:00:00").getTime() < Date.now() - 86_400_000 ? "overdue" : "pending";
}

function Knots({ items }: { items: Item[] }) {
  return (
    <>
      {items
        .filter((i) => i.status !== "cancelled")
        .map((i) => (
          <div key={i.id} className={`knot ${i.status}`}>
            <div className="item-label">{i.label}</div>
            <div className="item-sub">
              Due {fmtDate(i.due)} · <span className={`pill ${statusClass(i)}`}>{statusText(i)}</span>
            </div>
            {i.attempts.length > 0 && (
              <div className="item-sub">
                {i.attempts.length} contact{i.attempts.length > 1 ? "s" : ""} · last:{" "}
                {i.attempts[i.attempts.length - 1].outcome.replace("_", " ")} via{" "}
                {i.attempts[i.attempts.length - 1].channel}
                {i.attempts[i.attempts.length - 1].note ? ` · “${i.attempts[i.attempts.length - 1].note}”` : ""}
              </div>
            )}
          </div>
        ))}
    </>
  );
}

export default function FamilyThread() {
  const { id } = useParams<{ id: string }>();
  const [t, setT] = useState<Thread | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Thread>(`/mothers/${id}/thread`).then(setT).catch((e) => setError((e as Error).message));
  }, [id]);

  if (error) return <p className="notice error">{error}</p>;
  if (!t) return <p className="empty">Loading…</p>;

  return (
    <main>
      <p className="eyebrow">
        <Link href="/families">Families</Link> · One thread
      </p>
      <h1 className="page-title">{t.name}</h1>
      <p className="sub">
        {t.phone ? `+91 ${t.phone}` : "No phone"} · RCH ID {t.rch_id ?? "not on file"} · {t.village ?? "village unknown"} ·
        reminders in {t.language === "ta" ? "Tamil" : "English"}
      </p>

      {t.pregnancies.map((p) => {
        const anc = p.items.filter((i) => i.schedule === "anc");
        const pnc = p.items.filter((i) => i.schedule === "pnc");
        return (
          <section key={p.id} className="card pad" style={{ marginTop: 18 }}>
            <div className="cols">
              <div>
                <p className="eyebrow">Mother · obstetrics</p>
                <div className="thread">
                  <div className="knot">
                    <div className="item-sub">Last menstrual period {fmtDate(p.lmp) || "not recorded"}</div>
                  </div>
                  <Knots items={anc} />
                  {p.delivery_date && (
                    <div className="knot handover">
                      <div className="handover-label">Delivered {fmtDate(p.delivery_date)}</div>
                      <div className="item-sub">
                        Handover: the baby&apos;s schedule started here, next to the mother&apos;s postnatal plan.
                      </div>
                    </div>
                  )}
                  <Knots items={pnc} />
                </div>
              </div>
              <div>
                {p.babies.length === 0 && (
                  <p className="item-sub" style={{ marginTop: 28 }}>
                    The baby&apos;s thread starts at delivery: newborn checks and the immunisation schedule are created
                    automatically, owned by paediatrics.
                  </p>
                )}
                {p.babies.map((b) => (
                  <div key={b.id}>
                    <p className="eyebrow">Baby · paediatrics</p>
                    <div className="thread">
                      <div className="knot handover">
                        <div className="handover-label">{b.name ?? "Baby"}</div>
                        <div className="item-sub">
                          Born {fmtDate(b.dob)}
                          {b.sex ? ` · ${b.sex === "F" ? "girl" : "boy"}` : ""}
                        </div>
                      </div>
                      <Knots items={b.items} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        );
      })}
    </main>
  );
}
