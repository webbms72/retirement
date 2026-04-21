# Design: Scenario Renaming, Withdrawal Playbook & Healthcare Visibility

**Date:** 2026-04-20
**Status:** Approved

---

## Overview

Three related UX improvements to the retirement planning app:

1. **Scenario renaming** — inline editable names on scenario cards
2. **Withdrawal Playbook** — year-by-year actionable instructions with PDF export, surfaced as a new panel in the Results tab
3. **Healthcare cost visibility** — dedicated KPI card, portfolio chart shading, and spending breakdown showing the pre-Medicare insurance gap

---

## 1. Scenario Renaming

### What

Each scenario card in the Scenarios tab gains a pencil (✏️) icon. Clicking it converts the name into an inline text input. The user types the new name, then confirms with Enter/✓ or cancels with Esc/✕.

### Behaviour

- **Trigger:** Click pencil icon on any scenario card
- **State:** Name field becomes `<input>` with current name pre-filled and focused
- **Confirm:** Enter key or ✓ button → calls `updateScenario({ name: newName })` → reverts to display mode
- **Cancel:** Esc key or ✕ button → discards change, reverts to display mode
- **Propagation:** The scenario name appears in the Results tab header, Monte Carlo tab header, and chart legends. All references update when name is saved.
- **Validation:** Name must be non-empty; max 60 characters. Blank name reverts to previous value.

### Backend changes

- Add `name: str` field to `Scenario` model (nullable, max 60 chars). Defaults to `"Scenario {id}"` if not set.
- Add `name` to the scenario schema and `updateScenario` API endpoint.

### Frontend changes

- `ScenariosTab.jsx`: add pencil icon + inline input state per card
- `ResultsTab.jsx`, `MonteCarloTab.jsx`: display scenario name in header
- `PortfolioChart.jsx`, `PercentileFanChart.jsx`: use scenario name in chart legend/title

---

## 2. Withdrawal Playbook

### What

A new collapsible panel at the bottom of the Results tab. Shows year-by-year withdrawal instructions derived from the projection engine's per-year `withdrawal_notes` and `income_by_source` data. The user selects a year from a strip of year buttons and sees numbered steps for that year.

### Year selector

- Horizontal strip of year buttons spanning retirement year through life expectancy
- Past years (before current date) shown in muted style
- Selected year highlighted in blue
- Default selection: first year of retirement (or current year if already retired)

### Instruction steps

Each step is one `<li>` with:
- Coloured dot indicating account type (brokerage=blue, 401k=amber, Roth=green, RMD=purple, healthcare=orange)
- **Bold dollar amount** and **bold account name**
- One-line plain-English reason (derived from the optimizer note for that step)

**Step ordering per year:**
1. Healthcare reminder (if pre-Medicare and healthcare cost > 0)
2. RMD (if age 73+) — mandatory
3. HSA draw (if healthcare gap and HSA balance > 0)
4. Brokerage draw (with LTCG rate note)
5. Roth conversion (if enabled)
6. 401(k) draw (with Rule of 55 or penalty note)
7. Roth IRA draw (if needed)

**Footer:** Estimated federal + state tax for the year, with "consider quarterly estimated payments" reminder.

### PDF export

Export button in the playbook header with three scope options (toggle chips):
- **This year** — single-page checklist for the selected year
- **Full plan** — multi-page document, one page per year from retirement to life expectancy
- **Phase summary** — three-page document: Pre-SS / Post-SS / RMD phases

**PDF content per year includes:**
- Year, age, scenario name
- Numbered withdrawal steps with dollar amounts and reasons
- Estimated tax liability (federal + state)
- Healthcare cost line if applicable

**Implementation:** Use `window.print()` with a print-specific CSS stylesheet injected at export time. The playbook panel renders a print-ready layout when triggered. No server-side PDF generation required.

### Data source

The playbook reads from the existing projection API response (`GET /api/projections/{scenario_id}`). Each year in `projection.years` already contains:
- `income_by_source` — dollar amounts per source
- `withdrawal_notes` — array of optimizer notes explaining each decision
- `federal_tax`, `state_tax` — tax estimates
- `age_you`, `age_spouse` — for age-gated logic (Medicare, RMD, Rule of 55)

No new backend endpoints required. The frontend transforms the raw optimizer notes into human-readable instructions using a `buildPlaybookSteps(year)` utility function.

