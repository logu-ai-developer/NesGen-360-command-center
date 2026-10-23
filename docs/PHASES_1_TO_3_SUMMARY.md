# NesGen 360 V1.1: what was covered in Phases 1, 2 and 3

Repository: `nesgen-360-final-v1` (local Streamlit POC). Environment used for validation: Python 3.12.10, Streamlit 1.66.0, the existing `C:\Nes360\.venv`.

> **A note on numbering.** Phase 1 (metric correctness) and Phase 2 (time intelligence) were explicit phases. No work was ever labelled "Phase 3": each time a Phase 3 was mentioned it was deferred ("Do not start Phase 3"). Between and after those phases three smaller pieces were delivered, which this document groups as **Phase 3 (follow-up work)** so everything is in one place:
> 1. the UX simplification pass,
> 2. the Time Window selector visibility fix,
> 3. the Demo Scenario Data mode.
>
> The items on the original "later phases" list are still **not implemented** (see section 6).

## Contents
1. Test-count history
2. Phase 1: metric correctness and honest labelling
3. Phase 2: time-intelligence foundation
4. Phase 3 (follow-up work): UX simplification, selector fix, Demo mode
5. Where things live
6. Known limitations and what is deferred
7. How to verify

---

## 1. Test-count history

Counts are from successive snapshots; earlier numbers are history, not current results.

| Snapshot | Passed | Notes |
|---|---|---|
| Before Phase 1 (local snapshot) | 133 | baseline, re-run and confirmed |
| After Phase 1 | 201 | +68 tests in `tests/test_phase1_metrics.py` |
| After UX simplification | 207 | +6 tests in `tests/test_ux_simplification.py`; no existing test edited |
| After Phase 2 | 263 | +56 tests in `tests/test_phase2_time.py` |
| After selector fix | 263 | selector tests updated, none added |
| After Demo mode (current) | **273** | +10 tests in `tests/test_demo_mode.py` |

Tests use mocked or generated sources (Parquet and workbook fixtures, Streamlit AppTest). A guard fixture fails any test that reaches Gemini while pages render, so Gemini has never been called in validation. A real interactive browser session was never possible in the tooling used; only headless boot checks (HTTP 200, health `ok`) and AppTest page renders were performed. The user separately validated the UI in a browser and reported the selector and data observations that drove the later fixes.

---

## 2. Phase 1: metric correctness and honest labelling

**Goal:** make metrics internally consistent, honestly named, source-aware, and safe for later duration filtering and AI analysis. Formulas and labels were fixed before any visual redesign.

### 2.1 Problem found
Real telemetry has 3,000,000 events: 1,900,309 `FLOW-END`, 99,691 `FLOW-ERROR`, and 1,000,000 with no marker. The Level 1 cards excluded the unmarked rows, but the daily trend and Executive "availability" treated them as successful (null severity counted as non-error). The same source therefore told two different reliability stories.

### 2.2 Outcome classification (one helper, `src/metrics.py`)
Every event is exactly one of **Successful** (`Body.Tracepoint = FLOW-END`), **Failed** (`FLOW-ERROR`) or **Unclassified** (anything else, including a missing column). An event is never assumed successful because it lacks an error marker or has `INFO` severity. A SQL twin (`outcome_sql`) guarantees DuckDB and Python agree.

| Quantity | Formula | Denominator |
|---|---|---|
| Total events | Successful + Failed + Unclassified | n/a |
| Classified calls | Successful + Failed | n/a |
| Classified-call success rate | Successful / Classified x 100 | Classified calls |
| Classified-call failure rate | Failed / Classified x 100 | Classified calls |
| Unclassified share | Unclassified / Total events x 100 | Total events |

Zero-denominator behaviour: with no classified calls, rates are unavailable (`N/A` in the UI, `null` in tool evidence), never 0% or 100%, and no reliability finding is generated.

The same helper now feeds the Platform Health cards, the daily trend, failures by model, top errors, the Executive finding, decision briefs, the AI tool evidence and the query-tool metrics. The severity-based "non-error event rate" survives only as a separately named query metric and is documented as not comparable.

