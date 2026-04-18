import React, { useEffect, useState } from 'react';
import { getScenarios, runMonteCarlo, getMonteCarlo } from '../api/client.js';
import PercentileFanChart from '../components/PercentileFanChart.jsx';
import SensitivityChart from '../components/SensitivityChart.jsx';
import SSStrategyTable from '../components/SSStrategyTable.jsx';

const SIM_OPTIONS = [1000, 5000, 10000, 50000];

function fmtDollar(v) {
  if (v == null) return '—';
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}k`;
  return `$${v}`;
}

function survivalColor(pct) {
  if (pct >= 85) return '#81c784';
  if (pct >= 70) return '#ffb74d';
  return '#ef5350';
}

function MetricCard({ label, value, color }) {
  return (
    <div className="metric-card">
      <div className="metric-value" style={color ? { color } : {}}>{value}</div>
      <div className="metric-label">{label}</div>
    </div>
  );
}

export default function MonteCarloTab() {
  const [scenarios, setScenarios] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [mcResult, setMcResult] = useState(null);
  const [numSims, setNumSims] = useState(10000);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [mcLoading, setMcLoading] = useState(false);
  const [error, setError] = useState(null);
  const [runError, setRunError] = useState(null);

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
    setMcLoading(true);
    getMonteCarlo(selectedId)
      .then(setMcResult)
      .catch(() => setMcResult(null))
      .finally(() => setMcLoading(false));
  }, [selectedId]);

  async function handleRun() {
    if (!selectedId) return;
    setRunning(true);
    setRunError(null);
    try {
      const result = await runMonteCarlo(selectedId, numSims);
      setMcResult(result);
    } catch (err) {
      setRunError(err.message);
    } finally {
      setRunning(false);
    }
  }

  if (loading) return <div style={{ color: '#90a4ae' }}>Loading scenarios…</div>;
  if (error) return <div style={{ color: '#ef5350' }}>Error: {error}</div>;

  const selectedScenario = scenarios.find(s => s.id === selectedId);
  const survivalPct = mcResult?.survival_rate != null ? mcResult.survival_rate * 100 : null;

  // Extract last-year percentiles for the 3 metric cards
  const p50LastYear = mcResult?.percentile_50
    ? (() => {
        const years = Object.keys(mcResult.percentile_50).map(Number).sort((a, b) => a - b);
        return mcResult.percentile_50[years[years.length - 1]];
      })()
    : null;
  const p10LastYear = mcResult?.percentile_10
    ? (() => {
        const years = Object.keys(mcResult.percentile_10).map(Number).sort((a, b) => a - b);
        return mcResult.percentile_10[years[years.length - 1]];
      })()
    : null;
  const p90LastYear = mcResult?.percentile_90
    ? (() => {
        const years = Object.keys(mcResult.percentile_90).map(Number).sort((a, b) => a - b);
        return mcResult.percentile_90[years[years.length - 1]];
      })()
    : null;

  return (
    <div>
      {/* Scenario selector */}
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

      {/* Sim count selector + Run */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24 }}>
        <span style={{ color: '#90a4ae', fontSize: 12 }}>Simulations:</span>
        {SIM_OPTIONS.map(n => (
          <button key={n}
            onClick={() => setNumSims(n)}
            style={{
              background: numSims === n ? '#4fc3f7' : '#16213e',
              color: numSims === n ? '#0d1b2a' : '#e0e0e0',
              border: `1px solid ${numSims === n ? '#4fc3f7' : '#1e3a5f'}`,
              padding: '6px 12px',
              fontSize: 12,
            }}>
            {n >= 1000 ? `${n / 1000}k` : n}
          </button>
        ))}
        <button
          onClick={handleRun}
          disabled={running || !selectedId}
          style={{ background: running ? '#1e3a5f' : '#4fc3f7', minWidth: 100 }}>
          {running ? 'Running…' : 'Run'}
        </button>
        {runError && <span style={{ color: '#ef5350', fontSize: 12 }}>{runError}</span>}
      </div>

      {/* Large survival % */}
      {survivalPct != null && (
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{ fontSize: 72, fontWeight: 700, color: survivalColor(survivalPct), lineHeight: 1 }}>
            {survivalPct.toFixed(1)}%
          </div>
          <div style={{ color: '#90a4ae', fontSize: 14, marginTop: 6 }}>
            Portfolio Survival Rate ({(mcResult?.num_simulations ?? numSims).toLocaleString()} simulations)
          </div>
        </div>
      )}

      {mcLoading && <div style={{ color: '#90a4ae', marginBottom: 16 }}>Loading Monte Carlo results…</div>}

      {/* 3 metric cards */}
      {mcResult && (
        <div className="three-col" style={{ marginBottom: 24 }}>
          <MetricCard label="Median Portfolio (Final Year)" value={fmtDollar(p50LastYear)} color="#81c784" />
          <MetricCard label="10th Percentile (Final Year)" value={fmtDollar(p10LastYear)} color="#ef5350" />
          <MetricCard label="90th Percentile (Final Year)" value={fmtDollar(p90LastYear)} color="#4fc3f7" />
        </div>
      )}

      {/* Fan chart + Sensitivity side by side */}
      {mcResult && (
        <div className="two-col" style={{ alignItems: 'start', marginBottom: 24 }}>
          <div className="card">
            <div className="section-title">Portfolio Percentile Fan</div>
            <PercentileFanChart
              mcResult={mcResult}
              retirementAge={selectedScenario?.retirement_age_you}
              ssStartAge={selectedScenario?.ss_claim_age_you}
            />
          </div>
          <div className="card">
            <div className="section-title">Sensitivity Analysis</div>
            <SensitivityChart sensitivity={mcResult?.sensitivity} />
          </div>
        </div>
      )}

      {/* SS Strategy Table */}
      {selectedScenario && (
        <SSStrategyTable scenario={selectedScenario} />
      )}
    </div>
  );
}
