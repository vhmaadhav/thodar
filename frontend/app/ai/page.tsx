"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface Job {
  job: string;
  provider: string;
  processes_in: string;
  active: boolean;
  without_it: string;
  why: string;
}

export default function AIPage() {
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Job[]>("/ai").then(setJobs).catch((e) => setError((e as Error).message));
  }, []);

  return (
    <main>
      <p className="eyebrow">Transparency</p>
      <h1 className="page-title">AI &amp; data</h1>
      <p className="sub">
        AI only reads paper and talks to families. Everything that decides who is due, overdue or missed is a fixed rule.
        Each job uses the provider that works best for Tamil clinic data, tested on our own samples, and works without it.
      </p>
      {error && <p className="notice error">{error}</p>}
      <section className="card" style={{ marginTop: 18 }}>
        <table className="plain">
          <thead>
            <tr>
              <th>Job</th>
              <th>Provider</th>
              <th>Data processed in</th>
              <th>Status</th>
              <th>If it is off</th>
              <th>Why this choice</th>
            </tr>
          </thead>
          <tbody>
            {jobs?.map((j) => (
              <tr key={j.job}>
                <td className="item-label">{j.job}</td>
                <td>{j.provider}</td>
                <td>
                  <span className={`pill ${j.processes_in.startsWith("Outside") ? "overdue" : "done"}`}>{j.processes_in}</span>
                </td>
                <td>{j.active ? <span className="pill done">On</span> : <span className="pill pending">Off (no key)</span>}</td>
                <td className="item-sub">{j.without_it}</td>
                <td className="item-sub">{j.why}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