### 2.3 Labels
| Before | After |
|---|---|
| Platform availability | Classified-call success rate (not verified availability) |
| Governed models (Executive) | Models in inventory |
| Monthly active apps / use cases | Active-status use cases |
| New this month | New-status use cases |
| Dormant use cases ("No use in 30 days") | Dormant-status use cases (no inactivity window claimed) |
| Active platform users | Estimated / Reported active users |
| Total API calls / Successful calls / Failed calls | Total / Successful / Failed classified calls |
| Services healthy 41 / 43 | Removed (was a hardcoded illustration) |
| AI tool `priority_actions: 3` | Real count of decision-brief findings |

### 2.4 Stage, status, approval and activity are separate
- **Stage:** Sandbox, Industrialized. **Status:** Active, Dormant, New, Onboarding. **Approval:** a date within a period. **Activity:** no validated timestamp exists, so no activity metric is calculated.
- Status matching is **exact and allow-listed** (trim, case-fold). `Inactive` is `Unknown`, never `Active`. `Operational` is kept as an alias of Active. Unmapped values are preserved as `Unknown`.

### 2.5 Canonical use-case identity
The application ID is the key; the name is only a label. Duplicate IDs collapse to the first row, rows without an ID are **kept and reported** (previously dropped), and no ID is invented. Reconciliation metadata (total, by stage, by status, unknown status, duplicates, missing IDs) is shown in a User Adoption expander.

### 2.6 Active-user terminology
| Term | When |
|---|---|
| Estimated active users | synthetic fallback (derived from expected users) |
| Reported active users | workbook with an `Active Users` field; measurement unverified |
| N/A | workbook without the field |
| Observed active users | reserved; needs timestamp, identity, period and deduplication rule |

