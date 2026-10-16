// src/lib/api.ts
// Typed API client — every label/number in the UI comes from here.
// No hard-coded architecture text anywhere in components.

const BASE = '/api/v1';

export type Role = 'admin' | 'doctor' | 'auditor';

export interface User {
  username: string;
  role: Role;
}

export interface TeamMember {
  name: string;
  roll: string;
  module: string;
}

export interface SystemInfo {
  project: string;
  course: string;
  institute: string;
  team: TeamMember[];
  backend: {
    framework: string;
    python: string;
    storage: string;
    storage_type: string;
    auth: string;
    audit: string;
    alerts: string[];
  };
  model: {
    name: string;
    file: string;
    loaded: boolean;
    ml_backend: string;
    window_size: number;
    features: string[];
    thresholds_ms: { low_medium: number; medium_high: number; veto: number };
  };
  decision_engine: {
    type: string;
    emergency_threshold: number;
    veto_threshold_ms: number;
    consistency_ratio: string;
    weights: { latency: number; cost: number; criticality: number };
  };
  aws_migration_map: Record<string, string>;
  runtime_stats: { total_decisions: number; edge: number; cloud: number };
}

export interface MetricsSummary {
  generated_at: string;
  source_filter: string;
  total_decisions: number;
  edge:  { count: number; pct: number };
  cloud: { count: number; pct: number };
  reasons: {
    ahp_decision: number;
    emergency_override: number;
    network_degradation_veto: number;
    uncategorised: number;
  };
  alerts: { emergency_overrides: number; delivered: number; failed: number };
}

export interface Decision {
  device_id: string;
  stored_at: string;
  routing_decision: 'EDGE' | 'CLOUD';
  reason: string;
  patient_criticality_score: number;
  predicted_latency_ms: number;
}

export interface DecisionsResponse {
  total: number;
  limit: number;
  offset: number;
  items: Decision[];
}

// ── Auth ────────────────────────────────────────────────────────────────────
// We piggyback on the existing /api/v1 prefix.
// Token stored in memory only (refresh via httpOnly cookie in production).
let _token: string | null = localStorage.getItem('portal_token');
let _user:  User  | null  = (() => {
  try { return JSON.parse(localStorage.getItem('portal_user') || 'null'); }
  catch { return null; }
})();

export function getToken() { return _token; }
export function getUser()  { return _user;  }

export function setSession(token: string, user: User) {
  _token = token;
  _user  = user;
  localStorage.setItem('portal_token', token);
  localStorage.setItem('portal_user',  JSON.stringify(user));
}

export function clearSession() {
  _token = null; _user = null;
  localStorage.removeItem('portal_token');
  localStorage.removeItem('portal_user');
}

// ── Fetch wrapper ───────────────────────────────────────────────────────────
async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init?.headers as Record<string, string>),
  };
  if (_token) headers['Authorization'] = `Bearer ${_token}`;

  const res = await fetch(path, { ...init, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// ── Public API ──────────────────────────────────────────────────────────────
export const api = {
  health: () => apiFetch<{ status: string }>('/health'),

  systemInfo: () => apiFetch<SystemInfo>(`${BASE}/system/info`),

  metricsSummary: (source = 'live') =>
    apiFetch<MetricsSummary>(`${BASE}/metrics/summary?source=${source}`),

  timeseries: (limit = 100) =>
    apiFetch<{ items: { stored_at: string; predicted_latency_ms: number; routing_decision: string; reason: string }[] }>(
      `${BASE}/metrics/timeseries?limit=${limit}`
    ),

  decisions: (limit = 50, offset = 0) =>
    apiFetch<DecisionsResponse>(`${BASE}/decisions?limit=${limit}&offset=${offset}`),

  devices: () =>
    apiFetch<{ devices: unknown[] }>(`${BASE}/devices`),

  /** Mock login against the existing auth endpoint.
   *  Returns a User on success or throws on failure. */
  login: async (username: string, password: string): Promise<User> => {
    const res = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) throw new Error('Invalid credentials');
    const data = await res.json() as { token: string; role?: Role };
    const user: User = { username, role: data.role ?? 'admin' };
    setSession(data.token, user);
    return user;
  },
};
