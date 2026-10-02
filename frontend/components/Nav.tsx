"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSyncExternalStore } from "react";
import { getStaff, type Role, signOut } from "@/lib/api";

const LINKS: { href: string; label: string; roles: Role[] }[] = [
  { href: "/", label: "Worklist", roles: ["nurse", "doctor", "admin"] },
  { href: "/field", label: "Field visits", roles: ["vhn", "nurse", "doctor", "admin"] },
  { href: "/families", label: "Families", roles: ["vhn", "nurse", "doctor", "admin"] },
  { href: "/insights", label: "Insights", roles: ["nurse", "doctor", "admin"] },
  { href: "/review", label: "Review", roles: ["nurse", "doctor", "admin"] },
  { href: "/import", label: "Import", roles: ["nurse", "doctor", "admin"] },
  { href: "/audit", label: "Audit", roles: ["doctor", "admin"] },
  { href: "/ai", label: "AI & data", roles: ["vhn", "nurse", "doctor", "admin"] },
];

const ROLE_LABEL: Record<Role, string> = { nurse: "Nurse", doctor: "Doctor", vhn: "Village health nurse", admin: "Admin" };

function subscribe(cb: () => void) {
  window.addEventListener("storage", cb);
  return () => window.removeEventListener("storage", cb);
}

export default function Nav() {
  const path = usePathname();
  // Read the signed-in staff from localStorage without a hydration mismatch.
  const staffJson = useSyncExternalStore(subscribe, () => JSON.stringify(getStaff()), () => "null");
  const staff = JSON.parse(staffJson) as ReturnType<typeof getStaff>;
  if (path.startsWith("/login")) {
    return (
      <header className="topbar">
        <span className="brand">
          <span className="brand-name">Thodar</span>
          <span className="brand-tag">one thread for every mother and baby</span>
        </span>
      </header>
    );
  }
  const role = staff?.role ?? "admin";
  return (
    <header className="topbar">
      <Link href={role === "vhn" ? "/field" : "/"} className="brand">
        <span className="brand-name">Thodar</span>
        <span className="brand-tag">one thread for every mother and baby</span>
      </Link>
      <nav className="nav">
        {LINKS.filter((l) => l.roles.includes(role)).map((l) => {
          const active = l.href === "/" ? path === "/" : path.startsWith(l.href);
          return (
            <Link key={l.href} href={l.href} className={active ? "active" : ""}>
              {l.label}
            </Link>
          );
        })}
      </nav>
      {staff && staff.id !== null && (
        <div className="toolbar" style={{ margin: 0, gap: 8 }}>
          <span className="pill pending" title={staff.villages.length ? `Villages: ${staff.villages.join(", ")}` : ""}>
            {staff.name} · {ROLE_LABEL[staff.role]}
          </span>
          <button className="btn small" onClick={signOut}>
            Sign out
          </button>
        </div>
      )}
    </header>
  );
}
