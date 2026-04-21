import React, { useEffect, useState } from 'react';
import {
  getScenarios, createScenario, updateScenario, deleteScenario,
  duplicateScenario, runProjection, getProfiles,
} from '../api/client.js';

const DEFAULT_SCENARIO = {
  name: 'New Scenario',
  retirement_age_you: 60,
  retirement_age_spouse: 60,
  ss_claim_age_you: 67,
  ss_claim_age_spouse: 67,
  annual_spending: 120000,
  inflation_rate: 0.025,
  expected_return_stocks: 0.07,
  expected_return_bonds: 0.04,
  stock_allocation: 0.60,
  withdrawal_strategy: 'optimized',
  manual_withdrawal_order: [],
  roth_conversion_enabled: false,
  roth_conversion_target_bracket: '22%',
  healthcare_monthly_pre_medicare: 1500,
};

const WITHDRAWAL_ACCOUNT_TYPES = ['401k', 'roth_ira', 'brokerage', 'hsa', 'nqdc', 'pension'];
const ACCOUNT_LABELS = {
  '401k': '401(k)', roth_ira: 'Roth IRA', brokerage: 'Brokerage',
  hsa: 'HSA', nqdc: 'NQDC', pension: 'Pension',
};

function SliderField({ label, value, min, max, step = 1, onChange, suffix = '' }) {
  return (
    <div className="field">
      <label>{label}: {value}{suffix}</label>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(step < 1 ? parseFloat(e.target.value) : parseInt(e.target.value, 10))} />
      <div style={{ display: 'flex', justifyContent: 'space-between', color: '#90a4ae', fontSize: 11 }}>
        <span>{min}{suffix}</span><span>{max}{suffix}</span>
      </div>
    </div>
  );
}

function WithdrawalOrderEditor({ order, onChange }) {
  const types = order.length > 0 ? order : WITHDRAWAL_ACCOUNT_TYPES;

  function moveUp(idx) {
    if (idx === 0) return;
    const next = [...types];
    [next[idx - 1], next[idx]] = [next[idx], next[idx - 1]];
    onChange(next);
  }

  function moveDown(idx) {
    if (idx === types.length - 1) return;
    const next = [...types];
    [next[idx], next[idx + 1]] = [next[idx + 1], next[idx]];
    onChange(next);
  }

  return (
    <div>
      {types.map((type, idx) => (
        <div key={type} style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '6px 10px', marginBottom: 4,
          background: '#16213e', borderRadius: 6, border: '1px solid #1e3a5f',
        }}>
          <span style={{ flex: 1, fontSize: 13 }}>{idx + 1}. {ACCOUNT_LABELS[type] || type}</span>
          <button className="secondary" style={{ padding: '2px 8px', fontSize: 12 }}
            onClick={() => moveUp(idx)} disabled={idx === 0}>▲</button>
          <button className="secondary" style={{ padding: '2px 8px', fontSize: 12 }}
            onClick={() => moveDown(idx)} disabled={idx === types.length - 1}>▼</button>
        </div>
      ))}
    </div>
  );
}

// API stores rates as decimals (0.07); UI works in percentages (7.0).
function toDisplay(s) {
  return {
    ...s,
    expected_return_stocks: +(s.expected_return_stocks * 100).toFixed(2),
    expected_return_bonds: +(s.expected_return_bonds * 100).toFixed(2),
    inflation_rate: +(s.inflation_rate * 100).toFixed(2),
    stock_allocation: +(s.stock_allocation * 100).toFixed(1),
    manual_withdrawal_order: s.manual_withdrawal_order || [],
  };
}

function toApi(s) {
  return {
    ...s,
    expected_return_stocks: s.expected_return_stocks / 100,
    expected_return_bonds: s.expected_return_bonds / 100,
    inflation_rate: s.inflation_rate / 100,
    stock_allocation: s.stock_allocation / 100,
  };
}

