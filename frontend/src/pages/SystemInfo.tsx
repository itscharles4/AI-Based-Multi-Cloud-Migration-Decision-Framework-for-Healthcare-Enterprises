// src/pages/SystemInfo.tsx
// Guide §3 System page — live architecture from /api/v1/system/info
// Every label comes from the API, nothing is hard-coded.
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { Settings, Database, Brain, Zap, Cloud, ExternalLink } from 'lucide-react';

function Card({ title, icon: Icon, children }: {
  title: string; icon: React.ElementType; children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border p-5" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
      <div className="flex items-center gap-2 mb-4">
        <Icon size={17} style={{ color: 'var(--cloud)' }} />
        <h2 className="font-semibold text-sm" style={{ color: 'var(--text)' }}>{title}</h2>
      </div>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between py-1.5 border-b last:border-0 text-sm"
      style={{ borderColor: 'var(--border)' }}>
      <span style={{ color: 'var(--muted)' }}>{label}</span>
      <span className="text-right font-medium" style={{ color: 'var(--text)', maxWidth: '60%' }}>{value}</span>
    </div>
  );
}

export default function SystemInfo() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['system-info'],
    queryFn: api.systemInfo,
    staleTime: 30_000,
  });

  if (isLoading) return (
    <div className="space-y-4">
      {[...Array(4)].map((_, i) => (
        <div key={i} className="h-40 rounded-xl animate-pulse" style={{ background: 'var(--border)' }} />
      ))}
    </div>
  );

  if (error || !data) return (
    <div className="text-center py-20 text-sm" style={{ color: 'var(--emergency)' }}>
      Could not load system info — is the API backend running?
    </div>
  );

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2" style={{ color: 'var(--text)' }}>
          <Settings size={24} style={{ color: 'var(--cloud)' }} /> System Information
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>
          {data.project} · {data.course} · {data.institute}
        </p>
      </div>

      {/* Live stats */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Total Decisions', value: data.runtime_stats.total_decisions.toLocaleString() },
          { label: 'EDGE Routed',     value: data.runtime_stats.edge.toLocaleString() },
          { label: 'CLOUD Routed',    value: data.runtime_stats.cloud.toLocaleString() },
        ].map(s => (
          <div key={s.label} className="rounded-xl border p-4 text-center"
            style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
            <p className="text-2xl font-bold" style={{ color: 'var(--text)' }}>{s.value}</p>
            <p className="text-xs mt-1" style={{ color: 'var(--muted)' }}>{s.label}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">

        {/* Backend */}
        <Card title="Backend Stack" icon={Database}>
          <Row label="Framework"    value={data.backend.framework} />
          <Row label="Python"       value={data.backend.python} />
          <Row label="Storage"      value={data.backend.storage} />
          <Row label="Auth"         value={data.backend.auth} />
          <Row label="Audit"        value={data.backend.audit} />
          <Row label="Alert channels" value={data.backend.alerts.join(', ')} />
        </Card>

        {/* Model */}
        <Card title="AI Model" icon={Brain}>
          <Row label="Architecture" value={data.model.name} />
          <Row label="File"         value={data.model.file} />
          <Row label="Status"       value={
            <span style={{ color: data.model.loaded ? 'var(--ok)' : 'var(--veto)' }}>
              {data.model.loaded ? 'Loaded' : 'Fallback (dummy)'}
            </span>
          } />
          <Row label="ML backend"   value={data.model.ml_backend} />
          <Row label="Window"       value={`${data.model.window_size} readings`} />
          <Row label="Thresholds"   value={`${data.model.thresholds_ms.low_medium} / ${data.model.thresholds_ms.medium_high} / ${data.model.thresholds_ms.veto} ms`} />
        </Card>

        {/* Decision engine */}
        <Card title="Decision Engine" icon={Zap}>
          <Row label="Type"                value={data.decision_engine.type} />
          <Row label="Emergency threshold" value={`≥ ${data.decision_engine.emergency_threshold} / 10`} />
          <Row label="Network veto"        value={`≥ ${data.decision_engine.veto_threshold_ms} ms`} />
          <Row label="Consistency ratio"   value={data.decision_engine.consistency_ratio} />
          <Row label="Weights" value={
            Object.entries(data.decision_engine.weights)
              .map(([k, v]) => `${k}: ${v}`)
              .join(' · ')
          } />
        </Card>

        {/* Team */}
        <Card title="Team" icon={Settings}>
          {data.team.map(m => (
            <div key={m.roll} className="flex items-start gap-3 py-2 border-b last:border-0"
              style={{ borderColor: 'var(--border)' }}>
              <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0"
                style={{ background: 'var(--cloud)' }}>
                {m.name[0]}
              </div>
              <div>
                <p className="font-medium text-sm" style={{ color: 'var(--text)' }}>{m.name}</p>
                <p className="text-xs" style={{ color: 'var(--muted)' }}>{m.roll} · {m.module}</p>
              </div>
            </div>
          ))}
        </Card>
      </div>

      {/* AWS Migration Map */}
      <Card title="AWS Migration Path" icon={Cloud}>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b" style={{ borderColor: 'var(--border)' }}>
              <th className="text-left py-2 font-semibold text-xs uppercase tracking-wide" style={{ color: 'var(--muted)' }}>
                Current (Local)
              </th>
              <th className="text-left py-2 font-semibold text-xs uppercase tracking-wide" style={{ color: 'var(--muted)' }}>
                AWS Target Service
              </th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(data.aws_migration_map).map(([local, aws]) => (
              <tr key={local} className="border-b last:border-0" style={{ borderColor: 'var(--border)' }}>
                <td className="py-2.5 pr-4 font-mono text-xs" style={{ color: 'var(--muted)' }}>{local}</td>
                <td className="py-2.5 flex items-center gap-1.5">
                  <span className="text-sm font-medium" style={{ color: 'var(--cloud)' }}>{aws}</span>
                  <ExternalLink size={11} style={{ color: 'var(--muted)' }} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
