export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Bucket = "unreachable" | "overdue" | "due_today" | "due_soon";

export interface Attempt {
  channel: string;
  outcome: string;
  note: string | null;
  actor: string;
  at: string;
}

export interface WorklistRow {
  item_id: number;
  mother_id: number;
  baby_id: number | null;
  who: string;
  phone: string | null;
  village: string | null;
  label: string;
  schedule: string;
  owner: string;
  bucket: Bucket;
  due: string;
  days_overdue: number;
  failed_attempts: number;
  last_attempt: Attempt | null;
  next_step: string;
  benefit: string | null;
}

export interface Item {
  id: number;
  code: string;
  label: string;
  schedule: string;
  subject: string;
  owner: string;
  due: string;
  window_end: string;
  actionable_until: string;
  status: string;
  rescheduled_to: string | null;
  completed_on: string | null;
  attempts: Attempt[];
}

export interface Thread {
  mother_id: number;
  name: string;
  phone: string | null;
  rch_id: string | null;
  village: string | null;
  language: string;
  consent_at: string | null;
  opted_out: boolean;
  family_phone: string | null;
  family_relation: string | null;
  pregnancies: {
    id: number;
    lmp: string | null;
    delivery_date: string | null;
    items: Item[];
    babies: { id: number; name: string | null; dob: string; sex: string | null; items: Item[] }[];
  }[];
}

export interface Metrics {
  as_of: string;
  open_items: number;
  overdue: number;
  unreachable: number;
  due_today: number;
  median_days_overdue: number;
  missed: number;
  missed_rate: number | null;
  on_time_rate: number | null;
  families_reached_rate: number | null;
  brought_back_visits: number;
  brought_back_families: number;
}

export interface Review {
  id: number;
  source: string;
  row: Record<string, string | null>;
  candidate_mother_id: number;
  candidate_name: string;
  score: number;
  reason: string;
}

export interface FamilySummary {
  mother_id: number;
  name: string;
  phone: string | null;
  village: string | null;
  stage: string;
  open_items: number;
  missed: number;
}

// ---- Sign-in -------------------------------------------------------------------------------------

export type Role = "nurse" | "doctor" | "vhn" | "admin";

export interface StaffMe {
  id: number | null;
  name: string;
  role: Role;
  villages: string[];
}

const TOKEN_KEY = "thodar.token";
const STAFF_KEY = "thodar.staff";

function store(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function getToken(): string | null {
  return store()?.getItem(TOKEN_KEY) ?? null;
}

export function getStaff(): StaffMe | null {
  const raw = store()?.getItem(STAFF_KEY);
  try {
    return raw ? (JSON.parse(raw) as StaffMe) : null;
  } catch {
    return null;
  }
}

export function saveSession(token: string, staff: StaffMe) {
  store()?.setItem(TOKEN_KEY, token);
  store()?.setItem(STAFF_KEY, JSON.stringify(staff));
}

export function signOut() {
  store()?.removeItem(TOKEN_KEY);
  store()?.removeItem(STAFF_KEY);
  // A full reload on purpose: it drops every in-memory copy of family data from the signed-out session.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.href = "/login";
}

/** fetch with the staff token; a 401 sends the user to the sign-in page. */
export async function authFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${API}${path}`, { cache: "no-store", ...init, headers });
  if (res.status === 401 && typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
    signOut();
  }
  return res;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await authFetch(path, init);
  if (!res.ok) {
    const body = await res.text();
    let detail = body;
    try {
      detail = JSON.parse(body).detail ?? body;
    } catch {}
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export function patchJSON<T>(path: string, body: unknown): Promise<T> {
  return api<T>(path, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

export function postJSON<T>(path: string, body: unknown): Promise<T> {
  return api<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso + (iso.length === 10 ? "T00:00:00" : ""));
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export function pct(x: number | null | undefined): string {
  return x == null ? "–" : `${Math.round(x * 100)}%`;
}

export const BUCKET_LABEL: Record<Bucket, string> = {
  unreachable: "Unreachable",
  overdue: "Overdue",
  due_today: "Due today",
  due_soon: "Due soon",
};
