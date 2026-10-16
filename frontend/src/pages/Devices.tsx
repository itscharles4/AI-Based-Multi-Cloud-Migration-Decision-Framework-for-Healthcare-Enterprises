// src/pages/Devices.tsx
// Real Devices page — reads /api/v1/devices, shows device cards with sparklines
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { fmtLatency, fmtCriticality, fmtTimeShort } from '../lib/utils';
import { Activity, Cpu, Cloud, Zap, AlertTriangle, Clock } from 'lucide-react';
import {
  LineChart, Line, ResponsiveContainer, Tooltip,
} from 'recharts';

// ── Device type colours ────────────────────────────────────────────────────
const DEVICE_META: Record<string, { label: string; color: string; icon: string }> = {
  'ECG-101':   { label: 'ECG Monitor',         color: 'var(--cloud)',     icon: '❤️' },
  'SPO2-202':  { label: 'Pulse Oximeter',       color: 'var(--ok)',        icon: '🫁' },
  'BP-303':    { label: 'Blood Pressure Sensor',color: 'var(--veto)',      icon: '💉' },
  'TEMP-404':  { label: 'Temperature Sensor',   color: 'var(--edge)',      icon: '🌡️' },
  'RESP-505':  { label: 'Respiratory Monitor',  color: 'var(--muted)',     icon: '💨' },
  'ECG-DEMO':  { label: 'Demo ECG (Faculty)',   color: 'var(--emergency)', icon: '🔴' },
};

function getMeta(id: string) {
  return DEVICE_META[id] ?? { label: id, color: 'var(--cloud)', icon: '📡' };
}

interface DeviceData {
  device_id: string;
  total: number;
  edge_count: number;
  cloud_count: number;
  last_seen: string;
  avg_latency_ms: number;
  max_criticality: number;
  sparkline: number[];
  status: string;
}

function RiskBadge({ score }: { score: number }) {
  let label = 'LOW';
  let color = 'var(--ok)';
  if (score >= 9) { label = 'CRITICAL'; color = 'var(--emergency)'; }
  else if (score >= 7) { label = 'HIGH'; color = 'var(--veto)'; }
  else if (score >= 4) { label = 'MEDIUM'; color = 'var(--cloud)'; }
  return (
    <span className="text-xs font-bold px-2 py-0.5 rounded-full"
      style={{ background: `${color}20`, color, border: `1px solid ${color}40` }}>
      {label} {score.toFixed(1)}
    </span>
  );
}

