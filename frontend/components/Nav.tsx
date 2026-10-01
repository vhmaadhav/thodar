"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Worklist" },
  { href: "/families", label: "Families" },
  { href: "/insights", label: "Insights" },
  { href: "/review", label: "Review" },
  { href: "/import", label: "Import" },
  { href: "/ai", label: "AI & data" },
];

export default function Nav() {
  const path = usePathname();
  return (
    <header className="topbar">
      <Link href="/" className="brand">
        <span className="brand-name">Thodar</span>
        <span className="brand-tag">one thread for every mother and baby</span>
      </Link>
      <nav className="nav">
        {LINKS.map((l) => {
          const active = l.href === "/" ? path === "/" : path.startsWith(l.href);
          return (
            <Link key={l.href} href={l.href} className={active ? "active" : ""}>
              {l.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
