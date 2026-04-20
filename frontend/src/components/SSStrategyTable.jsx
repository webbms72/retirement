import React, { useEffect, useState } from 'react';
import { getProfiles, getSocialSecurity, getSsStrategies, updateScenario } from '../api/client.js';

function fmtDollar(v) {
  if (v == null) return '—';
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}k`;
  return `$${v}`;
}

export default function SSStrategyTable({ scenario }) {
  const [strategies, setStrategies] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expandedIdx, setExpandedIdx] = useState(null);
  const [applying, setApplying] = useState(null);
  const [applySuccess, setApplySuccess] = useState(null);
  const [hasSSData, setHasSSData] = useState(true);

  useEffect(() => {
    async function loadStrategies() {
      setLoading(true);
      setError(null);
      try {
        // Load profiles + their SS data to build query params
        const profiles = await getProfiles();
        const ssMap = {};
        for (const p of profiles) {
          try { ssMap[p.id] = await getSocialSecurity(p.id); }
          catch { ssMap[p.id] = null; }
        }

        const youProfile = profiles.find(p => p.role === 'primary') || profiles[0];
        const spouseProfile = profiles.find(p => p.role === 'spouse') || profiles[1];
        const youSS = youProfile ? ssMap[youProfile.id] : null;
        const spouseSS = spouseProfile ? ssMap[spouseProfile.id] : null;

        // Check if there's meaningful SS data
        const hasSS = (youSS?.benefit_at_fra > 0) || (spouseSS?.benefit_at_fra > 0);
        setHasSSData(hasSS);

        if (!hasSS) {
          setLoading(false);
          return;
        }

        // Build params matching backend query param names exactly
        const calcAge = dob => dob ? new Date().getFullYear() - parseInt(dob.slice(0, 4), 10) : 54;

        const params = {
          benefit_62_you:   youSS?.benefit_at_62  ?? 0,
          benefit_fra_you:  youSS?.benefit_at_fra  ?? 0,
          benefit_70_you:   youSS?.benefit_at_70   ?? 0,
          fra_age_you:      youSS?.fra_age         ?? 67,
          benefit_62_spouse:  spouseSS?.benefit_at_62  ?? 0,
          benefit_fra_spouse: spouseSS?.benefit_at_fra  ?? 0,
          benefit_70_spouse:  spouseSS?.benefit_at_70   ?? 0,
          fra_age_spouse:     spouseSS?.fra_age         ?? 67,
          life_exp_you:     youProfile?.life_expectancy_age    ?? 88,
          life_exp_spouse:  spouseProfile?.life_expectancy_age ?? 90,
          current_age_you:   calcAge(youProfile?.dob),
          current_age_spouse: calcAge(spouseProfile?.dob),
          survivor_benefit_pct: youSS?.survivor_benefit_pct ?? 1.0,
        };

        const result = await getSsStrategies(params);
        setStrategies(Array.isArray(result) ? result : result.strategies ?? []);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    loadStrategies();
  }, []);

  async function handleApply(strategy, idx) {
    if (!scenario?.id) return;
    setApplying(idx);
    try {
      await updateScenario(scenario.id, {
        ...scenario,
        ss_claim_age_you: strategy.claim_age_you,
        ss_claim_age_spouse: strategy.claim_age_spouse,
      });
      setApplySuccess(idx);
      setTimeout(() => setApplySuccess(null), 2500);
    } catch (err) {
      console.error('Failed to apply SS strategy:', err);
    } finally {
      setApplying(null);
    }
  }

  if (!hasSSData) {
    return (
      <div className="card" style={{ marginTop: 24 }}>
        <div className="section-title">SS Claim Strategy Optimizer</div>
        <div style={{ color: '#90a4ae', fontSize: 13, padding: '12px 0' }}>
          Enter Social Security benefit amounts in the Profile tab to see optimized claim strategies.
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="card" style={{ marginTop: 24 }}>
        <div className="section-title">SS Claim Strategy Optimizer</div>
        <div style={{ color: '#90a4ae' }}>Loading strategies…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card" style={{ marginTop: 24 }}>
        <div className="section-title">SS Claim Strategy Optimizer</div>
        <div style={{ color: '#ef5350', fontSize: 13 }}>Error loading strategies: {error}</div>
      </div>
    );
  }

  if (strategies.length === 0) {
    return (
      <div className="card" style={{ marginTop: 24 }}>
        <div className="section-title">SS Claim Strategy Optimizer</div>
        <div style={{ color: '#90a4ae', fontSize: 13 }}>No strategies available.</div>
      </div>
    );
  }

  const topStrategy = strategies[0];

  return (
    <div className="card" style={{ marginTop: 24 }}>
      <div className="section-title">SS Claim Strategy Optimizer</div>
      <table>
        <thead>
          <tr>
            <th>Rank</th>
            <th>Your Age</th>
            <th>Spouse Age</th>
            <th>Lifetime Benefit</th>
            <th>vs Recommended</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {strategies.map((s, idx) => {
            const isTop = idx === 0;
            const delta = s.lifetime_benefit - topStrategy.lifetime_benefit;
            const isExpanded = expandedIdx === idx;

            return (
              <React.Fragment key={idx}>
                <tr
                  style={{
                    background: isTop ? '#0a2a0a' : 'transparent',
                    cursor: 'pointer',
                  }}
                  onClick={() => setExpandedIdx(isExpanded ? null : idx)}
                >
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      {isTop && (
                        <span style={{
                          background: '#81c78433', color: '#81c784',
                          border: '1px solid #81c78455', borderRadius: 4,
                          fontSize: 12, padding: '1px 6px', fontWeight: 700,
                        }}>★</span>
                      )}
                      <span style={{ color: isTop ? '#81c784' : '#e0e0e0' }}>#{idx + 1}</span>
                    </div>
                  </td>
                  <td style={{ color: isTop ? '#81c784' : '#e0e0e0' }}>
                    Age {s.claim_age_you ?? '—'}
                  </td>
                  <td style={{ color: isTop ? '#81c784' : '#e0e0e0' }}>
                    {s.claim_age_spouse != null ? `Age ${s.claim_age_spouse}` : '—'}
                  </td>
                  <td style={{ color: isTop ? '#81c784' : '#e0e0e0', fontWeight: isTop ? 700 : 400 }}>
                    {fmtDollar(s.lifetime_benefit)}
                  </td>
                  <td>
                    {idx === 0 ? (
                      <span style={{ color: '#81c784', fontSize: 12 }}>Recommended</span>
                    ) : (
                      <span style={{ color: '#ef5350', fontSize: 12 }}>
                        {fmtDollar(delta)}
                      </span>
                    )}
                  </td>
                  <td>
                    <button
                      className="secondary"
                      style={{ fontSize: 11, padding: '4px 10px' }}
                      onClick={e => { e.stopPropagation(); handleApply(s, idx); }}
                      disabled={applying === idx}
                    >
                      {applySuccess === idx ? '✓ Applied' : applying === idx ? 'Applying…' : 'Apply'}
                    </button>
                  </td>
                </tr>
                {isExpanded && s.notes && (
                  <tr>
                    <td colSpan={6} style={{ padding: '8px 16px', background: '#0d1b2a' }}>
                      <div style={{ color: '#90a4ae', fontSize: 12 }}>
                        {Array.isArray(s.notes)
                          ? s.notes.map((n, i) => <div key={i} style={{ marginBottom: 2 }}>• {n}</div>)
                          : <div>{s.notes}</div>
                        }
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
