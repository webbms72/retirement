# Retirement Calculator — Design Spec

**Date:** 2026-04-17  
**Status:** Approved  
**Owner:** Webbm

---

## Overview

A local-first retirement planning web application for a married couple (early 50s, targeting retirement at 56–59) with all major account types. The tool answers questions like:

- At what retirement age does our portfolio survive with >90% probability?
- What is the most tax-efficient withdrawal order each year?
- When should each spouse claim Social Security to maximize lifetime benefits and survivor protection?
- What does a Roth conversion ladder look like during the low-income window between retirement and SS?
- How sensitive are our outcomes to spending, returns, and inflation assumptions?

---

## User Profile

- **Age:** Early 50s (both spouses)
- **Target retirement:** 56–59 (Rule of 55 is a key feature)
- **Filing status:** Married Filing Jointly; single after first spouse death
- **State:** Delaware
- **Accounts:** 401k/Traditional IRA, Roth 401k/IRA, Taxable Brokerage, HSA, NQDC (fixed payout schedule), Pension/Defined Benefit, Real Estate/Rental Income
- **SS:** Direct SSA statement input (amounts at 62, 67, 70 per person)
- **Spouse modeling:** Full — both spouses modeled including survivor benefits

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy, SQLite |
| Numerical | NumPy, pandas |
| Frontend | React 18, Vite, Recharts |
| Dev tooling | Makefile, uvicorn (backend), Vite dev server (frontend) |
| Database | SQLite (`retirement.db` in project root) |

### Launch

```
make install   # one-time: pip install + npm install
make dev       # starts backend (port 8000) + frontend (port 5173) + opens browser
make db-reset  # wipe and re-initialize database
make test      # run backend test suite
```

A single `./start.sh` wrapper also available for non-Makefile users.

---

## Architecture

```
Frontend (React, :5173)
  ↕ REST API (JSON)
Backend (FastAPI, :8000)
  ├── Projection Engine
  ├── Tax Engine
  ├── Monte Carlo Engine
  ├── Withdrawal Optimizer
  └── SS Optimizer
  ↕ SQLAlchemy ORM
SQLite (retirement.db)
```

The backend is stateless per request — all state lives in SQLite. Projection and Monte Carlo results are cached in the database, keyed by a hash of the scenario inputs, so re-running the same scenario is instant.

---

## Data Model

### `profiles`
One row per person (you + spouse).

| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| name | text | "You" or "Spouse" |
| dob | date | |
| life_expectancy_age | int | User-adjustable, default 88/90 |
| state | text | "DE" |
| filing_status | text | "mfj" or "single" (auto-switches after death) |
| pre_retirement_income | decimal | Used for current-year tax modeling |

### `accounts`
One row per account.

| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| owner_id | int FK → profiles | |
| account_type | text | 401k, roth_ira, brokerage, hsa, nqdc, pension, real_estate |
| balance | decimal | Current balance |
| annual_return | decimal | Expected return rate |
| annual_contribution | decimal | Contributions until retirement |
| nqdc_schedule | json | List of {date, amount} for NQDC only |
| pension_monthly | decimal | Monthly benefit for pension type |
| pension_start_age | int | |
| rental_annual_income | decimal | For real_estate type |

### `social_security`
One row per person.

| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| owner_id | int FK → profiles | |
| benefit_at_62 | decimal | Monthly, from SSA statement |
| benefit_at_fra | decimal | Monthly at full retirement age |
| fra_age | int | 67 for most born after 1960 |
| benefit_at_70 | decimal | Monthly |
| survivor_benefit_pct | decimal | % of deceased spouse's benefit |

### `scenarios`
Named what-if configurations.

| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| name | text | e.g. "Retire 57 · SS 67" |
| retirement_age_you | int | |
| retirement_age_spouse | int | |
| annual_spending | decimal | Today's dollars |
| spending_glide_path | json | Optional age→amount overrides |
| ss_claim_age_you | int | |
| ss_claim_age_spouse | int | |
| withdrawal_strategy | text | "manual" or "optimized" |
| manual_withdrawal_order | json | Account type priority list |
| roth_conversion_enabled | bool | Advanced toggle |
| roth_conversion_target_bracket | text | e.g. "22%" |
| healthcare_monthly_pre_medicare | decimal | ACA estimate ages 56–65 |
| stock_allocation | decimal | 0.0–1.0 |
| expected_return_stocks | decimal | Default 7.0% |
| expected_return_bonds | decimal | Default 4.0% |
| inflation_rate | decimal | Default 2.5% |

