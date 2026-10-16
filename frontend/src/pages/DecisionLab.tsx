// src/pages/DecisionLab.tsx
// Guide §3 Decision Lab — sliders for criticality, latency, cost.
// Shows each veto check step-by-step and the AHP maths.
// Calls POST /decision/explain (hypothetical — no DB write).
import { useState, useCallback } from 'react';
import { FlaskConical, CheckCircle2, XCircle, ArrowRight } from 'lucide-react';

const AHP_WEIGHTS = { latency: 0.6396, cost: 0.2583, criticality: 0.1021 };
const THRESHOLDS  = { emergency: 9.0, veto: 300.0 };

interface ExplainResult {
  criticality:      number;
  predictedLatency: number;
  costIndex:        number;
  emergencyFired:   boolean;
  vetoFired:        boolean;
  ahpEdge:          number | null;
  ahpCloud:         number | null;
  decision:         'EDGE' | 'CLOUD';
  reason:           string;
}

function explainLocally(c: number, l: number, cost: number): ExplainResult {
  const emergencyFired = c >= THRESHOLDS.emergency;
  const vetoFired      = l >= THRESHOLDS.veto;

  let decision: 'EDGE' | 'CLOUD' = 'CLOUD';
  let reason = 'ahp_decision';
  let ahpEdge: number | null = null;
  let ahpCloud: number | null = null;

  if (emergencyFired) { decision = 'EDGE'; reason = 'override_critical_patient'; }
  else if (vetoFired) { decision = 'EDGE'; reason = 'network_degradation_veto'; }
  else {
    // Simplified AHP: normalise each criterion [0-1], weight and sum
    const normLatency     = Math.min(l / 500, 1);
    const normCost        = Math.min(cost, 1);
    const normCriticality = Math.min(c / 10, 1);

    // Edge scores high when latency & criticality are high (local processing preferred)
    ahpEdge  = AHP_WEIGHTS.latency * normLatency
             + AHP_WEIGHTS.criticality * normCriticality
             + AHP_WEIGHTS.cost * (1 - normCost);
    ahpCloud = AHP_WEIGHTS.latency * (1 - normLatency)
             + AHP_WEIGHTS.criticality * (1 - normCriticality)
             + AHP_WEIGHTS.cost * normCost;

    decision = ahpEdge > ahpCloud ? 'EDGE' : 'CLOUD';
    reason = 'ahp_decision';
  }

  return { criticality: c, predictedLatency: l, costIndex: cost,
           emergencyFired, vetoFired, ahpEdge, ahpCloud, decision, reason };
}

function Slider({ label, value, min, max, step, unit, onChange }: {
  label: string; value: number; min: number; max: number; step: number;
  unit: string; onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-sm">
        <label className="font-medium" style={{ color: 'var(--text)' }}>{label}</label>
        <span className="font-mono font-bold" style={{ color: 'var(--cloud)' }}>
          {value.toFixed(1)} {unit}
        </span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(parseFloat(e.target.value))}
        className="w-full accent-[var(--cloud)]" />
      <div className="flex justify-between text-xs" style={{ color: 'var(--muted)' }}>
        <span>{min} {unit}</span><span>{max} {unit}</span>
      </div>
    </div>
  );
}

function VetoCheck({ label, threshold, value, unit, fired }: {
  label: string; threshold: number; value: number; unit: string; fired: boolean;
}) {
  return (
    <div className="flex items-center justify-between rounded-lg px-4 py-3 border text-sm"
      style={{
        borderColor: fired ? 'var(--emergency)' : 'var(--border)',
        background:  fired ? 'rgba(220,38,38,0.06)' : 'var(--page)',
      }}>
      <div>
        <p className="font-medium" style={{ color: 'var(--text)' }}>{label}</p>
        <p className="text-xs mt-0.5" style={{ color: 'var(--muted)' }}>
          Threshold: {threshold} {unit} · Current: <strong>{value.toFixed(1)} {unit}</strong>
        </p>
      </div>
      <div className="flex items-center gap-1.5" style={{ color: fired ? 'var(--emergency)' : 'var(--ok)' }}>
        {fired ? <XCircle size={18} /> : <CheckCircle2 size={18} />}
        <span className="font-semibold text-xs">{fired ? 'FIRED' : 'Clear'}</span>
      </div>
    </div>
  );
}

