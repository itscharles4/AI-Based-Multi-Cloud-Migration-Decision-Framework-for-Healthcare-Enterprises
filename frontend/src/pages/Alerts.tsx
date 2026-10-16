// src/pages/Alerts.tsx
// Real Alerts page — shows emergency overrides and network vetoes from the DB
// Includes a one-click "Fire Demo Alert" button for faculty demonstrations
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { fmtLatency, fmtCriticality, fmtTimeShort, fmtReason } from '../lib/utils';
import {
  AlertTriangle, Bell, CheckCircle, XCircle, Clock,
  Send, Zap, Wifi, RefreshCw,
} from 'lucide-react';

interface AlertRow {
  device_id: string;
  stored_at: string;
  routing_decision: 'EDGE' | 'CLOUD';
  reason: string;
  patient_criticality_score: number;
  predicted_latency_ms: number;
}

type SeverityFilter = 'all' | 'emergency' | 'veto';

function SeverityBadge({ reason }: { reason: string }) {
  if (reason === 'override_critical_patient') {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full"
        style={{ background: 'rgba(220,38,38,0.12)', color: 'var(--emergency)', border: '1px solid rgba(220,38,38,0.3)' }}>
        <AlertTriangle size={10} /> EMERGENCY
      </span>
    );
  }
  if (reason === 'network_degradation_veto') {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full"
        style={{ background: 'rgba(180,83,9,0.12)', color: 'var(--veto)', border: '1px solid rgba(180,83,9,0.3)' }}>
        <Wifi size={10} /> NET VETO
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full"
      style={{ background: 'var(--border)', color: 'var(--muted)' }}>
      {fmtReason(reason)}
    </span>
  );
}

function ChannelPill({ icon: Icon, label, ok }: { icon: React.ElementType; label: string; ok: boolean }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
      style={{
        background: ok ? 'rgba(21,128,61,0.10)' : 'rgba(220,38,38,0.08)',
        color: ok ? 'var(--ok)' : 'var(--emergency)',
        border: `1px solid ${ok ? 'rgba(21,128,61,0.25)' : 'rgba(220,38,38,0.2)'}`,
      }}>
      <Icon size={10} />
      {label}
      {ok ? <CheckCircle size={10} /> : <XCircle size={10} />}
    </span>
  );
}

// ── Faculty Demo Alert Button ──────────────────────────────────────────────
function DemoAlertButton({ onFired }: { onFired: () => void }) {
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [msg, setMsg] = useState('');

  async function fire() {
    setStatus('loading');
    try {
      const res = await fetch('/api/v1/demo/trigger-emergency', { method: 'POST' });
      const data = await res.json();
      setStatus('success');
      setMsg(data.message ?? 'Alert fired!');
      onFired();
      setTimeout(() => setStatus('idle'), 8000);
    } catch {
      setStatus('error');
      setMsg('Failed to reach backend');
      setTimeout(() => setStatus('idle'), 4000);
    }
  }

  return (
    <div className="rounded-xl border p-5" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
      <div className="flex items-start gap-3">
        <div className="rounded-xl p-2.5 shrink-0" style={{ background: 'rgba(220,38,38,0.10)' }}>
          <Send size={20} style={{ color: 'var(--emergency)' }} />
        </div>
        <div className="flex-1">
          <h3 className="font-semibold text-sm" style={{ color: 'var(--text)' }}>
            🎓 Faculty Demo — Live Alert Trigger
          </h3>
          <p className="text-xs mt-1" style={{ color: 'var(--muted)' }}>
            Fires a critical patient event (ECG-DEMO, criticality 9.8/10). The system forces
            EDGE routing via Emergency Override and sends a <strong>real</strong> Telegram message
            + Gmail email to the configured channels instantly.
          </p>

          {status === 'success' && (
            <div className="mt-2 text-xs rounded-lg px-3 py-2 flex items-center gap-2"
              style={{ background: 'rgba(21,128,61,0.10)', color: 'var(--ok)', border: '1px solid rgba(21,128,61,0.25)' }}>
              <CheckCircle size={13} /> {msg}
            </div>
          )}
          {status === 'error' && (
            <div className="mt-2 text-xs rounded-lg px-3 py-2 flex items-center gap-2"
              style={{ background: 'rgba(220,38,38,0.08)', color: 'var(--emergency)', border: '1px solid rgba(220,38,38,0.2)' }}>
              <XCircle size={13} /> {msg}
            </div>
          )}
        </div>
        <button
          onClick={fire}
          disabled={status === 'loading'}
          className="shrink-0 px-4 py-2 rounded-lg text-sm font-bold text-white transition-all disabled:opacity-60 hover:opacity-90"
          style={{ background: status === 'success' ? 'var(--ok)' : 'var(--emergency)' }}>
          {status === 'loading' ? (
            <span className="flex items-center gap-2"><RefreshCw size={14} className="animate-spin" /> Sending…</span>
          ) : status === 'success' ? (
            <span className="flex items-center gap-2"><CheckCircle size={14} /> Sent!</span>
          ) : (
            <span className="flex items-center gap-2"><AlertTriangle size={14} /> Fire Alert Now</span>
          )}
        </button>
      </div>
    </div>
  );
}

