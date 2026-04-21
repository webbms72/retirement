import React, { useState, useEffect } from 'react';

function fmtFull(v) {
  return v != null ? `$${Math.round(v).toLocaleString()}` : '$0';
}

const STEP_CONFIG = {
  healthcare:      { color: '#f97316' },
  rmd:             { color: '#7c3aed' },
  hsa:             { color: '#0d9488' },
  brokerage:       { color: '#0369a1' },
  roth_conversion: { color: '#047857' },
  k401:            { color: '#92400e' },
  roth_ira:        { color: '#059669' },
};

function findNote(notes, prefix) {
  return (notes || []).find(n => n.startsWith(prefix)) || '';
}

function buildPlaybookSteps(yearData) {
  const src = yearData.income_by_source || {};
  const notes = yearData.withdrawal_notes || [];
  const steps = [];

  if (yearData.age_you < 65 && src.healthcare_annual > 0) {
    steps.push({
      type: 'healthcare',
      amount: src.healthcare_annual,
      text: `Budget ${fmtFull(src.healthcare_annual)} for health insurance (Jan–Dec)`,
      reason: 'Pre-Medicare coverage — pay premiums from your checking/savings account',
    });
  }
  if (src.rmd > 0) {
    steps.push({
      type: 'rmd',
      amount: src.rmd,
      text: `Take ${fmtFull(src.rmd)} RMD from your 401(k) by Dec 31`,
      reason: findNote(notes, 'RMD:') || 'Required Minimum Distribution — mandatory by IRS',
    });
  }
  if (src.hsa_withdrawal > 0) {
    steps.push({
      type: 'hsa',
      amount: src.hsa_withdrawal,
      text: `Draw ${fmtFull(src.hsa_withdrawal)} from HSA for medical expenses`,
      reason: findNote(notes, 'HSA:') || 'Qualified medical expense reimbursement — tax-free',
    });
  }
  if (src.brokerage_withdrawal > 0) {
    steps.push({
      type: 'brokerage',
      amount: src.brokerage_withdrawal,
      text: `Draw ${fmtFull(src.brokerage_withdrawal)} from Brokerage`,
      reason: findNote(notes, 'Brokerage:') || 'Long-term capital gains rate applies to growth',
    });
  }
  if (src.roth_conversion > 0) {
    steps.push({
      type: 'roth_conversion',
      amount: src.roth_conversion,
      text: `Convert ${fmtFull(src.roth_conversion)} from 401(k) to Roth IRA`,
      reason: findNote(notes, 'Roth conversion:') || 'Reduces future RMDs — grows tax-free',
    });
  }
  if (src['401k_withdrawal'] > 0) {
    steps.push({
      type: 'k401',
      amount: src['401k_withdrawal'],
      text: `Draw ${fmtFull(src['401k_withdrawal'])} from 401(k)`,
      reason: findNote(notes, '401k:') || 'Ordinary income — taxed at your marginal rate',
    });
  }
  if (src.roth_withdrawal > 0) {
    steps.push({
      type: 'roth_ira',
      amount: src.roth_withdrawal,
      text: `Draw ${fmtFull(src.roth_withdrawal)} from Roth IRA (tax-free)`,
      reason: findNote(notes, 'Roth IRA:') || 'Qualified distributions are completely tax-free',
    });
  }
  return steps;
}

function StepText({ text, amount }) {
  const amountStr = fmtFull(amount);
  const idx = text.indexOf(amountStr);
  if (idx === -1) return <span>{text}</span>;
  return (
    <>
      <span>{text.slice(0, idx)}</span>
      <strong style={{ color: '#f1f5f9' }}>{amountStr}</strong>
      <span>{text.slice(idx + amountStr.length)}</span>
    </>
  );
}

function PlaybookYear({ yearData }) {
  const steps = buildPlaybookSteps(yearData);
  const totalTax = (yearData.federal_tax || 0) + (yearData.state_tax || 0);

  if (steps.length === 0) {
    return (
      <div style={{ color: '#64748b', fontSize: 13, padding: '12px 0' }}>
        No portfolio withdrawals needed — guaranteed income covers all spending.
      </div>
    );
  }

  return (
    <div>
      <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
        {steps.map((step, i) => {
          const cfg = STEP_CONFIG[step.type] || { color: '#64748b' };
          return (
            <li key={i} style={{
              display: 'flex', alignItems: 'flex-start', gap: 10,
              padding: '9px 0', borderBottom: '1px solid #1e2535', fontSize: 13,
            }}>
              <div style={{
                width: 22, height: 22, borderRadius: '50%',
                background: cfg.color, color: '#fff',
                fontSize: 11, fontWeight: 700, flexShrink: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                marginTop: 1,
              }}>{i + 1}</div>
              <div style={{ color: '#cbd5e1', lineHeight: 1.5 }}>
                <StepText text={step.text} amount={step.amount} />
                <span style={{ color: '#64748b', fontSize: 12, display: 'block' }}>{step.reason}</span>
              </div>
            </li>
          );
        })}
      </ul>
      {totalTax > 0 && (
        <div style={{
          marginTop: 12, padding: '10px 14px',
          background: '#1a1a2e', borderRadius: 8,
          fontSize: 12, color: '#94a3b8',
          borderLeft: '3px solid #334155',
        }}>
          <strong style={{ color: '#f1f5f9' }}>Estimated tax: {fmtFull(totalTax)}</strong>
          {` (federal ${fmtFull(yearData.federal_tax)} + state ${fmtFull(yearData.state_tax)}) — consider quarterly estimated payments.`}
        </div>
      )}
    </div>
  );
}

