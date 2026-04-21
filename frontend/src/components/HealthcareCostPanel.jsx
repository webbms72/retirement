import React from 'react';

function fmtDollar(v) {
  if (v == null) return '—';
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}k`;
  return `$${Math.round(v).toLocaleString()}`;
}

export default function HealthcareCostPanel({ rows, scenario }) {
  if (!scenario || !rows || rows.length === 0) return null;

  const monthlyPremium = scenario.healthcare_monthly_pre_medicare || 0;
  if (monthlyPremium === 0) return null;

  const annualToday = monthlyPremium * 12;
  const inflationRate = scenario.inflation_rate || 0.025;
  const currentAge = rows[0]?.age_you ?? 0;
  const retirementAge = scenario.retirement_age_you;

  const yearsToMedicare = Math.max(0, 65 - currentAge);
  const annualAt65 = annualToday * Math.pow(1 + inflationRate, yearsToMedicare);

  const gapRows = rows.filter(r => r.age_you >= retirementAge && r.age_you < 65);
  const totalGap = gapRows.reduce(
    (sum, r) => sum + (r.income_by_source?.healthcare_annual || 0), 0
  );

  const avgAnnualSpending = gapRows.length > 0
    ? gapRows.reduce((s, r) => s + (r.income_by_source?.healthcare_annual || 0), 0) / gapRows.length
    : 0;
  const pctOfSpending = scenario.annual_spending > 0 && avgAnnualSpending > 0
    ? (avgAnnualSpending / scenario.annual_spending) * 100
    : 0;

  const medicareYear = new Date().getFullYear() + yearsToMedicare;

  const tableRows = [
    { label: "Annual cost (today's $)",       value: fmtDollar(annualToday) },
    { label: 'Annual cost (age 65, inflated)', value: fmtDollar(annualAt65) },
    { label: 'Total over gap period',          value: fmtDollar(totalGap) },
    { label: '% of avg annual spending',       value: pctOfSpending > 0 ? `${pctOfSpending.toFixed(1)}%` : '—' },
    { label: 'Medicare begins',                value: `${medicareYear} (age 65)` },
  ];

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="section-title" style={{ color: '#fcd34d', marginBottom: 12 }}>
        Pre-Medicare Healthcare
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <tbody>
          {tableRows.map(({ label, value }) => (
            <tr key={label} style={{ borderBottom: '1px solid #1e2535' }}>
              <td style={{ padding: '7px 0', color: '#94a3b8' }}>{label}</td>
              <td style={{ padding: '7px 0', color: '#f1f5f9', fontWeight: 600, textAlign: 'right' }}>{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
