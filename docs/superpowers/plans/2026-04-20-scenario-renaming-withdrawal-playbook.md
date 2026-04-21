# Scenario Renaming, Withdrawal Playbook & Healthcare Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add inline scenario renaming on cards, a year-by-year withdrawal playbook with PDF export, and healthcare cost visibility panels to the Results tab.

**Architecture:** All new UI reads from the existing `GET /api/projections/{scenario_id}` response — no new backend endpoints. One backend change adds `healthcare_annual` to `income_by_source`. Three new React components are wired into `ResultsTab`.

**Tech Stack:** FastAPI/SQLAlchemy (backend), React 18/Recharts (frontend), `window.print()` for PDF export, pytest (backend tests).

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `backend/engines/projection.py` | Modify | Add `healthcare_annual` to `income_by_source` dict |
| `backend/tests/test_projection.py` | Modify | Add test for `healthcare_annual` field |
| `frontend/src/tabs/ScenariosTab.jsx` | Modify | Pencil-icon inline rename on list cards |
| `frontend/src/tabs/MonteCarloTab.jsx` | Modify | Scenario name heading below selector chips |
| `frontend/src/components/PortfolioChart.jsx` | Modify | Amber HC zone shading via `ReferenceArea` |
| `frontend/src/components/WithdrawalPlaybook.jsx` | Create | Year strip + instruction list + PDF export |
| `frontend/src/components/HealthcareCostPanel.jsx` | Create | 5-row HC metrics table |
| `frontend/src/components/SpendingBreakdownBar.jsx` | Create | Proportional horizontal spending bar |
| `frontend/src/tabs/ResultsTab.jsx` | Modify | KPI swap, layout restructure, wire all components |

---

### Task 1: Add `healthcare_annual` to `income_by_source` (backend)

**Files:**
- Modify: `backend/engines/projection.py`
- Test: `backend/tests/test_projection.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_projection.py`:

```python
def test_healthcare_annual_in_income_by_source():
    """healthcare_annual must be present and correct for pre-65 retirement years."""
    from backend.engines.projection import project_one_year, ScenarioParams
    from backend.engines.withdrawal import AccountState

    params = ScenarioParams(
        retirement_age_you=57,
        retirement_age_spouse=57,
        annual_spending=60_000.0,
        spending_glide_path={},
        ss_claim_age_you=67,
        ss_claim_age_spouse=67,
        ss_monthly_you=0.0,
        ss_monthly_spouse=0.0,
        withdrawal_strategy="optimized",
        manual_withdrawal_order=[],
        roth_conversion_enabled=False,
        roth_conversion_target_bracket=None,
        healthcare_monthly_pre_medicare=1_500.0,
        stock_allocation=0.6,
        expected_return_stocks=0.07,
        expected_return_bonds=0.04,
        inflation_rate=0.025,
        pension_monthly_you=0.0,
        pension_start_age_you=0,
        rental_annual_income=0.0,
        nqdc_schedule=[],
        life_expectancy_you=88,
        life_expectancy_spouse=88,
        dob_year_you=1969,
        dob_year_spouse=1969,
        base_year=2024,
        filing_status="mfj",
        state="DE",
    )
    accounts = [
        AccountState(
            account_type="brokerage",
            balance=500_000.0,
            basis=0.0,
            owner="you",
            is_rule_of_55_eligible=False,
            annual_contribution=0.0,
        )
    ]
    result = project_one_year(
        year=2026,
        age_you=57,
        age_spouse=57,
        accounts=accounts,
        params=params,
        prior_year_magi=0.0,
        cumulative_inflation=1.0,
        is_retired_you=True,
        is_retired_spouse=True,
        first_death_year=None,
    )
    assert "healthcare_annual" in result.income_by_source
    assert result.income_by_source["healthcare_annual"] == pytest.approx(1_500.0 * 12, rel=0.001)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/markwebb/Documents/Dev/webbms72/retirement
python -m pytest backend/tests/test_projection.py::test_healthcare_annual_in_income_by_source -v
```

Expected: FAIL (`KeyError` or `AssertionError`)

- [ ] **Step 3: Add `healthcare_annual` to the `income_by_source` dict in `projection.py`**

In `backend/engines/projection.py`, find the `income_by_source` dict (around line 322). Change:

```python
    income_by_source = {
        "ss_you": round(ss_you_annual, 2),
        "ss_spouse": round(ss_spouse_annual, 2),
        "nqdc": round(nqdc_income, 2),
        "pension": round(pension_annual, 2),
        "rental": round(rental_annual, 2),
        "rmd": round(total_rmd, 2),
        "401k_withdrawal": round(wr.withdrawals_by_account.get("401k", 0.0), 2),
        "roth_withdrawal": round(wr.withdrawals_by_account.get("roth_ira", 0.0), 2),
        "brokerage_withdrawal": round(ltcg_income, 2),
        "hsa_withdrawal": round(wr.withdrawals_by_account.get("hsa", 0.0), 2),
        "roth_conversion": round(wr.roth_conversion_amount, 2),
    }
```

To:

```python
    income_by_source = {
        "ss_you": round(ss_you_annual, 2),
        "ss_spouse": round(ss_spouse_annual, 2),
        "nqdc": round(nqdc_income, 2),
        "pension": round(pension_annual, 2),
        "rental": round(rental_annual, 2),
        "rmd": round(total_rmd, 2),
        "401k_withdrawal": round(wr.withdrawals_by_account.get("401k", 0.0), 2),
        "roth_withdrawal": round(wr.withdrawals_by_account.get("roth_ira", 0.0), 2),
        "brokerage_withdrawal": round(ltcg_income, 2),
        "hsa_withdrawal": round(wr.withdrawals_by_account.get("hsa", 0.0), 2),
        "roth_conversion": round(wr.roth_conversion_amount, 2),
        "healthcare_annual": round(healthcare_annual, 2),
    }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest backend/tests/test_projection.py::test_healthcare_annual_in_income_by_source -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite**

```bash
python -m pytest backend/tests/ -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/engines/projection.py backend/tests/test_projection.py
git commit -m "feat: expose healthcare_annual in income_by_source projection data"
```

---

### Task 2: Scenario card inline rename

**Files:**
- Modify: `frontend/src/tabs/ScenariosTab.jsx`

The scenario list on the left side of `ScenariosTab` shows name + metadata divs (lines 320–338). Add pencil-icon inline editing per card.

- [ ] **Step 1: Add rename state to `ScenariosTab`**

After the existing state declarations (around line 239), add:

```javascript
  const [renamingId, setRenamingId] = useState(null);
  const [renameValue, setRenameValue] = useState('');
```

- [ ] **Step 2: Add `handleRename` function**

After the `handleRun` function (around line 302), add:

```javascript
  async function handleRename(id) {
    const trimmed = renameValue.trim().slice(0, 60);
    if (!trimmed) { setRenamingId(null); return; }
    const scenario = scenarios.find(s => s.id === id);
    if (!scenario) { setRenamingId(null); return; }
    try {
      const updated = await updateScenario(id, { ...scenario, name: trimmed });
      setScenarios(prev => prev.map(s => s.id === id ? { ...s, name: updated.name } : s));
    } catch (err) { console.error('Rename failed:', err); }
    setRenamingId(null);
  }