function ScenarioEditor({ scenario, profiles, onSave, onRun, onDelete, onDuplicate, running }) {
  const [local, setLocal] = useState(() => toDisplay(scenario));
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    setLocal(toDisplay(scenario));
    setDirty(false);
  }, [scenario.id]);

  function update(patch) {
    setLocal(prev => ({ ...prev, ...patch }));
    setDirty(true);
  }

  async function handleSave() {
    await onSave(toApi(local));
    setDirty(false);
  }

  const youProfile = profiles.find(p => p.role === 'primary') || profiles[0];
  const spouseProfile = profiles.find(p => p.role === 'spouse') || profiles[1];

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <input
          type="text"
          value={local.name}
          onChange={e => update({ name: e.target.value })}
          style={{ fontSize: 16, fontWeight: 600, background: 'transparent', border: 'none', borderBottom: '1px solid #1e3a5f', borderRadius: 0, color: '#e0e0e0', padding: '4px 0', width: 240 }}
        />
        <div style={{ display: 'flex', gap: 8 }}>
          {dirty && <button onClick={handleSave} style={{ background: '#81c784', color: '#0d1b2a' }}>Save</button>}
          <button className="secondary" onClick={onDuplicate}>Duplicate</button>
          <button className="danger" onClick={onDelete}>Delete</button>
        </div>
      </div>

      <div className="two-col">
        <div>
          <div className="section-title">Retirement Ages</div>
          {youProfile && (
            <SliderField label={`${youProfile.name} retires`} value={local.retirement_age_you}
              min={52} max={70} onChange={v => update({ retirement_age_you: v })} />
          )}
          {spouseProfile && (
            <SliderField label={`${spouseProfile.name} retires`} value={local.retirement_age_spouse}
              min={52} max={70} onChange={v => update({ retirement_age_spouse: v })} />
          )}

          <div className="section-title" style={{ marginTop: 16 }}>Social Security Claim Ages</div>
          {youProfile && (
            <SliderField label={`${youProfile.name} claims SS`} value={local.ss_claim_age_you}
              min={62} max={70} onChange={v => update({ ss_claim_age_you: v })} />
          )}
          {spouseProfile && (
            <SliderField label={`${spouseProfile.name} claims SS`} value={local.ss_claim_age_spouse}
              min={62} max={70} onChange={v => update({ ss_claim_age_spouse: v })} />
          )}

          <div className="section-title" style={{ marginTop: 16 }}>Spending</div>
          <div className="field">
            <label>Annual Spending ($)</label>
            <input type="number" min={0} step={1000} value={local.annual_spending}
              onChange={e => update({ annual_spending: parseFloat(e.target.value) || 0 })} />
          </div>
          <SliderField label="Inflation Rate" value={local.inflation_rate}
            min={1} max={6} step={0.1} onChange={v => update({ inflation_rate: v })} suffix="%" />
        </div>

        <div>
          <div className="section-title">Return Assumptions</div>
          <SliderField label="Stock Return" value={local.expected_return_stocks}
            min={3} max={12} step={0.1} onChange={v => update({ expected_return_stocks: v })} suffix="%" />
          <SliderField label="Bond Return" value={local.expected_return_bonds}
            min={1} max={8} step={0.1} onChange={v => update({ expected_return_bonds: v })} suffix="%" />
          <SliderField label="Stock Allocation" value={local.stock_allocation}
            min={20} max={100} step={5} onChange={v => update({ stock_allocation: v })} suffix="%" />

          <div className="section-title" style={{ marginTop: 16 }}>Withdrawal Strategy</div>
          <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
            {['optimized', 'manual'].map(strategy => (
              <button key={strategy}
                style={{
                  background: local.withdrawal_strategy === strategy ? '#4fc3f7' : '#16213e',
                  color: local.withdrawal_strategy === strategy ? '#0d1b2a' : '#e0e0e0',
                  border: '1px solid #1e3a5f',
                }}
                onClick={() => update({ withdrawal_strategy: strategy })}>
                {strategy === 'optimized' ? 'Optimized' : 'Manual Order'}
              </button>
            ))}
          </div>
          {local.withdrawal_strategy === 'manual' && (
            <WithdrawalOrderEditor
              order={local.manual_withdrawal_order || []}
              onChange={order => update({ manual_withdrawal_order: order })}
            />
          )}

          <div className="section-title" style={{ marginTop: 16 }}>Advanced</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <input type="checkbox" id="roth-toggle" style={{ width: 'auto' }}
              checked={local.roth_conversion_enabled || false}
              onChange={e => update({ roth_conversion_enabled: e.target.checked })} />
            <label htmlFor="roth-toggle" style={{ margin: 0, textTransform: 'none', fontSize: 13 }}>
              Enable Roth Conversions
            </label>
          </div>
          {local.roth_conversion_enabled && (
            <div className="field">
              <label>Max Annual Roth Conversion ($)</label>
              <input type="number" min={0} step={1000}
                value={local.roth_conversion_annual_limit || 50000}
                onChange={e => update({ roth_conversion_annual_limit: parseFloat(e.target.value) || 0 })} />
            </div>
          )}
        </div>
      </div>

      <div style={{ marginTop: 20, display: 'flex', justifyContent: 'flex-end' }}>
        <button onClick={() => { if (dirty) handleSave().then(() => onRun(local.id)); else onRun(local.id); }}
          disabled={running}
          style={{ background: running ? '#1e3a5f' : '#4fc3f7', minWidth: 160 }}>
          {running ? 'Running…' : 'Run Projection'}
        </button>
      </div>
    </div>
  );
}

