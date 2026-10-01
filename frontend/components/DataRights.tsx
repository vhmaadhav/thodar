"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { API, postJSON } from "@/lib/api";

/** DPDP Act: a family can see everything held about them, and ask for it to be erased. */
export default function DataRights({ motherId, name }: { motherId: number; name: string }) {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [typed, setTyped] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function exportData() {
    const res = await fetch(`${API}/mothers/${motherId}/export`);
    const blob = new Blob([JSON.stringify(await res.json(), null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `thodar-${name.replace(/\W+/g, "-").toLowerCase()}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function erase() {
    try {
      await postJSON(`/mothers/${motherId}/erase`, { confirm_name: typed, requested_by: "staff" });
      router.push("/families");
    } catch (e) {
      setError((e as Error).message.replace(/^\d+: /, ""));
    }
  }

  return (
    <section className="card pad" style={{ marginTop: 14 }}>
      <p className="eyebrow">The family&apos;s data</p>
      <div className="toolbar" style={{ margin: "8px 0 0" }}>
        <button className="btn small" onClick={exportData}>
          Export everything we hold (JSON)
        </button>
        {!confirming ? (
          <button className="btn small" onClick={() => setConfirming(true)}>
            Erase on request…
          </button>
        ) : (
          <>
            <input
              className="btn small"
              placeholder={`type “${name}” to confirm`}
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              style={{ width: 220 }}
            />
            <button className="btn small accent" disabled={!typed} onClick={erase}>
              Erase permanently
            </button>
            <button className="btn small" onClick={() => setConfirming(false)}>
              Cancel
            </button>
          </>
        )}
        {error && <span className="pill overdue">{error}</span>}
      </div>
      <p className="item-sub" style={{ marginTop: 8 }}>
        Under the DPDP Act a family may ask what is held about them and ask for it to be erased. Erasure removes the
        mother, babies, visits, contact history and messages; only a count is kept as proof.
      </p>
    </section>
  );
}