### `projections`
Cached year-by-year results per scenario.

| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| scenario_id | int FK | |
| input_hash | text | SHA256 of scenario + accounts + profiles |
| year | int | Calendar year |
| age_you | int | |
| age_spouse | int | |
| portfolio_balance | decimal | Total across all accounts |
| balances_by_account | json | Per-account breakdown |
| gross_income | decimal | |
| income_by_source | json | SS, 401k, Roth, brokerage, NQDC, RMD, rental, pension |
| federal_tax | decimal | |
| state_tax | decimal | |
| effective_rate | decimal | |
| roth_conversion_amount | decimal | |
| withdrawal_notes | json | Optimizer decisions |

### `mc_results`
Cached Monte Carlo results per scenario.

| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| scenario_id | int FK | |
| input_hash | text | |
| num_simulations | int | |
| survival_rate | decimal | |
| percentile_10 | json | Balance by year |
| percentile_25 | json | |
| percentile_50 | json | |
| percentile_75 | json | |
| percentile_90 | json | |
| sensitivity | json | Variable → survival delta |
| run_at | datetime | |

---

## Calculation Engines

### 1. Projection Engine

Runs year-by-year from current year through the later spouse's life expectancy. Each year:

1. Apply expected investment return to each account balance
2. Apply annual contributions (until retirement date)
3. Apply NQDC payout schedule (fixed, user-defined)
4. Apply pension income if active
5. Apply rental income
6. Calculate RMDs (IRS Uniform Lifetime Table, starting at age 73) on all pre-tax accounts
7. Invoke Withdrawal Optimizer to cover spending gap: `spending + taxes - guaranteed_income`
8. Pass income composition to Tax Engine → get tax bill
9. If first spouse dies in this year: merge accounts, adjust SS to survivor benefit, switch to single filing status
10. Record year row to `projections` table

**Rule of 55:** If retirement age ≥ 55 and account is a current-employer 401k, no 10% early withdrawal penalty applies. The engine tracks this and applies the penalty (10% of withdrawal) otherwise.

**Early withdrawal (age < 59½):** Standard 10% penalty on traditional 401k/IRA withdrawals unless Rule of 55 applies or exception qualifies. HSA: penalty-free for qualified medical expenses at any age.

### 2. Tax Engine

Models federal and Delaware state taxes each year.

**Federal:**
- Ordinary income: MFJ brackets (2024 rates, inflation-adjusted by CPI each year)
- Long-term capital gains: 0% / 15% / 20% based on taxable income
- Social Security inclusion: 0% below base threshold, 50% in middle tier, 85% above upper threshold (both thresholds indexed to scenario inflation)
- Standard deduction applied (MFJ or single, age 65+ additional deduction)
- IRMAA surcharge: if prior-year MAGI exceeds thresholds, add Medicare Part B/D surcharge
- Roth conversion: added to ordinary income in conversion year

**Delaware State:**
- Standard DE income tax brackets applied to DE taxable income
- Retirement income exclusion: $12,500 per person (each spouse) for pension/retirement income after age 60
- No DE tax on Social Security income

**Outputs per year:** gross income, federal tax, state tax, effective rate, marginal rate, IRMAA flag, bracket used for conversions.

### 3. Monte Carlo Engine

Runs N simulations (default 10,000, configurable 1,000–50,000) on a given scenario.

**Per simulation:**
1. Sample annual stock return from a normal distribution (mean = `expected_return_stocks`, σ = 15%)
2. Sample annual bond return (mean = `expected_return_bonds`, σ = 6%)
3. Sample inflation (mean = `inflation_rate`, σ = 1%)
4. Run the full Projection Engine with sampled values (deterministic tax modeling)
5. Record portfolio balance each year and whether portfolio survived to life expectancy

**Outputs:**
- Survival rate (% of simulations where portfolio > 0 at life expectancy)
- Percentile bands by year: 10th, 25th, 50th, 75th, 90th
- Sensitivity table: re-run with ±1σ on each key variable, record survival delta

