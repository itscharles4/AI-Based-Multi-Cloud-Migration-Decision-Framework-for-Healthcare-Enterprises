// src/pages/Overview.tsx
// Guide §3 Overview page — KPI row, latency chart, routing donut,
// decision reasons bar, latest alerts. All values from /api/v1/*.
import { useQuery } from '@tanstack/react-query';
import {
  PieChart, Pie, Cell, Legend, Tooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, ReferenceLine,
  LineChart, Line, Tooltip as LT,
} from 'recharts';
import { api } from '../lib/api';
import { fmtCount, fmtPct, fmtLatency, fmtTimeShort, fmtReason } from '../lib/utils';
import { TrendingUp, Cloud, Zap, AlertTriangle, Bell, Clock } from 'lucide-react';

// Design tokens
const C = {
  cloud:     'var(--cloud)',
  edge:      'var(--edge)',
  emergency: 'var(--emergency)',
  veto:      'var(--veto)',
  ok:        'var(--ok)',
};

function KpiCard({
  label, value, sub, icon: Icon, accent,
}: { label: string; value: string; sub?: string; icon: React.ElementType; accent: string }) {
  return (
    <div className="rounded-xl p-5 border flex flex-col gap-1"
      style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
      <div className="flex items-center gap-2 mb-1">
        <div className="rounded-lg p-1.5" style={{ background: `${accent}18` }}>
          <Icon size={15} style={{ color: accent }} />
        </div>
        <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
          {label}
        </span>
      </div>
      <span className="text-3xl font-bold leading-none" style={{ color: 'var(--text)', fontSize: 36 }}>
        {value}
      </span>
      {sub && <span className="text-xs" style={{ color: 'var(--muted)' }}>{sub}</span>}
    </div>
  );
}

function Skeleton({ h = 'h-8' }: { h?: string }) {
  return <div className={`${h} rounded-lg animate-pulse`} style={{ background: 'var(--border)' }} />;
}