```

- [ ] **Step 3: Replace the scenario list card rendering**

Replace the entire `{scenarios.map(s => (` block (lines 320–337) with:

```javascript
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
```

- [ ] **Step 4: Manual verify**

Start the dev server. On the Scenarios tab:
- Each card shows a ✏️ button
- Clicking ✏️ shows an input pre-filled with the current name
- Enter saves, Esc cancels
- Saved name updates immediately in the card and in the editor header

- [ ] **Step 5: Commit**

```bash
git add frontend/src/tabs/ScenariosTab.jsx
git commit -m "feat: pencil-icon inline rename on scenario list cards"
```

---

### Task 3: MonteCarloTab — scenario name heading

**Files:**
- Modify: `frontend/src/tabs/MonteCarloTab.jsx`

- [ ] **Step 1: Add name heading after scenario selector chips**

Find the closing `</div>` of the scenario selector chip row (around line 116 — the closing tag of the `div` that contains the `{scenarios.map(...)}` flex row). After that closing `</div>`, add:

```jsx
      {selectedScenario && (
        <h2 style={{ color: '#f1f5f9', fontSize: 18, fontWeight: 700, margin: '0 0 20px 0' }}>
          {selectedScenario.name}
        </h2>
      )}
```

- [ ] **Step 2: Manual verify**

Switch scenarios in the Monte Carlo tab and confirm the heading updates to match the selected scenario name.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/tabs/MonteCarloTab.jsx
git commit -m "feat: show selected scenario name as heading in Monte Carlo tab"
```

---

### Task 4: PortfolioChart — pre-Medicare HC zone shading

**Files:**
- Modify: `frontend/src/components/PortfolioChart.jsx`

- [ ] **Step 1: Add `ReferenceArea` to the Recharts import**

Change line 1–5 from:

```javascript
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceLine, Legend,
} from 'recharts';
```

To:

```javascript
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceLine, ReferenceArea, Legend,
} from 'recharts';
```

- [ ] **Step 2: Add `medicareStartAge` prop and shading element**

Change the component signature from:

```javascript
export default function PortfolioChart({ data, retirementAge, ssStartAge }) {
```

To:

```javascript
export default function PortfolioChart({ data, retirementAge, ssStartAge, medicareStartAge }) {
```

Inside `<LineChart>`, after the last existing `<ReferenceLine>` (the RMD one at age 73), add:

```jsx
        {retirementAge != null && medicareStartAge != null && retirementAge < medicareStartAge && (
          <ReferenceArea
            x1={retirementAge}
            x2={medicareStartAge}
            fill="rgba(180, 83, 9, 0.07)"
            label={{ value: 'HC cost zone', position: 'insideTopLeft', fill: '#b45309', fontSize: 9 }}
          />
        )}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/PortfolioChart.jsx
git commit -m "feat: amber HC cost zone shading on portfolio chart"
```

---

### Task 5: WithdrawalPlaybook component

**Files:**
- Create: `frontend/src/components/WithdrawalPlaybook.jsx`

- [ ] **Step 1: Create the file**

Create `frontend/src/components/WithdrawalPlaybook.jsx`:

```jsx
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
    window.print();
    document.head.removeChild(style);
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

      {/* Hidden print target — rendered for all scopes on demand */}
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
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/WithdrawalPlaybook.jsx
git commit -m "feat: add WithdrawalPlaybook component with year selector, steps, and PDF export"
```

---

### Task 6: HealthcareCostPanel component

**Files:**
- Create: `frontend/src/components/HealthcareCostPanel.jsx`

- [ ] **Step 1: Create the file**

```jsx
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
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/HealthcareCostPanel.jsx
git commit -m "feat: add HealthcareCostPanel component"
```

---

### Task 7: SpendingBreakdownBar component

**Files:**
- Create: `frontend/src/components/SpendingBreakdownBar.jsx`

- [ ] **Step 1: Create the file**

```jsx
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
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/SpendingBreakdownBar.jsx
git commit -m "feat: add SpendingBreakdownBar component"
```

---

### Task 8: ResultsTab — KPI swap + full layout integration

**Files:**
- Modify: `frontend/src/tabs/ResultsTab.jsx`

- [ ] **Step 1: Update imports**

Replace the existing import block at the top:

```javascript
import React, { useEffect, useState } from 'react';
import { getScenarios, getProjection } from '../api/client.js';
import PortfolioChart from '../components/PortfolioChart.jsx';
import IncomeBreakdownChart from '../components/IncomeBreakdownChart.jsx';
import TaxSummaryPanel from '../components/TaxSummaryPanel.jsx';
```

With:

```javascript
import React, { useEffect, useState } from 'react';
import { getScenarios, getProjection } from '../api/client.js';
import PortfolioChart from '../components/PortfolioChart.jsx';
import IncomeBreakdownChart from '../components/IncomeBreakdownChart.jsx';
import TaxSummaryPanel from '../components/TaxSummaryPanel.jsx';
import WithdrawalPlaybook from '../components/WithdrawalPlaybook.jsx';
import HealthcareCostPanel from '../components/HealthcareCostPanel.jsx';
import SpendingBreakdownBar from '../components/SpendingBreakdownBar.jsx';
```

- [ ] **Step 2: Add HC cost computations after `estateBalance`**

After line 69 (`const estateBalance = lastRow?.portfolio_balance ?? null;`), add:

```javascript
  const preMedicareHcCost = rows
    .filter(r => (r.income_by_source?.healthcare_annual || 0) > 0)
    .reduce((sum, r) => sum + (r.income_by_source?.healthcare_annual || 0), 0);

  const hasMedicareGap =
    (selectedScenario?.healthcare_monthly_pre_medicare || 0) > 0 &&
    (selectedScenario?.retirement_age_you ?? 99) < 65;
  const medicareStartAge = hasMedicareGap ? 65 : null;

  const hcGapYears = rows.filter(
    r => r.age_you >= (selectedScenario?.retirement_age_you ?? 99) && r.age_you < 65
  );
  const hcStartAge = hcGapYears[0]?.age_you ?? null;
```

- [ ] **Step 3: Replace the 4th MetricCard**

Find:

```jsx
        <MetricCard label="Estate at Life Exp" value={fmtDollar(estateBalance)} />
```

Replace with:

```jsx
        <MetricCard
          label={hcStartAge != null ? `Pre-Medicare HC Cost · Ages ${hcStartAge}–65` : 'Pre-Medicare HC Cost'}
          value={preMedicareHcCost > 0 ? fmtDollar(preMedicareHcCost) : '—'}
          color="#fcd34d"
        />
```

- [ ] **Step 4: Replace the two-column charts/panels section and add playbook**

Find the entire block starting with `{/* Charts + Tax Summary */}` through the closing `</div>` of the two-col div (lines 110–133). Replace it with:

```jsx
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
```

- [ ] **Step 5: End-to-end manual test**

1. Run `make dev` (or equivalent) to start both servers
2. Run a projection from the Scenarios tab
3. Navigate to Results tab and verify:
   - 4th KPI card shows amber "Pre-Medicare HC Cost" (or `—` if no HC configured)
   - Portfolio chart shows amber shading labeled "HC cost zone" over pre-Medicare years
   - Right column: HealthcareCostPanel (amber title) → SpendingBreakdownBar → TaxSummaryPanel
   - WithdrawalPlaybook appears at the bottom with a year strip
   - Clicking a year updates the instruction list with colored numbered dots
   - Tax footer shows federal + state total
   - Scope chips cycle between "This year", "Full plan", "Phase summary"
   - "Export PDF" opens the browser print dialog

- [ ] **Step 6: Commit**

```bash
git add frontend/src/tabs/ResultsTab.jsx
git commit -m "feat: HC visibility KPI, chart shading, spending bar, and withdrawal playbook in Results tab"
```

---

## Self-Review

**Spec coverage:**

| Requirement | Task |
|---|---|
| `name` field on Scenario model/schema/router | Already in codebase — no changes needed |
| Pencil-icon inline rename on scenario cards | Task 2 |
| Scenario name in Results tab | Existing selector chips already show `s.name` ✓ |
| Scenario name in MC tab header | Task 3 |
| `healthcare_annual` in projection API response | Task 1 |
| Withdrawal Playbook — year strip | Task 5 |
| Playbook — colored step dots (HC orange, brokerage blue, 401k amber, Roth green, RMD purple) | Task 5 (`STEP_CONFIG`) |
| Playbook — step ordering per spec | Task 5 (`buildPlaybookSteps`) |
| Playbook — tax footer with quarterly reminder | Task 5 (`PlaybookYear`) |
| PDF export with 3 scope chips | Task 5 |
| 4th KPI card — Pre-Medicare HC Cost in amber | Task 8 |
| Portfolio chart HC zone shading with label | Tasks 4 + 8 |
| HealthcareCostPanel — 5 rows | Task 6 |
| SpendingBreakdownBar — 3 segments | Task 7 |
| No new backend endpoints | All read from existing projection API ✓ |

**Placeholder scan:** None found — all steps contain complete code.

**Type consistency:**
- `WithdrawalPlaybook` props: `{ rows, retirementAge, scenarioName }` — matches Task 8 usage ✓
- `HealthcareCostPanel` props: `{ rows, scenario }` — matches Task 8 usage ✓
- `SpendingBreakdownBar` props: `{ rows, scenario }` — matches Task 8 usage ✓
- `PortfolioChart` new prop: `medicareStartAge` — defined in Task 4, passed in Task 8 ✓
- `income_by_source.healthcare_annual` — added in Task 1, consumed in Tasks 5/6/7/8 ✓