**Sensitivity variables:**
- Retirement age (current ± 2 years)
- Annual spending (current ± 15%)
- SS claim age (62 vs 70 for primary earner)
- Expected stock return (± 1%)
- Inflation (± 1%)
- Stock/bond allocation (± 10%)

Results cached in `mc_results` by `input_hash`. Cache invalidated automatically when scenario or profile inputs change.

### 4. Withdrawal Optimizer

Given a required withdrawal amount for the year, determines the most tax-efficient source order.

**Inputs:** required amount, current account balances, current bracket, age, whether Rule of 55 applies, Roth conversion flag.

**Logic (optimized mode):**

1. **Required minimum distributions** — must be taken first from all pre-tax accounts at 73+
2. **NQDC payout** — fixed schedule, not discretionary; applied as income regardless
3. **Pension + rental income** — applied as income regardless
4. **Cover remaining gap:**
   a. Check if current bracket allows 0% LTCG (taxable income ≤ 12% bracket top) → use brokerage first
   b. If Roth conversion enabled: fill current bracket to target rate with 401k → Roth conversion
   c. HSA: use for qualified medical expenses (healthcare line item) before other accounts
   d. Draw from Roth IRA last (tax-free, no RMDs, best for late years and estate)
   e. Rule of 55 window (age 55–59½): prefer 401k over IRA to use penalty exemption

**Manual mode:** Follow user-specified account priority order, apply same penalty/RMD rules.

**Output per year:** withdrawal amounts by account, conversion amounts, optimizer notes (human-readable), effective strategy used.

### 5. SS Optimizer

Exhaustively evaluates all valid Social Security claiming combinations for both spouses.

**Claim age options:** All integer ages 62–70 evaluated exhaustively for each spouse (9×9 = 81 combinations). Fractional month optimization is out of scope for v1.

**Rules modeled:**
- Early claim reduction: ~6.67%/year before FRA (ages 62–FRA)
- Delayed credits: 8%/year after FRA (FRA–70)
- Spousal benefit: 50% of primary earner's FRA benefit; can't claim before 62; reduced if claimed before own FRA
- Survivor benefit: higher of own benefit or deceased spouse's benefit; maximized when higher earner delays to 70
- Earnings test (age < FRA): if still working, benefits withheld above threshold — relevant for pre-retirement years

**Output:** ranked table of (you_age, spouse_age) combinations sorted by lifetime benefit at specified life expectancies, with notes on survivor impact.

---

## Frontend

### Navigation
Top-level tabs: **Profile** | **Scenarios** | **Results** | **Monte Carlo**

### Profile Tab
Two-column layout:
- Left: People (DOB, life expectancy) + Social Security (amounts at 62/FRA/70, per person)
- Right: Accounts table (type, owner, balance, return, add/edit/delete) + NQDC schedule editor (date/amount rows)

### Scenarios Tab
List of named scenarios with quick stats (survival rate, retirement age, SS ages). Click to open/edit. "Duplicate" to create a variant. "Compare" to put two scenarios side by side.

Scenario editor fields: retirement ages, annual spending, optional spending glide path, SS claim ages, withdrawal strategy (manual/optimized), Roth conversion toggle (advanced), healthcare estimate, return assumptions.

### Results Tab
Two-panel layout:

**Left (charts):**
- Key metrics row: portfolio at retirement, depletion age (or "Never"), avg effective tax rate, estate value at life expectancy
- Portfolio balance over time (line chart with retirement, SS start, and RMD markers)
- Annual income by source (stacked bar chart: 401k, Roth, Brokerage, SS, NQDC, RMD, Pension, Rental)

**Right (tax summary):**
- Tax summary by phase (pre-SS, post-SS, post-RMD)
- Per-phase: income sources, federal tax, state tax, effective rate
- Optimizer notes: what decisions were made each phase

Scenario selector at top allows switching or adding a comparison scenario.

### Monte Carlo Tab
- Survival rate (large number, color-coded green/yellow/red)
- Key percentile callouts (10th/50th/90th portfolio at life expectancy)
- Percentile fan chart (portfolio by year, 10/25/50/75/90 bands)
- Sensitivity table (horizontal bar chart, variables ranked by survival impact)
- SS Claiming Strategy comparison table (top 4 strategies, lifetime benefit, survivor notes)
- Run button with simulation count selector

---