export default function Overview() {
  const { data: summary, isLoading: loadingS, error: errS } =
    useQuery({ queryKey: ['metrics-summary'], queryFn: () => api.metricsSummary(), refetchInterval: 15_000 });

  const { data: decisions, isLoading: loadingD } =
    useQuery({ queryKey: ['decisions'], queryFn: () => api.decisions(100), refetchInterval: 15_000 });

  if (loadingS) return (
    <div className="space-y-6">
      <Skeleton h="h-12" />
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {[...Array(6)].map((_, i) => <Skeleton key={i} h="h-28" />)}
      </div>
    </div>
  );

  if (errS) return (
    <div className="text-center py-20" style={{ color: 'var(--emergency)' }}>
      Failed to load metrics — is the API backend running?<br />
      <code className="text-sm">python -m uvicorn src.api.main:app --port 8000</code>
    </div>
  );

  const s = summary!;

  // Prepare charts data
  const donutData = [
    { name: 'CLOUD', value: s.cloud.count, color: C.cloud },
    { name: 'EDGE',  value: s.edge.count,  color: C.edge  },
  ];

  const reasonsData = [
    { name: 'AHP Decision',              value: s.reasons.ahp_decision,             color: C.cloud },
    { name: 'Network Veto',              value: s.reasons.network_degradation_veto, color: C.veto  },
    { name: 'Emergency Override',        value: s.reasons.emergency_override,        color: C.emergency },
    { name: 'Uncategorised',             value: s.reasons.uncategorised,             color: '#94A3B8' },
  ].filter(r => r.value > 0);

  // Latency series from recent decisions
  const latSeries = (decisions?.items ?? [])
    .slice().reverse()
    .map((d, i) => ({
      i,
      latency: +d.predicted_latency_ms.toFixed(1),
      decision: d.routing_decision,
    }));

  // Latest alerts (emergency overrides only)
  const alerts = (decisions?.items ?? []).filter(d => d.reason === 'override_critical_patient').slice(0, 5);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold" style={{ color: 'var(--text)' }}>Overview</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>
          Real-time IoMT routing metrics · IST timezone · source: {s.source_filter}
        </p>
      </div>

      {/* ── KPI row ── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        <KpiCard label="Total Decisions" value={fmtCount(s.total_decisions)} icon={TrendingUp} accent={C.cloud} />
        <KpiCard label="EDGE"  value={fmtCount(s.edge.count)}  sub={fmtPct(s.edge.pct)}  icon={Zap}   accent={C.edge}  />
        <KpiCard label="CLOUD" value={fmtCount(s.cloud.count)} sub={fmtPct(s.cloud.pct)} icon={Cloud} accent={C.cloud} />
        <KpiCard label="Emergency Overrides" value={fmtCount(s.alerts.emergency_overrides)} icon={AlertTriangle} accent={C.emergency} />
        <KpiCard label="Network Vetoes" value={fmtCount(s.reasons.network_degradation_veto)} icon={Clock} accent={C.veto} />
        <KpiCard
          label="Alerts Delivered" icon={Bell} accent={C.ok}
          value={fmtCount(s.alerts.delivered)}
          sub={s.alerts.failed > 0 ? `${s.alerts.failed} failed` : 'Telegram + Gmail'}
        />
      </div>

      {/* ── Charts row ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Latency trend */}
        <div className="lg:col-span-2 rounded-xl border p-5"
          style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <h2 className="font-semibold text-sm mb-4" style={{ color: 'var(--text)' }}>
            Predicted Latency Trend
            <span className="ml-2 text-xs font-normal" style={{ color: 'var(--muted)' }}>(last 100 events)</span>
          </h2>
          {loadingD ? <Skeleton h="h-52" /> : latSeries.length === 0
            ? <div className="h-52 flex items-center justify-center text-sm" style={{ color: 'var(--muted)' }}>No data yet</div>
            : (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={latSeries} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="i" hide />
                  <LT
                    formatter={(v) => v != null ? [`${Number(v).toFixed(1)} ms`, 'Predicted'] : ['—', 'Predicted']}
                    contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                  />
                  <ReferenceLine y={75}  stroke={C.veto}      strokeDasharray="4 2" label={{ value: '75 ms',  position: 'right', fontSize: 10, fill: C.veto  }} />
                  <ReferenceLine y={150} stroke={C.veto}      strokeDasharray="4 2" label={{ value: '150 ms', position: 'right', fontSize: 10, fill: C.veto  }} />
                  <ReferenceLine y={300} stroke={C.emergency} strokeDasharray="4 2" label={{ value: '300 ms (veto)', position: 'right', fontSize: 10, fill: C.emergency }} />
                  <Line type="monotone" dataKey="latency" dot={false} stroke={C.cloud} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            )}
        </div>

        {/* Routing donut */}
        <div className="rounded-xl border p-5"
          style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <h2 className="font-semibold text-sm mb-4" style={{ color: 'var(--text)' }}>Routing Split</h2>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={donutData} cx="50%" cy="50%" innerRadius={55} outerRadius={85}
                dataKey="value" nameKey="name"
                label={({ name, value }) => `${name}: ${fmtCount(value)}`}
                labelLine={true}>
                {donutData.map((d, i) => <Cell key={i} fill={d.color} />)}
              </Pie>
              <Legend formatter={(v) => <span style={{ color: 'var(--text)', fontSize: 12 }}>{v}</span>} />
              <Tooltip formatter={(v) => fmtCount(Number(v))} contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Reasons + Alerts ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Decision reasons bar */}
        <div className="rounded-xl border p-5"
          style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <h2 className="font-semibold text-sm mb-1" style={{ color: 'var(--text)' }}>Decision Reasons</h2>
          <p className="text-xs mb-4" style={{ color: 'var(--muted)' }}>
            Sum: {fmtCount(reasonsData.reduce((a, r) => a + r.value, 0))} of {fmtCount(s.total_decisions)} total
          </p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={reasonsData} margin={{ top: 5, right: 10, left: 0, bottom: 30 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: 'var(--muted)' }} angle={-15} textAnchor="end" interval={0} />
              <YAxis tick={{ fontSize: 10, fill: 'var(--muted)' }} />
              <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {reasonsData.map((d, i) => <Cell key={i} fill={d.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Latest alerts */}
        <div className="rounded-xl border p-5"
          style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <h2 className="font-semibold text-sm mb-4" style={{ color: 'var(--text)' }}>
            Latest Emergency Alerts
          </h2>
          {alerts.length === 0 ? (
            <div className="text-sm py-8 text-center" style={{ color: 'var(--muted)' }}>
              No emergency alerts in current data
            </div>
          ) : (
            <ul className="space-y-2">
              {alerts.map((a, i) => (
                <li key={i} className="flex items-start justify-between rounded-lg px-3 py-2.5 text-sm"
                  style={{ background: 'rgba(220,38,38,0.07)', border: '1px solid rgba(220,38,38,0.2)' }}>
                  <div>
                    <span className="font-semibold" style={{ color: 'var(--emergency)' }}>
                      {a.device_id}
                    </span>
                    <span className="mx-1.5" style={{ color: 'var(--muted)' }}>·</span>
                    <span style={{ color: 'var(--muted)' }}>Criticality {a.patient_criticality_score.toFixed(1)}/10</span>
                    <br />
                    <span className="text-xs" style={{ color: 'var(--muted)' }}>
                      {fmtLatency(a.predicted_latency_ms)} · Telegram + Gmail dispatched
                    </span>
                  </div>
                  <span className="text-xs shrink-0" style={{ color: 'var(--muted)' }}>
                    {fmtTimeShort(a.stored_at)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