export default function ScenariosTab() {
  const [scenarios, setScenarios] = useState([]);
  const [profiles, setProfiles] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [running, setRunning] = useState(false);
  const [runStatus, setRunStatus] = useState(null);
  const [renamingId, setRenamingId] = useState(null);
  const [renameValue, setRenameValue] = useState('');

  useEffect(() => {
    async function load() {
      try {
        const [scens, profs] = await Promise.all([getScenarios(), getProfiles()]);
        setScenarios(scens);
        setProfiles(profs);
        if (scens.length > 0) setSelectedId(scens[0].id);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  async function handleCreate() {
    try {
      const created = await createScenario(DEFAULT_SCENARIO);
      setScenarios(prev => [...prev, created]);
      setSelectedId(created.id);
    } catch (err) { console.error('Create scenario failed:', err); }
  }

  async function handleSave(scenario) {
    try {
      const updated = await updateScenario(scenario.id, scenario);
      setScenarios(prev => prev.map(s => s.id === scenario.id ? { ...s, ...updated } : s));
    } catch (err) { console.error('Save scenario failed:', err); }
  }

  async function handleDelete(id) {
    if (!confirm('Delete this scenario?')) return;
    try {
      await deleteScenario(id);
      const remaining = scenarios.filter(s => s.id !== id);
      setScenarios(remaining);
      setSelectedId(remaining.length > 0 ? remaining[0].id : null);
    } catch (err) { console.error('Delete scenario failed:', err); }
  }

  async function handleDuplicate(id) {
    try {
      const duped = await duplicateScenario(id);
      setScenarios(prev => [...prev, duped]);
      setSelectedId(duped.id);
    } catch (err) { console.error('Duplicate scenario failed:', err); }
  }

  async function handleRun(id) {
    setRunning(true);
    setRunStatus(null);
    try {
      await runProjection(id);
      setRunStatus({ type: 'success', message: 'Projection complete. View in Results tab.' });
    } catch (err) {
      setRunStatus({ type: 'error', message: `Run failed: ${err.message}` });
    } finally {
      setRunning(false);
    }
  }

  async function handleRename(id) {
    const trimmed = renameValue.trim().slice(0, 60);
    if (!trimmed) { setRenamingId(null); return; }
    const scenario = scenarios.find(s => s.id === id);
    if (!scenario) { setRenamingId(null); return; }
    try {
      const updated = await updateScenario(id, { ...scenario, name: trimmed });
      setScenarios(prev => prev.map(s => s.id === id ? { ...s, name: updated.name } : s));
    } catch (err) {
      console.error('Rename failed:', err);
      setRunStatus({ type: 'error', message: `Rename failed: ${err.message}` });
    }
    setRenamingId(null);
  }

  if (loading) return <div style={{ color: '#90a4ae' }}>Loading scenarios…</div>;
  if (error) return <div style={{ color: '#ef5350' }}>Error: {error}</div>;

  const selectedScenario = scenarios.find(s => s.id === selectedId);

  return (
    <div className="two-col" style={{ alignItems: 'start' }}>
      {/* Left: scenario list */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h2 style={{ color: '#4fc3f7', fontSize: 16 }}>Scenarios</h2>
          <button className="secondary" onClick={handleCreate}>+ New</button>
        </div>
        {scenarios.length === 0 && (
          <div style={{ color: '#90a4ae', fontSize: 13 }}>No scenarios yet. Create one to get started.</div>
        )}
        {scenarios.map(s => (
          <div key={s.id}
            onClick={() => { if (renamingId !== s.id) setSelectedId(s.id); }}
            style={{
              padding: '10px 14px', marginBottom: 6, borderRadius: 8,
              border: `1px solid ${selectedId === s.id ? '#4fc3f7' : '#1e3a5f'}`,
              background: selectedId === s.id ? '#0f3460' : '#16213e',
              cursor: 'pointer', transition: 'border-color 0.15s',
            }}>
            {renamingId === s.id ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                onClick={e => e.stopPropagation()}>
                <input
                  autoFocus
                  value={renameValue}
                  maxLength={60}
                  onChange={e => setRenameValue(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter') handleRename(s.id);
                    if (e.key === 'Escape') setRenamingId(null);
                  }}
                  style={{
                    flex: 1, fontSize: 13, fontWeight: 600,
                    background: '#0d1b2a', border: '1px solid #4fc3f7',
                    borderRadius: 4, color: '#e0e0e0', padding: '2px 6px',
                  }}
                />
                <button onClick={() => handleRename(s.id)}
                  style={{ background: 'transparent', border: 'none', color: '#22c55e', cursor: 'pointer', fontSize: 14, padding: '0 2px' }}>✓</button>
                <button onClick={() => setRenamingId(null)}
                  style={{ background: 'transparent', border: 'none', color: '#f87171', cursor: 'pointer', fontSize: 14, padding: '0 2px' }}>✕</button>
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ flex: 1, fontWeight: 600, color: selectedId === s.id ? '#4fc3f7' : '#e0e0e0', fontSize: 13 }}>{s.name}</div>
                <button
                  title="Rename"
                  onClick={e => { e.stopPropagation(); setRenameValue(s.name); setRenamingId(s.id); }}
                  style={{ background: 'transparent', border: 'none', color: '#475569', cursor: 'pointer', fontSize: 12, padding: '0 2px' }}>✏️</button>
              </div>
            )}
            <div style={{ fontSize: 11, color: '#90a4ae', marginTop: 2 }}>
              Retire {s.retirement_age_you} · SS {s.ss_claim_age_you} · ${(s.annual_spending / 1000).toFixed(0)}k/yr
            </div>
          </div>
        ))}
      </div>

      {/* Right: scenario editor */}
      <div>
        {runStatus && (
          <div style={{
            marginBottom: 12, padding: '10px 14px', borderRadius: 8,
            background: runStatus.type === 'success' ? '#1a3a1a' : '#3a1a1a',
            border: `1px solid ${runStatus.type === 'success' ? '#81c784' : '#ef5350'}`,
            color: runStatus.type === 'success' ? '#81c784' : '#ef5350',
            fontSize: 13,
          }}>
            {runStatus.message}
          </div>
        )}
        {selectedScenario ? (
          <ScenarioEditor
            key={selectedScenario.id}
            scenario={selectedScenario}
            profiles={profiles}
            onSave={handleSave}
            onRun={handleRun}
            onDelete={() => handleDelete(selectedScenario.id)}
            onDuplicate={() => handleDuplicate(selectedScenario.id)}
            running={running}
          />
        ) : (
          <div className="card" style={{ color: '#90a4ae', textAlign: 'center', padding: 40 }}>
            Select or create a scenario to edit it.
          </div>
        )}
      </div>
    </div>
  );
}