export default function DecisionLab() {
  const [crit,  setCrit]  = useState(5.0);
  const [lat,   setLat]   = useState(80.0);
  const [cost,  setCost]  = useState(0.4);

  const result = explainLocally(crit, lat, cost);

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2" style={{ color: 'var(--text)' }}>
          <FlaskConical size={24} style={{ color: 'var(--cloud)' }} />
          Decision Lab
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>
          Drag sliders to see how the AHP engine decides. No data is stored.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

        {/* Sliders */}
        <div className="rounded-xl border p-6 space-y-6"
          style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <h2 className="font-semibold text-sm" style={{ color: 'var(--text)' }}>Input Parameters</h2>
          <Slider label="Patient Criticality" value={crit} min={0} max={10} step={0.1} unit="/ 10" onChange={setCrit} />
          <Slider label="Predicted Network Latency" value={lat}  min={0} max={500} step={5} unit="ms" onChange={setLat} />
          <Slider label="Cloud Cost Index" value={cost} min={0} max={1} step={0.05} unit="" onChange={setCost} />
        </div>

        {/* Decision result */}
        <div className="rounded-xl border p-6 flex flex-col items-center justify-center"
          style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <p className="text-xs uppercase tracking-widest mb-2" style={{ color: 'var(--muted)' }}>Final Decision</p>
          <div className="text-5xl font-black mb-2"
            style={{ color: result.decision === 'EDGE' ? 'var(--edge)' : 'var(--cloud)' }}>
            {result.decision}
          </div>
          <div className="text-sm rounded-full px-4 py-1.5 font-medium mt-1"
            style={{
              background: result.reason === 'override_critical_patient' ? 'rgba(220,38,38,0.1)'
                        : result.reason === 'network_degradation_veto'  ? 'rgba(180,83,9,0.1)'
                        : 'rgba(37,99,235,0.1)',
              color: result.reason === 'override_critical_patient' ? 'var(--emergency)'
                   : result.reason === 'network_degradation_veto'  ? 'var(--veto)'
                   : 'var(--cloud)',
            }}>
            {result.reason === 'override_critical_patient' ? 'Emergency Override'
           : result.reason === 'network_degradation_veto'  ? 'Network Degradation Veto'
           : 'AHP Decision'}
          </div>
        </div>
      </div>

      {/* Step-by-step trace */}
      <div className="rounded-xl border p-6 space-y-4"
        style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
        <h2 className="font-semibold text-sm" style={{ color: 'var(--text)' }}>Step-by-Step Decision Trace</h2>

        {/* Veto checks */}
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--muted)' }}>
            Step 1 — Veto Checks
          </p>
          <VetoCheck label="Emergency Override" threshold={9.0}   value={crit} unit="/ 10" fired={result.emergencyFired} />
          <VetoCheck label="Network Veto"       threshold={300.0} value={lat}  unit="ms"   fired={result.vetoFired} />
        </div>

        {/* AHP maths (shown only when no veto) */}
        {!result.emergencyFired && !result.vetoFired && result.ahpEdge != null && (
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide mt-2" style={{ color: 'var(--muted)' }}>
              Step 2 — AHP Scoring (weights: latency 0.6396 · cost 0.2583 · criticality 0.1021)
            </p>
            <div className="grid grid-cols-2 gap-4 text-sm">
              {(['EDGE', 'CLOUD'] as const).map(dec => {
                const score = dec === 'EDGE' ? result.ahpEdge! : result.ahpCloud!;
                const isWinner = result.decision === dec;
                return (
                  <div key={dec} className="rounded-lg p-4 border"
                    style={{
                      borderColor: isWinner ? (dec === 'EDGE' ? 'var(--edge)' : 'var(--cloud)') : 'var(--border)',
                      background:  isWinner ? (dec === 'EDGE' ? 'rgba(15,118,110,0.07)' : 'rgba(37,99,235,0.07)') : 'var(--page)',
                    }}>
                    <div className="flex justify-between">
                      <span className="font-bold" style={{ color: dec === 'EDGE' ? 'var(--edge)' : 'var(--cloud)' }}>
                        {dec}
                      </span>
                      {isWinner && <span className="text-xs" style={{ color: 'var(--ok)' }}>Winner ✓</span>}
                    </div>
                    <div className="text-2xl font-mono font-bold mt-1" style={{ color: 'var(--text)' }}>
                      {score.toFixed(4)}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Arrow to decision */}
        <div className="flex items-center gap-2 pt-2" style={{ color: 'var(--muted)' }}>
          <ArrowRight size={16} />
          <span className="text-sm">Routed to
            <strong style={{ color: result.decision === 'EDGE' ? 'var(--edge)' : 'var(--cloud)', marginLeft: 4 }}>
              {result.decision}
            </strong>
          </span>
        </div>
      </div>
    </div>
  );
}
