import React from 'react';

function fmtDollar(v) {
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}k`;
  return `$${Math.round(v)}`;
}

const SEGMENTS = [
  { key: 'living',     label: 'Core Living',  color: '#4fc3f7' },
  { key: 'healthcare', label: 'Healthcare',   color: '#f97316' },
  { key: 'tax',        label: 'Tax',          color: '#ef5350' },
];

export default function SpendingBreakdownBar({ rows, scenario }) {
  if (!scenario || !rows || rows.length === 0) return null;

  const retirementAge = scenario.retirement_age_you;
  const retirementRows = rows.filter(r => r.age_you >= retirementAge);
  if (retirementRows.length === 0) return null;

  const n = retirementRows.length;
  const avgTax = retirementRows.reduce((s, r) => s + (r.federal_tax || 0) + (r.state_tax || 0), 0) / n;
  const avgHc  = retirementRows.reduce((s, r) => s + (r.income_by_source?.healthcare_annual || 0), 0) / n;
  // Core living: use today's-dollar scenario figure as the reference baseline
  const avgLiving = scenario.annual_spending || 0;

  const values = { living: avgLiving, healthcare: avgHc, tax: avgTax };
  const total = avgLiving + avgHc + avgTax;
  if (total === 0) return null;

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="section-title" style={{ marginBottom: 12 }}>Spending Breakdown</div>
      <div style={{ display: 'flex', borderRadius: 6, overflow: 'hidden', height: 28, marginBottom: 12 }}>
        {SEGMENTS.map(seg => {
          const pct = (values[seg.key] / total) * 100;
          if (pct < 1) return null;
          return (
            <div key={seg.key} style={{
              width: `${pct}%`, background: seg.color,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 11, fontWeight: 700, color: '#fff',
              overflow: 'hidden', whiteSpace: 'nowrap',
            }}>
              {pct > 8 ? `${pct.toFixed(0)}%` : ''}
            </div>
          );
        })}
      </div>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        {SEGMENTS.map(seg => (
          <div key={seg.key} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
            <div style={{ width: 10, height: 10, borderRadius: 2, background: seg.color }} />
            <span style={{ color: '#94a3b8' }}>{seg.label}:</span>
            <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{fmtDollar(values[seg.key])}/yr</span>
          </div>
        ))}
      </div>
      <div style={{ fontSize: 11, color: '#475569', marginTop: 8 }}>
        Core living shown in today's dollars. HC and tax are inflation-adjusted averages across all retirement years.
      </div>
    </div>
  );
}