function renderPrintContent(scope, retirementRows, selectedRow, scenarioName) {
  if (scope === 'This year') {
    return (
      <div>
        <h1 style={{ fontSize: 16 }}>{scenarioName} — {selectedRow.year} (Age {selectedRow.age_you}) Checklist</h1>
        <PlaybookYear yearData={selectedRow} />
      </div>
    );
  }
  if (scope === 'Full plan') {
    return (
      <div>
        <h1 style={{ fontSize: 16 }}>{scenarioName} — Full Withdrawal Plan</h1>
        {retirementRows.map(r => (
          <div key={r.year} style={{ pageBreakBefore: 'always' }}>
            <h2 style={{ fontSize: 14 }}>{r.year} (Age {r.age_you})</h2>
            <PlaybookYear yearData={r} />
          </div>
        ))}
      </div>
    );
  }
  // Phase summary
  const ssStartAge = retirementRows.find(r => (r.income_by_source?.ss_you || 0) > 0)?.age_you;
  const phases = [
    { label: 'Pre-Social Security', rows: retirementRows.filter(r => !ssStartAge || r.age_you < ssStartAge) },
    { label: 'Post-SS / Pre-RMD', rows: retirementRows.filter(r => ssStartAge && r.age_you >= ssStartAge && r.age_you < 73) },
    { label: 'RMD Phase', rows: retirementRows.filter(r => r.age_you >= 73) },
  ].filter(p => p.rows.length > 0);

  return (
    <div>
      <h1 style={{ fontSize: 16 }}>{scenarioName} — Phase Withdrawal Summary</h1>
      {phases.map(p => (
        <div key={p.label} style={{ pageBreakBefore: 'always' }}>
          <h2 style={{ fontSize: 14 }}>{p.label} ({p.rows[0].year}–{p.rows[p.rows.length - 1].year})</h2>
          <PlaybookYear yearData={p.rows[0]} />
          <p style={{ color: '#64748b', fontSize: 11 }}>Strategy applies across all years in this phase — amounts are representative of year {p.rows[0].year}.</p>
        </div>
      ))}
    </div>
  );
}

const EXPORT_SCOPES = ['This year', 'Full plan', 'Phase summary'];

export default function WithdrawalPlaybook({ rows, retirementAge, scenarioName }) {
  const [open, setOpen] = useState(true);
  const [exportScope, setExportScope] = useState('This year');

  const retirementRows = rows.filter(r => r.age_you >= retirementAge);
  const defaultYear = retirementRows[0]?.year ?? null;
  const [selectedYear, setSelectedYear] = useState(defaultYear);

  useEffect(() => {
    if (defaultYear != null) setSelectedYear(defaultYear);
  }, [defaultYear]);

  if (retirementRows.length === 0) return null;

  const selectedRow = retirementRows.find(r => r.year === selectedYear) || retirementRows[0];

  function handleExport() {
    const printEl = document.getElementById('__playbook_print_target__');
    if (!printEl) return;
    const style = document.createElement('style');
    style.id = '__playbook_print_style__';
    style.textContent = [
      '@media print {',
      '  body > * { display: none !important; }',
      '  #__playbook_print_target__ {',
      '    display: block !important; position: fixed; top: 0; left: 0;',
      '    width: 100%; background: white; color: black; padding: 24px;',
      '    font-family: -apple-system, sans-serif; font-size: 12px;',
      '  }',
      '}',
    ].join('\n');
    document.head.appendChild(style);
    window.addEventListener('afterprint', () => {
      document.head.removeChild(style);
    }, { once: true });
    window.print();
  }

  return (
    <div className="card" style={{ marginTop: 16 }}>
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: open ? 16 : 0 }}>
        <div style={{ flex: 1, fontWeight: 700, color: '#f1f5f9', fontSize: 15 }}>
          Withdrawal Playbook
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {EXPORT_SCOPES.map(scope => (
            <button key={scope} onClick={() => setExportScope(scope)} style={{
              fontSize: 11, padding: '3px 10px', borderRadius: 20,
              background: exportScope === scope ? '#1d4ed8' : '#1e2535',
              color: exportScope === scope ? '#fff' : '#64748b',
              border: `1px solid ${exportScope === scope ? '#1d4ed8' : '#334155'}`,
            }}>{scope}</button>
          ))}
        </div>
        <button onClick={handleExport} style={{
          fontSize: 12, padding: '4px 12px', background: '#1d4ed8',
          color: '#fff', borderRadius: 6, border: 'none', cursor: 'pointer',
        }}>Export PDF</button>
        <button onClick={() => setOpen(o => !o)} style={{
          background: 'transparent', border: 'none', color: '#64748b',
          fontSize: 16, cursor: 'pointer',
        }}>{open ? '▲' : '▼'}</button>
      </div>

      {/* Hidden print target */}
      <div id="__playbook_print_target__" style={{ display: 'none' }}>
        {renderPrintContent(exportScope, retirementRows, selectedRow, scenarioName)}
      </div>

      {open && (
        <>
          {/* Year selector strip */}
          <div style={{
            display: 'flex', gap: 6, flexWrap: 'wrap',
            marginBottom: 14, maxHeight: 88, overflowY: 'auto',
          }}>
            {retirementRows.map(r => (
              <button key={r.year} onClick={() => setSelectedYear(r.year)} style={{
                padding: '4px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                background: selectedYear === r.year ? '#1d4ed8' : '#1e3a5f',
                color: selectedYear === r.year ? '#fff' : '#7dd3fc',
                border: `1px solid ${selectedYear === r.year ? '#1d4ed8' : '#1e3a5f'}`,
              }}>
                {r.year} <span style={{ opacity: 0.7 }}>(Age {r.age_you})</span>
              </button>
            ))}
          </div>

          {/* Instruction list for selected year */}
          {selectedRow && <PlaybookYear yearData={selectedRow} />}
        </>
      )}
    </div>
  );
}