### 2.7 Source-mode vocabulary
`workbook`, `parquet`, `synthetic fallback`, `synthetic scenario`, `derived from workbook`, `derived from parquet`, `locally registered`, `unclassified telemetry present`. A badge shows origin only; it does not imply freshness, correctness, approval, production status, live integration or certification (stated in every KPI's details).

### 2.8 Other changes
- Query tools gained `outcome`-based and canonical-ID metrics, status/stage metrics, `active_users`, and corrected descriptions (kept under the 200-character tool-output truncation limit).
- The AI policy text was extended (unclassified is never success; no service-health inventory exists). No new LLM tool, no change to authentication, quota or request locking.
- Models carry `record_origin` (`catalog` or `locally registered`), and a locally registered badge appears on the lifecycle page.
- Small hardening: the lifecycle decision record no longer prints `nan` for unique API clients.

### 2.9 Documentation
Added `docs/METRIC_DEFINITIONS.md`; updated `README.md`, `DATA_CONTRACTS.md`, `LIMITATIONS.md`, `VALIDATION.md`, `V1_1_CHANGES.md`.

### 2.10 Tests (68 new)
Classification classes and edge cases, reconciliation, no `NaN`/`Infinity`, cards/trend/query tools/AI evidence agreeing on generated Parquet, exact status matching, canonical identity, active-user labels, source-mode vocabulary, locally registered models, the Services-healthy removal, rendered-page label checks and a sidebar-CSS check.

---

## 3. Phase 2: time-intelligence foundation

**Goal:** one deterministic time framework every page can use, without changing Phase 1 definitions.

### 3.1 The framework (`src/timewindow.py`)
| Sidebar option | Definition | Label |
|---|---|---|
| 1 Month | 30 days | Last 30 days |
| 3 Months | 90 days | Last 90 days |
| 6 Months (default) | 180 days | Last 180 days |

Fixed day counts, never calendar months. `resolve_window` returns `window_start`, `window_end`, `window_days`, `window_label`; both ends are inclusive; missing, unparseable and future dates fall outside every window.

**Anchor decision.** A window ends at the **latest non-future date of the source being windowed**, not at today's date. Reason: the real telemetry is from July 2026, and a today-anchored window would be empty. The end date is shown on every page. Forward-looking planning dates (`next_review_date`, `retire_date`) never set a lifecycle anchor, so windows cannot drift with the clock.

**Trend helpers (no Gemini):** `period_counts` (zero-filled 7-day buckets), `rolling_counts`, `period_total`, `period_average`, `trend_direction` (increasing / decreasing / stable; relative or absolute tolerance), `previous_window`.

### 3.2 What responds to the window
| Area | Date field | Windowed |
|---|---|---|
| Platform Health (cards, True P95, daily trend, failures by model and provider, top errors) | event timestamp | yes, one window for the whole page |
| Executive: success rate, unclassified events, trend chart, reliability finding | event timestamp | yes |
| Executive and User Adoption: Newly approved use cases, approval-based trend | approval date | yes |
| Model lifecycle date counts (caption) | review / retirement / migration dates | disclosed only; KPIs stay a snapshot |
| Inventory, status counts, chargeback, alerts | none | no (labelled snapshots) |

Every windowed view shows the window, the date field and the source mode. The Executive success-rate card also shows direction against the previous period. A "Newly approved use cases" card and an "Approval-based trend" section (with previous period and rows lacking an approval date) were added. Approval dates are never treated as activity.

### 3.3 Telemetry windowing details
`get_telemetry(window)` filters by event date, and now also returns `by_provider` and `undated_events`. **Events with no timestamp cannot be placed in any window**; in the real data the 1,000,000 unclassified rows have none, so they are excluded from windowed views and reported ("N events have no event timestamp…"). The un-windowed total still contains them.

### 3.4 Synthetic time coverage (fixed anchor 2026-10-17, seeds 362 to 365)
- **Platform health (180 days):** healthy baseline, degraded period, recovery ramp, error spikes (including the planted 8.6% day), latency spikes and unclassified-event spikes.
- **Approvals (100 use cases):** 20 older than 180 days, two approval spikes and a zero-approval gap. Approval dates only.
- **Models:** new `last_review_date`, `review_due_date`, `retirement_decision_date`, `migration_date` across the window; existing dates untouched.
- Two data-quality fixes found by tests: the baseline failure rate was lowered (from ~2.2% to ~1.2%) so healthy periods exist (2.2% sat below the 98% target), and an inverted recovery ramp was corrected.

### 3.5 Tests (56 new)
Window boundaries (30/90/180, inclusive, future exclusion, time zones, previous window), anchoring, trend helpers, synthetic determinism and scenario checks with frozen counts, executive metrics changing across windows without leakage, one window across every Platform Health component (trend equals cards), undated and empty windows, approval-only adoption, lifecycle date filtering, and pages rendering under all windows.

### 3.6 Real-data check
Windowed telemetry was run once against the real Parquet: all windows anchor on 2026-07-07 and 2,000,000 classified calls reconcile between the daily trend and the cards.

---

## 4. Phase 3 (follow-up work)

### 4.1 UX simplification pass (presentation only)
No formulas, classifications, sources or tests changed.

- **KPI drawers** now show only **What it means**, **Why it matters** and **Source**. Formula, denominators, FLOW-END/FLOW-ERROR rules, caveats, lineage and the badge note moved into a collapsed **Metric details** section. A one-line "why" exists for every KPI.
- **Executive:** "Today's focus" sentence became **Current focus** bullets of triggered findings only; empty state: "No priority findings identified in the selected scope."
- **Platform Health:** four primary cards (success rate, failed classified calls, unclassified events, True P95). Total classified calls, successful classified calls and daily-trend P95 moved to a "Supporting telemetry metrics" section. Order: reliability KPIs, most frequent errors, failures by model and provider, supporting telemetry. The unclassified notice became "33.3% of telemetry events could not be classified and are excluded from reliability calculations", with a **Learn more** expander.
- **Wording:** "High-risk replacements" became "Replacement candidates requiring review", subtitle "Alternative model may require additional assessment".
- **Colour hierarchy:** red only when the success rate is below target; green when met; amber for unclassified, dormant-status and replacement candidates; neutral for inventory and informational counts.

### 4.2 Time Window selector visibility fix
- **Symptom:** window logic worked, but users saw no control.
- **Root cause:** a global CSS rule hid every sidebar widget label, so the selector looked like an unlabeled dropdown ("6 Months") at the bottom of the scope list.
- **Fix:** the control became a visible radio (1 Month / 3 Months / 6 Months) directly under navigation with a "TIME WINDOW" heading and an indicator ("Time Window: 6 Months (180 days)"). The label-hiding rule now only restyles label text, so Region, Environment and Provider are labelled again, and scope order became Region, Environment, Provider.

### 4.3 Why numbers did not change with the window
Investigation, not a code change: real telemetry spans only 7 days (2026-07-01 to 07-07), so all windows include all of it (95.02% and 2,000,000 calls). Approvals (synthetic, because `ML_HUB_synthetic_5000rows.xlsx` is not a valid Excel file) did change (26, 31, 80). Lifecycle KPIs are snapshots by design.

### 4.4 Demo Scenario Data mode
A "Data mode" radio under the Time Window: **Real Data** (default) or **Demo Scenario Data**.
- Real Data changes nothing.
- Demo returns the existing deterministic synthetic telemetry (180 days, anchored 2026-10-17). No new random data; real Parquet is never read or modified, and the recorded source status is not overwritten.
- Scope: Executive telemetry metrics and Platform Health only. User Adoption, Model Lifecycle and Chargeback do not change.
- Visibility: an amber **DEMO SCENARIO DATA** box with a `synthetic scenario` badge, a `synthetic scenario` header badge, and a sidebar caption.

Example demo KPIs:

| Window | Classified-call success rate | Failed classified calls | Unclassified events | True P95 |
|---|---|---|---|---|
| 1 Month | 98.68% | 74,145 | 0 | 3.33 s |
| 3 Months | 98.55% | 244,039 | 132,228 | 3.30 s |
| 6 Months | 97.79% | 725,422 | 394,500 | 4.65 s |

In Real Data mode all three windows give identical values.

---

## 5. Where things live

| Concern | File |
|---|---|
| Classification, status, identity, user terms, source modes | `src/metrics.py` |
| Time windows and trend helpers | `src/timewindow.py` |
| KPI definitions, "why" lines, decision-brief rules | `src/insights.py` |
| Data loading, synthetic datasets, windowed telemetry, demo option | `src/data.py` |
| Query-tool catalog and metrics | `src/query_tools.py` |
| AI evidence and policy | `src/assistant_insights.py`, `src/agent.py` |
| Drawers, badges, CSS | `src/components.py` |
| Pages and sidebar | `app.py` |
| Definitions and contracts | `docs/METRIC_DEFINITIONS.md`, `docs/DATA_CONTRACTS.md`, `docs/LIMITATIONS.md`, `docs/VALIDATION.md` |
| Tests | `tests/test_phase1_metrics.py`, `test_ux_simplification.py`, `test_phase2_time.py`, `test_demo_mode.py` |

Unchanged throughout: authentication, quota, request locking, deployment files, and the older `nesgen-360-final-V0` folder.

---

## 6. Known limitations and what is deferred

- The classified-call success rate is **not** verified availability or deduplicated request success.
- No activity timestamps exist; approval dates are not activity. No "monthly active", "new this month" or dormancy-window metrics.
- Real telemetry covers 7 days, so windows are indistinguishable on real data; the 1,000,000 unclassified events have no timestamp and are excluded from windowed views. Demo mode exists for demonstrations.
- Windows are anchored per source, so different sources can end on different days (always displayed).
- AI tools keep their own `date_range` and do not follow the sidebar window or Data mode.
- Lifecycle windows are a caption only; inventory, status counts, chargeback and alerts are snapshots.
- `ML_HUB_synthetic_5000rows.xlsx` is still an invalid workbook, so User Adoption uses the synthetic fallback.
- The lifecycle page still says "Governed models"; `src/core.py` (legacy, unused) still contains a severity-based query; `tests/README.md` is an un-updated copy of the main README.
- No interactive browser validation, live Gemini, Docker, Windows batch or real-workbook validation was performed by the assistant.

**Not implemented (original later-phase list):** executive vertical insight sections, Leadership action queue changes, priority-card navigation, model risk-row styling, Model Evaluation Assistant, Error Analysis Assistant, replacement-model guardrail redesign, decommission-readiness formula redesign, broad chart redesign, new Gemini calls.

---

## 7. How to verify

From `nesgen-360-final-v1`:

```powershell
..\.venv\Scripts\python.exe -m pytest -q                       # full suite: 273 passed at the last run
..\.venv\Scripts\python.exe -m pytest -q tests/test_phase1_metrics.py tests/test_phase2_time.py tests/test_demo_mode.py
```

Manual check: open Platform Health, switch **Data mode** to Demo Scenario Data, then step through 1 / 3 / 6 Months and confirm the amber DEMO SCENARIO DATA box and changing KPIs; switch back to Real Data and confirm they stop changing.
