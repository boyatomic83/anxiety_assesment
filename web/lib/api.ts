/** Typed client for the Calma API (SPEC.md section 7). */

/** Base URL of the API. Accepts it with or without the /api/v1 prefix and trailing slashes. */
export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "").replace(/\/api\/v1$/, "");
const API_PREFIX = "/api/v1";

// ---------- types ----------
export type HealthResponse = { status: "ok"; version: string; environment: string; database: string };
export type Option = { value: number; label: string };
export type Item = { id: string; text: string; options: Option[] | null };
export type Questionnaire = {
  id: string;
  name: string;
  version: string;
  timeframe: string;
  options: Option[] | null;
  items: Item[];
  language: string;
};
export type Context = {
  age_band?: string;
  gender?: string;
  language?: "en" | "hi";
  country?: string;
  sleep_hours?: number;
  symptom_duration?: string;
  caffeine_cups?: number;
  stressful_event?: boolean;
  free_text?: string;
};
export type SessionCreated = { id: string; guest_token: string | null; consent_version: string; expires_at: string | null };
export type BandScore = { score: number; band: string; level: number };
export type Score = {
  questionnaire_id: string;
  questionnaire_version: string;
  total: number;
  band: string | null;
  level: number | null;
  subscales: Record<string, BandScore>;
};
export type Helpline = { name: string; number?: string | null; alt_number?: string | null; url?: string | null };
export type Helplines = { country: string; helplines: Helpline[] };
export type TopFactor = { feature: string; label: string; impact: number };
export type MLEstimate = {
  label: "AI-assisted estimate";
  composite_severity: number;
  composite_label: "minimal" | "mild" | "moderate" | "severe";
  probabilities: Record<string, number>;
  confidence: number;
  top_factors: TopFactor[];
  model_version: string;
  agrees_with_validated: boolean | null;
};
export type Result = {
  id: string;
  session_id: string;
  created_at: string;
  flagged: boolean;
  crisis: Helplines | null;
  primary: "validated";
  scores: Record<string, Score>;
  ml: MLEstimate | null;
  response_quality: { ok: boolean; flags: string[] } | null;
  disclaimer: string;
};
export type User = { id: string; email: string; role: "user" | "clinician" | "admin"; locale: string; reminder_days: number | null };
export type HistoryItem = { result_id: string; created_at: string; flagged: boolean; scores: Record<string, Score> };
export type PatientResult = {
  result_id: string;
  patient_ref: string;
  created_at: string;
  flagged: boolean;
  scores: Record<string, Score>;
  ml_composite: string | null;
};
export type AuditEntry = { id: string; actor_id: string | null; action: string; target: string | null; created_at: string };

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// ---------- auth token (memory only; refresh token is an httpOnly cookie) ----------
let accessToken: string | null = null;
export const setAccessToken = (t: string | null) => {
  accessToken = t;
};
export const getAccessToken = () => accessToken;

// ---------- guest session tokens (sessionStorage; guest data is deleted after 24h) ----------
const GUEST_KEY = "calma.guest";
type GuestStore = { sessions: Record<string, string>; results: Record<string, string> };
function readGuest(): GuestStore {
  try {
    return JSON.parse(sessionStorage.getItem(GUEST_KEY) ?? "") as GuestStore;
  } catch {
    return { sessions: {}, results: {} };
  }
}
export const guestStore = {
  rememberSession(sessionId: string, token: string) {
    const g = readGuest();
    g.sessions[sessionId] = token;
    sessionStorage.setItem(GUEST_KEY, JSON.stringify(g));
  },
  rememberResult(resultId: string, sessionId: string) {
    const g = readGuest();
    if (g.sessions[sessionId]) g.results[resultId] = g.sessions[sessionId];
    sessionStorage.setItem(GUEST_KEY, JSON.stringify(g));
  },
  sessionToken: (id: string) => readGuest().sessions[id] ?? null,
  resultToken: (id: string) => readGuest().results[id] ?? null,
  latestSession(): { id: string; token: string } | null {
    const entries = Object.entries(readGuest().sessions);
    const last = entries.at(-1);
    return last ? { id: last[0], token: last[1] } : null;
  },
  clear: () => sessionStorage.removeItem(GUEST_KEY),
};

type Opts = RequestInit & { guestToken?: string | null; raw?: boolean; retried?: boolean };

