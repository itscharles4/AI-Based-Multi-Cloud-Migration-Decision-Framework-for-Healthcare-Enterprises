// src/lib/utils.ts
// Shared formatting helpers — guide §4 format rules

/** Format latency: 38.6 ms */
export function fmtLatency(ms: number | null | undefined): string {
  if (ms == null) return '—';
  return `${ms.toFixed(1)} ms`;
}

/** Format criticality: 9.5 / 10 */
export function fmtCriticality(v: number | null | undefined): string {
  if (v == null) return '—';
  return `${v.toFixed(1)} / 10`;
}

/** Format count: 1,284 */
export function fmtCount(n: number): string {
  return n.toLocaleString();
}

/** Format pct: 25.9% */
export function fmtPct(p: number): string {
  return `${p.toFixed(1)}%`;
}

/** Format UTC ISO timestamp to IST (or chosen TZ) with label */
export function fmtTime(iso: string | null | undefined, tz = 'Asia/Kolkata'): string {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString('en-IN', {
      timeZone: tz,
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    }) + ' IST';
  } catch {
    return iso.slice(0, 19);
  }
}

/** Format time as HH:MM:SS IST */
export function fmtTimeShort(iso: string | null | undefined, tz = 'Asia/Kolkata'): string {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString('en-IN', { timeZone: tz, hour12: false }) + ' IST';
  } catch {
    return iso.slice(11, 19);
  }
}

/** Reason code → human label */
export const REASON_LABELS: Record<string, string> = {
  'ahp_decision':             'AHP Decision',
  'override_critical_patient':'Emergency Override',
  'network_degradation_veto': 'Network Degradation Veto',
};

export function fmtReason(code: string): string {
  return REASON_LABELS[code] ?? code.replace(/_/g, ' ');
}

/** CSS class for routing decision badge */
export function decisionClass(d: string): string {
  return d === 'EDGE'
    ? 'bg-[var(--edge)] text-white'
    : 'bg-[var(--cloud)] text-white';
}

/** CSS class for reason badge */
export function reasonClass(r: string): string {
  if (r === 'override_critical_patient') return 'bg-[var(--emergency)] text-white';
  if (r === 'network_degradation_veto')  return 'bg-[var(--veto)] text-white';
  return 'bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-100';
}

export function clsx(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(' ');
}
