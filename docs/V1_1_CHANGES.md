# NesGen 360 V1.1: what changed so far

Repo: `nesgen-360-final-v1`. Status: all 133 tests pass. The app was not checked in a browser by me, and a "This page could not render" error you reported has not been reproduced (see the last section).

## 1. Mock (synthetic) data: what is real, what is mock

The app uses real files when they are valid, and generated synthetic data otherwise. Every card and page header shows a badge (`workbook`, `parquet`, `synthetic`) so you can see which one you are looking at.

| Domain | Source used today | Mock rows | Notes |
|---|---|---|---|
| Model lifecycle | **Real:** `Model details Page.xlsx` (32 models) | 32 only if the file is missing | Real file has no Sandbox stage |
| Platform health (daily trend, calls, errors, P95) | **Real:** `NewRelic/*.parquet` (3 files, 3M events) | 90 days of mock if no parquet | See section 3 |
| User adoption / use cases | **Mock:** 100 use cases | **100** | `ML_HUB_synthetic_5000rows.xlsx` is not an Excel file (it is a copy of a NewRelic parquet), so the app falls back |
| Chargeback | **Mock:** 3 fixed rows (Azure, AWS, GCP) | 3 | Unchanged from V1 |
| Alerts | **Mock:** 3 fixed rows | 3 | Unchanged from V1 |
| "Services healthy 41 / 43" | **Hardcoded** | n/a | Now labelled "Illustrative" |

### 1a. Use cases: 100 mock entries (changed)
`synthetic_apps()` in `src/data.py`. Was 114 rows, now **100** (you asked for 100 entries). Fixed random seed 360, so the data is identical on every run.

| Field | How it is generated |
|---|---|
| Status | 62 Active, 12 Dormant, 15 Onboarding, 11 New (fixed counts) |
| Region | Europe 37%, Asia 30%, Americas 19%, AMEA 14% |
| Environment | Production 63%, Pre-production 21%, Sandbox 16% |
| Provider split | Fixed on every row: Azure 43.7%, AWS 34.5%, GCP 21.8% |
| Expected daily users | Random 200 to 12,000 |
| Monthly requests / business value | Random 10K to 1.3M / 100K to 1.9M |
| Platform | Industrialization, Sandbox or NesGen API (random) |
| Names | 8 names repeating (e.g. Knowledge Search Engine, Recipe Assistant) |
| **`use_case_stage` (new)** | `Sandbox` if platform is Sandbox, otherwise `Industrialized` |
| **`segment` (new)** | B2B 60%, B2C 40% (random) |
| **`active_users` (new)** | Active or New rows: 30% to 90% of expected daily users. All other rows: 0 |

Limits: names repeat, so unique names are only 8. `active_users` is invented from expected users, so it is not a real measurement. B2B/B2C and stage are random labels, not business facts.

### 1b. Models: mock only when the workbook is missing (unchanged)
`synthetic_models()`: 32 fake models named like "GPT 3.0 Enterprise", seed 361, stages include "Sandbox validation". With the real workbook present none of this is used. New on top of both real and mock models (derived, not stored): see section 2.

### 1c. Telemetry mock (new, fallback only)
`_synthetic_telemetry()` is used only when no NewRelic parquet exists. It is derived from the 90-day mock health data:
- 6 models across Azure OpenAI, AWS Bedrock, GCP Vertex AI.
- Total calls = sum of mock daily requests (about 16M), failures = the mock failure share (about 364K).
- 4 error rows (503, 429, 400, 403) with split shares of failures.
- Unique clients per model: random 20 to 400.

With your real files this is not used. Real values: 2,000,000 classified calls, 1,900,309 successful, 99,691 failed (5.0%), plus 1,000,000 events with no success or failure marker.

### 1d. Unchanged mock data
90-day health series (one planted 8.6% failure day), 3 charge rows (AWS variance 7.4% is the planted exception), 3 alerts.

## 2. Derived values (computed, not source data)
Computed in `enrich_models()` in `src/data.py`:
- **Category:** Sandbox, Industrialized or Retirement, mapped from the governance stage text.
- **Unique clients:** distinct API client IDs seen in telemetry for the model. These are API clients, not named people. Real parquet gives about 1,650 to 1,970 per model.
- **Suggested replacement:** another model, same provider and family preferred, retiring later, not already retired or imminent; best evaluation score wins. A rule, not an owner decision.
- **Decommission readiness (0 to 100):** 40% evaluation score + 20 if a backup exists + up to 15 for the backup's risk (Low 15, Medium 8, High 0) + up to 15 for time to retirement + up to 10 for evidence status.

## 3. UI and logic changes
- **Explanations inside widgets:** every KPI card has an ⓘ drawer (what it is, how it is derived, caveat, Source → Dataset → Metric). The old explainer block at the bottom of the Executive page is removed. Definitions live in `KPI_INFO` in `src/insights.py` (31 entries).
- **Executive overview:** priority-action count, focus sentence, AI Findings and Recommended Actions are computed by fixed rules (availability under 98%, provider variance over 5%, models needing review, dormant apps over 10%, critical alerts). Not Gemini.
- **Model lifecycle:** Sandbox, with-backup, readiness cards; category filter; new table columns; "How is evaluation / readiness scored?" box.
- **Platform health:** Level 1 total, successful (green) and failed (red) calls; Level 2 failures by model; Level 3 top errors; true P95 over all calls next to the daily-trend P95, with an explanation box. Telemetry cards ignore the Environment filter.
- **User adoption:** use-case cards (onboarded, sandbox, industrialized, active users), B2B vs B2C by stage chart, table capped at 100 rows.
- **Fixes:** sidebar fixed width removed; the full traceback is now logged to the terminal when a page fails to render; `Use Case Stage`, `Segment`, `Active Users` columns are read from a real workbook when present (documented in `docs/DATA_CONTRACTS.md`).

## 4. Known data issues
- `ML_HUB_synthetic_5000rows.xlsx` is invalid (parquet saved as .xlsx). Adoption data stays mock until a real workbook is supplied.
- NewRelic part 1 (1M rows) has the LogAnalytics layout and no success/failure marker. The daily success-rate trend treats those rows as successful, which overstates success. The new call cards exclude them and show them as unclassified.
- In the telemetry, error codes and messages do not always match (for example code 500 with "Rate limit exceeded"). They are shown as logged.

## 5. Open item
You reported "This page could not render". I could not reproduce it with real data, all 10 pages, filter combinations and an admin login. To find it, start the app from `nesgen-360-final-v1`, open the failing page, and paste the traceback printed in the terminal.

## 6. Files changed
`app.py`, `src/components.py`, `src/data.py`, new `src/insights.py`, `docs/DATA_CONTRACTS.md`, tests (`test_final.py` and `test_rebuild.py` updated from 114 to 100; new `test_insights.py`, `test_v11_data.py`).
Note: the older `nesgen-360-final-V0` folder holds an earlier version of the same S1 work and is not what runs.