async function request<T>(path: string, opts: Opts = {}): Promise<T> {
  const { guestToken, raw, retried, ...init } = opts;
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
  if (init.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  if (guestToken) headers["X-Session-Token"] = guestToken;
  const res = await fetch(`${API_URL}${API_PREFIX}${path}`, { ...init, headers, credentials: "include" });
  if (res.status === 401 && accessToken && !retried && !path.startsWith("/auth/")) {
    if (await refreshSession()) return request<T>(path, { ...opts, retried: true });
  }
  if (!res.ok) {
    let message = `API ${res.status} on ${path}`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, message);
  }
  if (raw) return res as unknown as T;
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const json = (body: unknown) => JSON.stringify(body);

export async function refreshSession(): Promise<User | null> {
  try {
    const out = await request<{ access_token: string; user: User }>("/auth/refresh", { method: "POST" });
    setAccessToken(out.access_token);
    return out.user;
  } catch {
    setAccessToken(null);
    return null;
  }
}

export const CONSENT_VERSION = "2026-11-v1";

export const api = {
  health: () => request<HealthResponse>("/health"),
  questionnaire: (id: string, lang = "en") => request<Questionnaire>(`/questionnaires/${id}?lang=${lang}`),
  helplines: (country?: string) => request<Helplines>(`/helplines${country ? `?country=${country}` : ""}`),

  createSession: (locale: string, context?: Context) =>
    request<SessionCreated>("/sessions", {
      method: "POST",
      body: json({ consent: true, consent_version: CONSENT_VERSION, locale, context }),
    }),
  updateContext: (sessionId: string, context: Context) =>
    request<void>(`/sessions/${sessionId}/context`, {
      method: "PUT",
      body: json(context),
      guestToken: guestStore.sessionToken(sessionId),
    }),
  saveAnswers: (sessionId: string, questionnaireId: string, answers: Record<string, number>, timings: Record<string, number>) =>
    request<{ saved_items: number; complete: boolean }>(`/sessions/${sessionId}/answers`, {
      method: "POST",
      body: json({ questionnaire_id: questionnaireId, answers, item_timings: timings }),
      guestToken: guestStore.sessionToken(sessionId),
    }),
  submit: (sessionId: string) =>
    request<Result>(`/sessions/${sessionId}/submit`, { method: "POST", guestToken: guestStore.sessionToken(sessionId) }),

  result: (id: string) => request<Result>(`/results/${id}`, { guestToken: guestStore.resultToken(id) }),
  resultPdf: (id: string) => request<Response>(`/results/${id}/pdf`, { guestToken: guestStore.resultToken(id), raw: true }),
  share: (id: string) => request<{ code: string; expires_at: string }>(`/results/${id}/share`, { method: "POST" }),

  register: (email: string, password: string, locale: string) =>
    request<{ access_token: string; user: User }>("/auth/register", { method: "POST", body: json({ email, password, locale }) }),
  login: (email: string, password: string) =>
    request<{ access_token: string; user: User }>("/auth/login", { method: "POST", body: json({ email, password }) }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),

  me: () => request<User>("/me"),
  updateMe: (body: { locale?: string; reminder_days?: number; clear_reminder?: boolean }) =>
    request<User>("/me", { method: "PATCH", body: json(body) }),
  history: () => request<HistoryItem[]>("/me/history"),
  claim: (sessionId: string, guestToken: string) =>
    request<void>("/me/sessions/claim", { method: "POST", body: json({ session_id: sessionId, guest_token: guestToken }) }),
  exportData: () => request<unknown>("/me/export"),
  deleteMe: () => request<void>("/me", { method: "DELETE" }),

  redeem: (code: string) => request<PatientResult>("/clinician/shares/redeem", { method: "POST", body: json({ code }) }),
  patients: () => request<PatientResult[]>("/clinician/patients"),
  flagged: () => request<PatientResult[]>("/clinician/flagged"),
  clinicianResult: (id: string) => request<Result>(`/clinician/results/${id}`),
  clinicianCsv: () => request<Response>("/clinician/export.csv", { raw: true }),

  audit: () => request<AuditEntry[]>("/admin/audit"),
  models: () => request<{ active: Record<string, unknown> | null }>("/admin/models"),
  setRole: (email: string, role: User["role"]) =>
    request<User>("/admin/users/role", { method: "POST", body: json({ email, role }) }),
};

/** Save a fetched file (PDF/CSV) to disk. */
export async function downloadResponse(res: Response, fallbackName: string) {
  const blob = await res.blob();
  const name = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "")?.[1] ?? fallbackName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