function Sparkline({ data, color }: { data: number[]; color: string }) {
  const pts = data.map((v, i) => ({ i, v }));
  if (pts.length === 0) return <div className="h-12 flex items-center text-xs" style={{ color: 'var(--muted)' }}>No data</div>;
  return (
    <ResponsiveContainer width="100%" height={48}>
      <LineChart data={pts} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
        <Line type="monotone" dataKey="v" dot={false} stroke={color} strokeWidth={1.5} />
        <Tooltip
          formatter={(v: unknown) => [`${Number(v).toFixed(1)} ms`, 'Latency']}
          contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 11 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

function DeviceCard({ d }: { d: DeviceData }) {
  const meta = getMeta(d.device_id);
  const edgePct = d.total > 0 ? Math.round((d.edge_count / d.total) * 100) : 0;

  return (
    <div className="rounded-xl border p-5 flex flex-col gap-3 hover:shadow-md transition-shadow"
      style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{meta.icon}</span>
          <div>
            <p className="font-bold text-sm" style={{ color: 'var(--text)' }}>{d.device_id}</p>
            <p className="text-xs" style={{ color: 'var(--muted)' }}>{meta.label}</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full animate-pulse" style={{ background: 'var(--ok)' }} />
          <span className="text-xs font-medium" style={{ color: 'var(--ok)' }}>Online</span>
        </div>
      </div>

      {/* Sparkline — 24 latest latency readings */}
      <div>
        <p className="text-xs mb-1" style={{ color: 'var(--muted)' }}>Predicted Latency (last {d.sparkline.length} readings)</p>
        <Sparkline data={d.sparkline} color={meta.color} />
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg p-3" style={{ background: 'var(--page)' }}>
          <p className="text-xs" style={{ color: 'var(--muted)' }}>Total Readings</p>
          <p className="text-xl font-bold mt-0.5" style={{ color: 'var(--text)' }}>{d.total.toLocaleString()}</p>
        </div>
        <div className="rounded-lg p-3" style={{ background: 'var(--page)' }}>
          <p className="text-xs" style={{ color: 'var(--muted)' }}>Avg Latency</p>
          <p className="text-xl font-bold mt-0.5" style={{ color: 'var(--text)' }}>{fmtLatency(d.avg_latency_ms)}</p>
        </div>
      </div>

      {/* Routing bar */}
      <div>
        <div className="flex justify-between text-xs mb-1" style={{ color: 'var(--muted)' }}>
          <span>EDGE ({d.edge_count})</span>
          <span>CLOUD ({d.cloud_count})</span>
        </div>
        <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
          <div className="h-full rounded-full" style={{ width: `${edgePct}%`, background: 'var(--edge)' }} />
        </div>
        <div className="flex justify-between text-xs mt-1" style={{ color: 'var(--muted)' }}>
          <span>{edgePct}% EDGE</span>
          <span>{100 - edgePct}% CLOUD</span>
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-1 border-t" style={{ borderColor: 'var(--border)' }}>
        <RiskBadge score={d.max_criticality} />
        <span className="text-xs" style={{ color: 'var(--muted)' }}>
          <Clock size={11} className="inline mr-1" />
          Last: {fmtTimeShort(d.last_seen)}
        </span>
      </div>
    </div>
  );
}

export default function Devices() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['devices'],
    queryFn: () => api.devices(),
    refetchInterval: 15_000,
  });

  const devices: DeviceData[] = (data as any)?.devices ?? [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text)' }}>Devices</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>
            {devices.length} active IoMT device{devices.length !== 1 ? 's' : ''} · auto-refreshes every 15s
          </p>
        </div>
        <button onClick={() => refetch()}
          className="px-4 py-2 rounded-lg text-sm font-medium border transition-colors hover:opacity-80"
          style={{ background: 'var(--surface)', borderColor: 'var(--border)', color: 'var(--text)' }}>
          ↻ Refresh
        </button>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-6">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="rounded-xl border p-5 animate-pulse" style={{ background: 'var(--surface)', borderColor: 'var(--border)', height: 260 }} />
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="text-center py-20 rounded-xl border" style={{ background: 'var(--surface)', borderColor: 'var(--border)', color: 'var(--emergency)' }}>
          <Activity size={40} className="mx-auto mb-3 opacity-40" />
          <p className="font-semibold">Failed to load devices</p>
          <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>Make sure the API backend is running on port 8000</p>
        </div>
      )}

      {/* Empty */}
      {!isLoading && !error && devices.length === 0 && (
        <div className="text-center py-20 rounded-xl border" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <Cpu size={40} className="mx-auto mb-3" style={{ color: 'var(--muted)' }} />
          <p className="font-semibold" style={{ color: 'var(--text)' }}>No devices found</p>
          <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>
            Run the simulator to generate IoMT data:<br />
            <code className="text-xs">python src/api/simulate_stream.py</code>
          </p>
        </div>
      )}

      {/* Device grid */}
      {!isLoading && devices.length > 0 && (
        <>
          {/* Summary bar */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: 'Devices', value: devices.length, icon: Cpu, color: 'var(--cloud)' },
              { label: 'Total Readings', value: devices.reduce((a, d) => a + d.total, 0).toLocaleString(), icon: Activity, color: 'var(--edge)' },
              { label: 'Avg Latency', value: `${(devices.reduce((a, d) => a + d.avg_latency_ms, 0) / Math.max(devices.length, 1)).toFixed(1)} ms`, icon: Clock, color: 'var(--veto)' },
              { label: 'Critical Events', value: devices.filter(d => d.max_criticality >= 9).length, icon: AlertTriangle, color: 'var(--emergency)' },
            ].map(({ label, value, icon: Icon, color }) => (
              <div key={label} className="rounded-xl border p-4" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                <div className="flex items-center gap-2 mb-1">
                  <Icon size={15} style={{ color }} />
                  <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--muted)' }}>{label}</span>
                </div>
                <p className="text-2xl font-bold" style={{ color: 'var(--text)' }}>{value}</p>
              </div>
            ))}
          </div>

          {/* Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-6">
            {devices.map(d => <DeviceCard key={d.device_id} d={d} />)}
          </div>
        </>
      )}
    </div>
  );
}