## Key Business Rules & Edge Cases

| Rule | Handling |
|---|---|
| Rule of 55 | No 10% penalty if separated from employer at 55+ and withdrawing from that employer's 401k |
| Early withdrawal penalty | 10% on pre-tax accounts before 59½, except Rule of 55, death, or disability (SEPP not modeled in v1) |
| HSA triple tax advantage | Contributions pre-tax, growth tax-free, withdrawals tax-free for medical. The user inputs an estimated annual healthcare spend; the optimizer applies HSA funds to that amount first. After 65, non-medical withdrawals are taxable as ordinary income (no penalty). The tool does not validate individual expense eligibility — it treats the user-provided healthcare line item as fully qualified. |
| NQDC taxation | Paid out per schedule, taxed as ordinary income in year received; no early withdrawal penalty |
| RMDs | Start at 73 (SECURE 2.0), calculated using IRS Uniform Lifetime Table on Dec 31 prior-year balance |
| SS taxation | 0–85% of SS included in federal income depending on combined income thresholds |
| DE exclusion | $12,500/person for pension/retirement income after age 60; does not apply to SS (already excluded by DE) |
| IRMAA | 2-year lookback; the Tax Engine automatically applies the surcharge based on projected MAGI two years prior. No manual input required — the engine looks back at the computed income from 2 years earlier in the projection. |
| Survivor benefit | On first death, survivor gets higher of own SS or 100% of deceased's SS; tool models both spouses' mortality |
| Roth 5-year rule | Conversions have a 5-year holding requirement before penalty-free withdrawal (before age 59½). The Withdrawal Optimizer tracks each conversion cohort by year and will not draw from a conversion cohort that hasn't seasoned. Contributions (not conversions) are always withdrawal-eligible. After age 59½ the 5-year rule for conversions no longer applies. |

---

## Makefile Targets

```makefile
install       # pip install -r requirements.txt && npm install (in frontend/)
dev           # start backend + frontend concurrently, open browser
backend       # start FastAPI backend only (uvicorn)
frontend      # start Vite dev server only
db-reset      # drop and recreate all SQLite tables
db-seed       # load sample profile data for development
test          # pytest backend/tests/
lint          # ruff check backend/ && eslint frontend/src/
build         # npm run build (production frontend bundle)
```

---

## Project Structure

```
retirement/
├── Makefile
├── start.sh
├── retirement.db              # SQLite (gitignored)
├── backend/
│   ├── main.py                # FastAPI app entry point
│   ├── models.py              # SQLAlchemy ORM models
│   ├── database.py            # DB session setup
│   ├── routers/
│   │   ├── profiles.py
│   │   ├── accounts.py
│   │   ├── scenarios.py
│   │   ├── projections.py
│   │   └── monte_carlo.py
│   ├── engines/
│   │   ├── projection.py      # Year-by-year simulation
│   │   ├── tax.py             # Federal + DE tax engine
│   │   ├── monte_carlo.py     # MC simulation runner
│   │   ├── withdrawal.py      # Withdrawal optimizer
│   │   └── ss_optimizer.py    # SS claiming strategy optimizer
│   ├── requirements.txt
│   └── tests/
│       ├── test_tax.py
│       ├── test_projection.py
│       ├── test_monte_carlo.py
│       └── test_ss_optimizer.py
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── tabs/
│       │   ├── ProfileTab.jsx
│       │   ├── ScenariosTab.jsx
│       │   ├── ResultsTab.jsx
│       │   └── MonteCarloTab.jsx
│       ├── components/
│       │   ├── AccountsTable.jsx
│       │   ├── NQDCSchedule.jsx
│       │   ├── PortfolioChart.jsx
│       │   ├── IncomeBreakdownChart.jsx
│       │   ├── PercentileFanChart.jsx
│       │   ├── SensitivityChart.jsx
│       │   ├── TaxSummaryPanel.jsx
│       │   └── SSStrategyTable.jsx
│       └── api/
│           └── client.js      # Axios API client
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-04-17-retirement-calculator-design.md
```

---

## Out of Scope (v1)

- Social Security fractional month optimization
- State taxes other than Delaware
- International accounts / foreign tax credit
- Estate planning (trusts, step-up in basis strategies)
- Real-time market data feeds
- Multi-user / cloud sync
- Mobile app
