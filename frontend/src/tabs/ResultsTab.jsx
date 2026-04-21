import React, { useEffect, useState } from 'react';
import { getScenarios, getProjection } from '../api/client.js';
import PortfolioChart from '../components/PortfolioChart.jsx';
import IncomeBreakdownChart from '../components/IncomeBreakdownChart.jsx';
import TaxSummaryPanel from '../components/TaxSummaryPanel.jsx';
import WithdrawalPlaybook from '../components/WithdrawalPlaybook.jsx';
import HealthcareCostPanel from '../components/HealthcareCostPanel.jsx';
import SpendingBreakdownBar from '../components/SpendingBreakdownBar.jsx';

function fmtDollar(v) {
  if (v == null) return '—';
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}k`;
  return `$${v}`;
}

function MetricCard({ label, value, color }) {
  return (
    <div className="metric-card">
      <div className="metric-value" style={color ? { color } : {}}>{value}</div>
      <div className="metric-label">{label}</div>
    </div>
  );
}

export default function ResultsTab() {
  const [scenarios, setScenarios] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [projection, setProjection] = useState(null);
  const [loading, setLoading] = useState(true);
  const [projLoading, setProjLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    getScenarios()
      .then(scens => {
        setScenarios(scens);
        if (scens.length > 0) setSelectedId(scens[0].id);
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setProjLoading(true);
    getProjection(selectedId)
      .then(setProjection)
      .catch(() => setProjection(null))
      .finally(() => setProjLoading(false));
  }, [selectedId]);

  if (loading) return <div style={{ color: '#90a4ae' }}>Loading scenarios…</div>;
  if (error) return <div style={{ color: '#ef5350' }}>Error: {error}</div>;

  const selectedScenario = scenarios.find(s => s.id === selectedId);
  const rows = projection?.years ?? [];

  // Compute key metrics
  const retirementRow = rows.find(r => r.age_you === selectedScenario?.retirement_age_you);
  const portfolioAtRetirement = retirementRow?.portfolio_balance ?? null;

  const depletionRow = rows.find(r => r.portfolio_balance <= 0);
  const depletionAge = depletionRow ? depletionRow.age_you : null;

  const taxRows = rows.filter(r => r.effective_rate != null);
  const avgEffectiveRate = taxRows.length > 0
    ? taxRows.reduce((sum, r) => sum + (r.effective_rate || 0), 0) / taxRows.length
    : null;

  const hasMedicareGap =
    (selectedScenario?.healthcare_monthly_pre_medicare || 0) > 0 &&
    (selectedScenario?.retirement_age_you ?? 99) < 65;
  const medicareStartAge = hasMedicareGap ? 65 : null;

  // hcGapYears: use healthcare_annual > 0 as truth source — backend correctly handles spouse Medicare age
  const hcGapYears = rows.filter(
    r => r.age_you >= (selectedScenario?.retirement_age_you ?? 99) &&
         (r.income_by_source?.healthcare_annual || 0) > 0
  );
  const hcStartAge = hcGapYears[0]?.age_you ?? null;

  // Sum HC cost only over the pre-Medicare gap period
  const preMedicareHcCost = hcGapYears.reduce(
    (sum, r) => sum + (r.income_by_source?.healthcare_annual || 0), 0
  );

  return (
    <div>
      {/* Scenario selector chips */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 20 }}>
        {scenarios.map(s => (
          <button key={s.id}
            onClick={() => setSelectedId(s.id)}
            style={{
              background: selectedId === s.id ? '#4fc3f7' : '#16213e',
              color: selectedId === s.id ? '#0d1b2a' : '#e0e0e0',
              border: `1px solid ${selectedId === s.id ? '#4fc3f7' : '#1e3a5f'}`,
              fontSize: 13,
            }}>
            {s.name}
          </button>
        ))}
        {scenarios.length === 0 && (
          <span style={{ color: '#90a4ae', fontSize: 13 }}>No scenarios. Create one in the Scenarios tab.</span>
        )}
      </div>

      {projLoading && <div style={{ color: '#90a4ae', marginBottom: 16 }}>Loading projection…</div>}

      {/* 4-metric row */}
      <div className="four-col" style={{ marginBottom: 24 }}>
        <MetricCard label="Portfolio at Retirement" value={fmtDollar(portfolioAtRetirement)} />
        <MetricCard
          label="Depletion Age"
          value={depletionAge ? `Age ${depletionAge}` : 'Never ✓'}
          color={depletionAge ? '#ef5350' : '#81c784'}
        />
        <MetricCard
          label="Avg Effective Tax Rate"
          value={avgEffectiveRate != null ? `${(avgEffectiveRate * 100).toFixed(1)}%` : '—'}
        />
        <MetricCard
          label={hcStartAge != null ? `Pre-Medicare HC Cost · Ages ${hcStartAge}–65` : 'Pre-Medicare HC Cost'}
          value={preMedicareHcCost > 0 ? fmtDollar(preMedicareHcCost) : '—'}
          color="#fcd34d"
        />
      </div>

      {/* Charts + panels */}
      <div className="two-col" style={{ alignItems: 'start' }}>
        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="section-title">Portfolio Balance</div>
            <PortfolioChart
              data={rows}
              retirementAge={selectedScenario?.retirement_age_you}
              ssStartAge={selectedScenario?.ss_claim_age_you}
              medicareStartAge={medicareStartAge}
            />
          </div>
          <div className="card">
            <div className="section-title">Income Breakdown (5-yr avg)</div>
            <IncomeBreakdownChart data={rows} />
          </div>
        </div>
        <div>
          <HealthcareCostPanel rows={rows} scenario={selectedScenario} />
          <SpendingBreakdownBar rows={rows} scenario={selectedScenario} />
          <TaxSummaryPanel
            rows={rows}
            retirementAge={selectedScenario?.retirement_age_you}
            ssStartAge={selectedScenario?.ss_claim_age_you}
          />
        </div>
      </div>

      {/* Withdrawal Playbook */}
      {rows.length > 0 && selectedScenario && (
        <WithdrawalPlaybook
          rows={rows}
          retirementAge={selectedScenario.retirement_age_you}
          scenarioName={selectedScenario.name}
        />
      )}
    </div>
  );
}