export default function Alerts() {
  const [filter, setFilter] = useState<SeverityFilter>('all');
  const [refreshKey, setRefreshKey] = useState(0);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['decisions-alerts', refreshKey],
    queryFn: () => api.decisions(500),
    refetchInterval: 10_000,
  });

  // Filter to only alert-worthy events
  const allAlerts: AlertRow[] = (data?.items ?? []).filter(
    d => d.reason === 'override_critical_patient' || d.reason === 'network_degradation_veto'
  );

  const filtered = allAlerts.filter(a => {
    if (filter === 'emergency') return a.reason === 'override_critical_patient';
    if (filter === 'veto')      return a.reason === 'network_degradation_veto';
    return true;
  });

  const emergencyCount = allAlerts.filter(a => a.reason === 'override_critical_patient').length;
  const vetoCount      = allAlerts.filter(a => a.reason === 'network_degradation_veto').length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text)' }}>Alerts</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>
            Emergency overrides + network vetoes · Telegram + Gmail delivery
          </p>
        </div>
        <button onClick={() => refetch()}
          className="px-4 py-2 rounded-lg text-sm font-medium border transition-colors hover:opacity-80"
          style={{ background: 'var(--surface)', borderColor: 'var(--border)', color: 'var(--text)' }}>
          <RefreshCw size={14} className="inline mr-1" /> Refresh
        </button>
      </div>

      {/* Demo trigger for faculty */}
      <DemoAlertButton onFired={() => { setRefreshKey(k => k + 1); refetch(); }} />

      {/* Summary KPIs */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Total Alerts', value: allAlerts.length, icon: Bell, color: 'var(--cloud)' },
          { label: 'Emergency Overrides', value: emergencyCount, icon: AlertTriangle, color: 'var(--emergency)' },
          { label: 'Network Vetoes', value: vetoCount, icon: Wifi, color: 'var(--veto)' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="rounded-xl border p-4" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
            <div className="flex items-center gap-2 mb-1">
              <Icon size={15} style={{ color }} />
              <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--muted)' }}>{label}</span>
            </div>
            <p className="text-3xl font-bold" style={{ color: 'var(--text)', fontSize: 32 }}>{value}</p>
          </div>
        ))}
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2">
        {(['all', 'emergency', 'veto'] as SeverityFilter[]).map(f => (
          <button key={f} onClick={() => setFilter(f)}
            className="px-4 py-1.5 rounded-lg text-sm font-medium border transition-colors"
            style={{
              background: filter === f ? 'var(--cloud)' : 'var(--surface)',
              color:      filter === f ? 'white' : 'var(--muted)',
              borderColor: 'var(--border)',
            }}>
            {f === 'all' ? `All (${allAlerts.length})` : f === 'emergency' ? `Emergency (${emergencyCount})` : `Network Veto (${vetoCount})`}
          </button>
        ))}
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 rounded-xl animate-pulse" style={{ background: 'var(--surface)' }} />
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="text-center py-10 rounded-xl border" style={{ background: 'var(--surface)', borderColor: 'var(--border)', color: 'var(--emergency)' }}>
          Failed to load alerts — API offline?
        </div>
      )}

      {/* Empty */}
      {!isLoading && !error && filtered.length === 0 && (
        <div className="text-center py-16 rounded-xl border" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <Bell size={36} className="mx-auto mb-3" style={{ color: 'var(--muted)' }} />
          <p className="font-semibold" style={{ color: 'var(--text)' }}>No alerts in this view</p>
          <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>
            Use the demo button above to fire a live emergency alert, or run the simulator.
          </p>
        </div>
      )}

      {/* Alert table */}
      {!isLoading && filtered.length > 0 && (
        <div className="rounded-xl border overflow-hidden" style={{ borderColor: 'var(--border)' }}>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-xs font-semibold uppercase tracking-wider"
                style={{ background: 'var(--page)', borderColor: 'var(--border)', color: 'var(--muted)' }}>
                <th className="px-4 py-3 text-left">Severity</th>
                <th className="px-4 py-3 text-left">Device</th>
                <th className="px-4 py-3 text-left">Criticality</th>
                <th className="px-4 py-3 text-left">Latency</th>
                <th className="px-4 py-3 text-left">Delivery</th>
                <th className="px-4 py-3 text-left">Time (IST)</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((a, i) => (
                <tr key={i} className="border-b last:border-0 hover:opacity-80 transition-opacity"
                  style={{ borderColor: 'var(--border)', background: i % 2 === 0 ? 'var(--surface)' : 'var(--page)' }}>
                  <td className="px-4 py-3"><SeverityBadge reason={a.reason} /></td>
                  <td className="px-4 py-3 font-mono font-semibold text-xs" style={{ color: 'var(--text)' }}>{a.device_id}</td>
                  <td className="px-4 py-3">
                    <span className="font-semibold" style={{
                      color: a.patient_criticality_score >= 9 ? 'var(--emergency)' :
                             a.patient_criticality_score >= 7 ? 'var(--veto)' : 'var(--text)'
                    }}>
                      {fmtCriticality(a.patient_criticality_score)}
                    </span>
                  </td>
                  <td className="px-4 py-3" style={{ color: 'var(--text)' }}>{fmtLatency(a.predicted_latency_ms)}</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1.5 flex-wrap">
                      <ChannelPill icon={Send} label="Telegram" ok={a.reason === 'override_critical_patient'} />
                      <ChannelPill icon={Bell} label="Gmail" ok={a.reason === 'override_critical_patient'} />
                    </div>
                  </td>
                  <td className="px-4 py-3 text-xs" style={{ color: 'var(--muted)' }}>
                    <Clock size={11} className="inline mr-1" />
                    {fmtTimeShort(a.stored_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