### `buildPlaybookSteps(year)` logic

```
inputs: ProjectionYear object
outputs: Step[]  { dot, amount, account, text, reason }

1. if year.age_you < 65 and healthcare_annual > 0:
     → Healthcare step: "Budget $X for health insurance (Jan–Dec)"

2. if rmd > 0:
     → RMD step: "Take $X RMD from your 401(k) by Dec 31"

3. if hsa_withdrawal > 0:
     → HSA step: "Draw $X from HSA for medical expenses"

4. if brokerage_withdrawal > 0:
     → Brokerage step: "Draw $X from Brokerage" + LTCG rate from note

5. if roth_conversion > 0:
     → Roth conversion step: "Convert $X from 401(k) → Roth IRA" + bracket note

6. if 401k_withdrawal > 0:
     → 401k step: "Draw $X from 401(k)" + penalty/Rule of 55 note

7. if roth_withdrawal > 0:
     → Roth step: "Draw $X from Roth IRA (tax-free)"
```

Reason text is extracted from the matching `withdrawal_notes` string (pattern-matched on account type prefix).

---

## 3. Healthcare Cost Visibility

### KPI card (4th card, replacing "Estate at Life Exp")

- Label: "Pre-Medicare HC Cost"
- Value: total inflation-adjusted healthcare cost over the gap period (sum of `healthcare_annual` across pre-65 years)
- Sub-label: "Ages X–65 · N yrs"
- Colour: amber (`#fcd34d`) to signal a significant cost centre

### Portfolio chart shading

- Light amber shading (`rgba(180, 83, 9, 0.07)`) over the x-axis range from retirement year through age-65 year
- Small "HC cost zone" label at top-left of the shaded region
- Requires knowing the retirement year and Medicare start year — both derivable from `projection.years`

### Spending breakdown panel (new, left column below chart)

Replaces nothing — added as a second panel in a two-column layout alongside the existing Tax Summary. Shows:
- **Core living** — `annual_spending` (base)
- **Healthcare (pre-65)** — `healthcare_annual` (shown as 0 after age 65)
- **Federal + state tax** — sum of `federal_tax + state_tax`

Displayed as horizontal bar segments proportional to total annual outflow. Values are averages across all projected years (or the selected phase).

### Dedicated healthcare panel

Sits in the left column of the two-column row below the chart. Shows:
| Field | Value |
|---|---|
| Annual cost (today's $) | `healthcare_monthly_pre_medicare * 12` |
| Annual cost (age 65, inflated) | above × `inflation_factor` at age 65 |
| Total over gap period | sum of `healthcare_annual` for ages < 65 |
| % of annual spending | total ÷ annual_spending × 100 |
| Medicare begins | year + (65 − current_age) |

---

## Data Flow Summary

```
Existing projection API response (no new endpoints)
  └── projection.years[]
        ├── income_by_source        → playbook step amounts
        ├── withdrawal_notes[]      → playbook step reasons
        ├── federal_tax, state_tax  → playbook footer, spending bar
        ├── healthcare_annual       → HC panel, spending bar, chart shading
        └── age_you                 → year selector, step gating, HC zone
```

---

## Out of Scope

- Implementing the manual withdrawal order in the backend optimizer (separate task)
- Roth conversion cohort tracking in the playbook
- IRMAA-specific warnings in the playbook
- Mobile/responsive layout changes

---

## Files Affected

| File | Change |
|---|---|
| `backend/models.py` | Add `name` column to `Scenario` |
| `backend/schemas.py` (or equivalent) | Add `name` to scenario schema |
| `backend/routers/scenarios.py` | Accept `name` in create/update |
| `frontend/src/tabs/ScenariosTab.jsx` | Inline rename UI |
| `frontend/src/tabs/ResultsTab.jsx` | KPI card swap, two-column layout, playbook panel |
| `frontend/src/tabs/MonteCarloTab.jsx` | Scenario name in header |
| `frontend/src/components/PortfolioChart.jsx` | HC cost zone shading |
| `frontend/src/components/WithdrawalPlaybook.jsx` | New component |
| `frontend/src/components/HealthcareCostPanel.jsx` | New component |
| `frontend/src/components/SpendingBreakdownBar.jsx` | New component |
