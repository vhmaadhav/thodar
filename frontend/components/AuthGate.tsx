"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { API, getToken, saveSession, type StaffMe } from "@/lib/api";

/** Shows the app only to signed-in staff. A village health nurse lands on her field list. */
export default function AuthGate({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const onLogin = path.startsWith("/login");

  useEffect(() => {
    if (onLogin) return;
    const token = getToken();
    fetch(`${API}/auth/me`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then(async (res) => {
        if (res.status === 401) {
          router.replace("/login");
          return;
        }
        const me = (await res.json()) as StaffMe;
        saveSession(token ?? "", me);
        if (me.role === "vhn" && path === "/") {
          router.replace("/field");
          return;
        }
        setReady(true);
      })
      .catch(() => setReady(true)); // API down: let pages show their own "can't reach the API" message
  }, [onLogin, path, router]);

  if (onLogin || ready) return <>{children}</>;
  return <p className="empty">Checking sign-in…</p>;
}
