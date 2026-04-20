import React, { useState, useMemo } from 'react';

const src = (r, key) => (r.income_by_source?.[key] || 0);

const INCOME_SOURCES = [
  { key: 'ss', label: 'Social Security', compute: r => src(r, 'ss_you') + src(r, 'ss_spouse') },
  { key: '401k_withdrawal', label: '401(k)', compute: r => src(r, '401k_withdrawal') },
  { key: 'roth_withdrawal', label: 'Roth', compute: r => src(r, 'roth_withdrawal') },
  { key: 'brokerage_withdrawal', label: 'Brokerage', compute: r => src(r, 'brokerage_withdrawal') },
  { key: 'nqdc', label: 'NQDC', compute: r => src(r, 'nqdc') },
  { key: 'pension', label: 'Pension', compute: r => src(r, 'pension') },
  { key: 'rental', label: 'Rental', compute: r => src(r, 'rental') },
  { key: 'rmd', label: 'RMD', compute: r => src(r, 'rmd') },
];

function fmtDollar(v) {
  if (v == null || v === 0) return '—';
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}k`;
  return `$${Math.round(v)}`;
}

function rateColor(rate) {
  if (rate < 0.12) return '#81c784';
  if (rate < 0.20) return '#ffb74d';
  return '#ef5350';
}

function avg(arr, fn) {
  if (!arr.length) return 0;
  return arr.reduce((sum, r) => sum + fn(r), 0) / arr.length;
}

function PhaseCard({ title, rows }) {
  const [open, setOpen] = useState(true);

  const avgFederal = avg(rows, r => r.federal_tax || 0);
  const avgState = avg(rows, r => r.state_tax || 0);
  const avgEffRate = avg(rows, r => r.effective_rate || 0);

  const notes = useMemo(() => {
    const seen = new Set();
    const result = [];
    for (const r of rows) {
      const rowNotes = r.withdrawal_notes || [];
      for (const n of rowNotes) {
        if (!seen.has(n)) { seen.add(n); result.push(n); }
      }
    }
    return result;
  }, [rows]);

  return (
    <div className="card" style={{ marginBottom: 12 }}>
      <div
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
        onClick={() => setOpen(o => !o)}
      >
        <div style={{ fontWeight: 600, color: '#e0e0e0', fontSize: 13 }}>{title}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ color: rateColor(avgEffRate), fontWeight: 700, fontSize: 14 }}>
            {(avgEffRate * 100).toFixed(1)}% eff
          </span>
          <span style={{ color: '#90a4ae', fontSize: 14 }}>{open ? '▲' : '▼'}</span>
        </div>
      </div>

      {open && rows.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div className="two-col" style={{ marginBottom: 12 }}>
            <div>
              <div style={{ color: '#90a4ae', fontSize: 11, marginBottom: 4 }}>AVG FEDERAL TAX</div>
              <div style={{ color: '#e0e0e0', fontWeight: 600 }}>{fmtDollar(avgFederal)}</div>
            </div>
            <div>
              <div style={{ color: '#90a4ae', fontSize: 11, marginBottom: 4 }}>AVG DE STATE TAX</div>
              <div style={{ color: '#e0e0e0', fontWeight: 600 }}>{fmtDollar(avgState)}</div>
            </div>
          </div>

          <div style={{ marginBottom: 10 }}>
            <div style={{ color: '#90a4ae', fontSize: 11, marginBottom: 6 }}>AVG INCOME BY SOURCE</div>
            {INCOME_SOURCES.map(s => {
              const val = avg(rows, s.compute);
              if (val < 1) return null;
              return (
                <div key={s.key} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 3 }}>
                  <span style={{ color: '#90a4ae' }}>{s.label}</span>
                  <span style={{ color: '#e0e0e0' }}>{fmtDollar(val)}</span>
                </div>
              );
            })}
          </div>

          {notes.length > 0 && (
            <div>
              <div style={{ color: '#90a4ae', fontSize: 11, marginBottom: 6 }}>OPTIMIZER NOTES</div>
              {notes.map((note, i) => (
                <div key={i} style={{
                  fontSize: 11, color: '#4fc3f7', background: '#0d1b2a',
                  borderRadius: 4, padding: '3px 8px', marginBottom: 3,
                  border: '1px solid #1e3a5f',
                }}>
                  {note}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {open && rows.length === 0 && (
        <div style={{ color: '#90a4ae', fontSize: 12, marginTop: 8 }}>No data for this phase.</div>
      )}
    </div>
  );
}

export default function TaxSummaryPanel({ rows, retirementAge, ssStartAge }) {
  if (!rows || rows.length === 0) {
    return (
      <div className="card" style={{ color: '#90a4ae', textAlign: 'center', padding: 32, fontSize: 13 }}>
        Run a projection to see tax summary.
      </div>
    );
  }

  const preSs = rows.filter(r => r.age_you != null && r.age_you >= (retirementAge || 0) && r.age_you < (ssStartAge || 999));
  const postSsPreRmd = rows.filter(r => r.age_you != null && r.age_you >= (ssStartAge || 0) && r.age_you < 73);
  const postRmd = rows.filter(r => r.age_you != null && r.age_you >= 73);

  return (
    <div>
      <h3 style={{ color: '#4fc3f7', fontSize: 14, marginBottom: 12 }}>Tax Summary by Phase</h3>
      <PhaseCard
        title={`Pre-SS (Age ${retirementAge ?? '?'}–${(ssStartAge ?? 1) - 1})`}
        rows={preSs}
      />
      <PhaseCard
        title={`Post-SS / Pre-RMD (Age ${ssStartAge ?? '?'}–72)`}
        rows={postSsPreRmd}
      />
      <PhaseCard
        title="Post-RMD (Age 73+)"
        rows={postRmd}
      />
    </div>
  );
}
