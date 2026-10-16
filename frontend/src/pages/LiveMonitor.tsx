// src/pages/LiveMonitor.tsx
// Real-time decisions table fed by polling (SSE fallback)
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { fmtLatency, fmtCriticality, fmtTimeShort, fmtReason, decisionClass, reasonClass } from '../lib/utils';
import { Pause, Play, Filter } from 'lucide-react';

type Filter = 'all' | 'EDGE' | 'CLOUD';

export default function LiveMonitor() {
  const [paused, setPaused]  = useState(false);
  const [filter, setFilter]  = useState<Filter>('all');
  const [selected, setSelected] = useState<number | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ['decisions-live'],
    queryFn: () => api.decisions(200),
    refetchInterval: paused ? false : 3000,
  });

  const items = (data?.items ?? []).filter(d =>
    filter === 'all' || d.routing_decision === filter
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text)' }}>Live Monitor</h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--muted)' }}>
            {paused ? 'Paused' : 'Updating every 3 s'} · {data?.total ?? 0} total decisions
          </p>
        </div>
        <div className="flex gap-2">
          {(['all', 'EDGE', 'CLOUD'] as Filter[]).map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className="px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors"
              style={{
                background: filter === f ? 'var(--cloud)' : 'var(--surface)',
                color:      filter === f ? 'white' : 'var(--muted)',
                borderColor: 'var(--border)',
              }}>
              {f === 'all' ? 'All' : f}
            </button>
          ))}
          <button onClick={() => setPaused(p => !p)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-sm font-medium"
            style={{ background: 'var(--surface)', borderColor: 'var(--border)', color: 'var(--text)' }}>
            {paused ? <><Play size={14} /> Resume</> : <><Pause size={14} /> Pause</>}
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border overflow-hidden"
        style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
        {isLoading ? (
          <div className="p-8 text-center text-sm" style={{ color: 'var(--muted)' }}>Loading…</div>
        ) : error ? (
          <div className="p-8 text-center text-sm" style={{ color: 'var(--emergency)' }}>
            Failed to load — API offline?
          </div>
        ) : items.length === 0 ? (
          <div className="p-12 text-center" style={{ color: 'var(--muted)' }}>
            <Filter size={32} className="mx-auto mb-3 opacity-30" />
            <p className="font-medium">No decisions yet</p>
            <p className="text-sm mt-1">Run the simulator to populate the pipeline.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b" style={{ borderColor: 'var(--border)', background: 'var(--page)' }}>
                  {['Device', 'Time (IST)', 'Decision', 'Reason', 'Latency', 'Criticality'].map(h => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wide"
                      style={{ color: 'var(--muted)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((d, i) => (
                  <>
                    <tr key={i}
                      onClick={() => setSelected(selected === i ? null : i)}
                      className="border-b cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors"
                      style={{ borderColor: 'var(--border)' }}>
                      <td className="px-4 py-3 font-mono text-xs">{d.device_id}</td>
                      <td className="px-4 py-3 text-xs whitespace-nowrap" style={{ color: 'var(--muted)' }}>
                        {fmtTimeShort(d.stored_at)}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-xs font-bold px-2 py-1 rounded-full ${decisionClass(d.routing_decision)}`}>
                          {d.routing_decision}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-xs px-2 py-1 rounded-full ${reasonClass(d.reason)}`}>
                          {fmtReason(d.reason)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-xs">
                        {fmtLatency(d.predicted_latency_ms)}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-xs">
                        {fmtCriticality(d.patient_criticality_score)}
                      </td>
                    </tr>
                    {selected === i && (
                      <tr style={{ background: 'rgba(37,99,235,0.04)', borderColor: 'var(--border)' }}
                        className="border-b">
                        <td colSpan={6} className="px-4 py-4">
                          <div className="text-xs space-y-1" style={{ color: 'var(--muted)' }}>
                            <p><span className="font-semibold" style={{ color: 'var(--text)' }}>Decision trace:</span></p>
                            <p>Device: <code>{d.device_id}</code> · Criticality: <strong>{d.patient_criticality_score.toFixed(1)}/10</strong></p>
                            <p>Predicted latency: <strong>{fmtLatency(d.predicted_latency_ms)}</strong></p>
                            <p>Veto checks:
                              {d.patient_criticality_score >= 9
                                ? <span style={{ color: 'var(--emergency)' }}> Emergency override FIRED (≥ 9.0)</span>
                                : <span style={{ color: 'var(--ok)' }}> Override not triggered</span>}
                              {d.predicted_latency_ms >= 300
                                ? <span style={{ color: 'var(--veto)' }}> · Network veto FIRED (≥ 300 ms)</span>
                                : <span style={{ color: 'var(--ok)' }}> · Network veto not triggered</span>}
                            </p>
                            <p>Final decision: <strong style={{ color: d.routing_decision === 'EDGE' ? 'var(--edge)' : 'var(--cloud)' }}>{d.routing_decision}</strong> via <em>{fmtReason(d.reason)}</em></p>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
