"use client";

import { useEffect, useState } from "react";
import { API, saveSession, type StaffMe } from "@/lib/api";

interface DemoAccount {
  name: string;
  phone: string;
  pin: string;
  role: string;
}

export default function LoginPage() {
  const [phone, setPhone] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [demo, setDemo] = useState<DemoAccount[]>([]);

  useEffect(() => {
    fetch(`${API}/auth/demo-accounts`)
      .then((r) => r.json())
      .then(setDemo)
      .catch(() => setDemo([]));
  }, []);

  async function signIn(p: string, code: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: p, pin: code }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail ?? "Sign-in failed");
      saveSession(body.token, body.staff as StaffMe);
      window.location.href = body.staff.role === "vhn" ? "/field" : "/";
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main style={{ maxWidth: 440, margin: "24px auto" }}>
      <p className="eyebrow">Care team</p>
      <h1 className="page-title">Sign in</h1>
      <form
        className="card pad"
        style={{ display: "grid", gap: 10, marginTop: 14 }}
        onSubmit={(e) => {
          e.preventDefault();
          signIn(phone, pin);
        }}
      >
        <label className="item-sub">
          Mobile number
          <input className="btn" style={{ width: "100%", marginTop: 4 }} inputMode="tel" autoComplete="username"
            value={phone} onChange={(e) => setPhone(e.target.value)} required />
        </label>
        <label className="item-sub">
          PIN
          <input className="btn" style={{ width: "100%", marginTop: 4 }} type="password" inputMode="numeric"
            autoComplete="current-password" value={pin} onChange={(e) => setPin(e.target.value)} required />
        </label>
        <button className="btn primary" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
        {error && <p className="notice error" style={{ margin: 0 }}>{error}</p>}
      </form>

      {demo.length > 0 && (
        <section className="card pad" style={{ marginTop: 14 }}>
          <p className="eyebrow">Demo accounts · synthetic data</p>
          <p className="item-sub">Each role sees and can do different things. Tap one to sign in.</p>
          <div style={{ display: "grid", gap: 8, marginTop: 10 }}>
            {demo.map((a) => (
              <button key={a.phone} className="btn" style={{ textAlign: "left" }} disabled={busy}
                onClick={() => signIn(a.phone, a.pin)}>
                <b>{a.name}</b>
                <span className="item-sub"> · {a.phone} · PIN {a.pin}</span>
              </button>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
