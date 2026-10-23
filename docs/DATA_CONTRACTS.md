# Data contracts
ML Hub requires Application ID and Region. Optional APM Name/Use Case Name, Environment, Platform, status fields, Models, Azure/AWS/GCP, Expected Daily Users, Business Value, Approval date, Functional Owner and RECERTIFICATION STATUS. Environment is not inferred from Platform. Missing optional values are Unknown/zero/NaT. monthly_requests uses supplied canonical values or expected_daily_users × 30.

Models require Model Name and Cloud Provider. Optional governance_stage, accountable_owner, evaluation_score, risk, lifecycle_status, migration_required, next_review_date, Retire Date, Model Family and Environment. Dates normalize to datetime64. Evaluation score is distinct from lifecycle risk.

Parquet mappings are in query_tools.py PARQUET_FIELDS. Direct missing sources return an error, not invented telemetry. Dashboard health can fall back explicitly. SQLite schema is initialized non-destructively; synthetic snapshots are seeded only if absent.

## V1.1 use-case contract (User adoption workbook)
Optional columns read by `get_apps()`; missing columns become `Unknown`/0, never invented:
`Use Case Stage` (Sandbox | Industrialized), `Segment` (B2B | B2C), `Active Users` (number), plus the existing `Application ID`, `APM Name`, `Region`, `LATEST STATUS OF USE CASE`, `Approval date`.
Note: `ML_HUB_synthetic_5000rows.xlsx` currently contains a NewRelic parquet file, not a workbook, so the app uses the 100-row synthetic fallback until a valid file is supplied.

## V1.1 Phase 1 additions (metric correctness)
Full definitions: `docs/METRIC_DEFINITIONS.md`.

- **Telemetry outcome** is resolved from `Body.Tracepoint`: `FLOW-END` = Successful, `FLOW-ERROR` = Failed, anything else (including a missing column) = Unclassified. Classified-call success % = Successful / (Successful + Failed) x 100; Unclassified % = Unclassified / Total events x 100. With no classified calls the rate is unavailable (`N/A` / `null`), not 0%.
- **Daily health frame** (`get_health`) now carries `requests` (all events), `successful_calls`, `failed_calls`, `unclassified_events`, `success_rate` (classified-call success %, NULL on a day without classified calls), `p95_latency_ms` (classified calls) and `cost`. `SeverityText` is no longer used to infer success.
- **Application ID** is the canonical key (`Application ID` in the ML Hub workbook). Rows with a missing or blank ID are kept and reported, not dropped or given invented IDs; repeated IDs collapse to the first row; names are display labels only.
- **Status** values are matched exactly against an allow-list (Active, Operational, Dormant, New, Onboarding); everything else is `Unknown`. **Stage** accepts Sandbox and Industrialized; everything else is `Unknown`.
- **Active users**: `get_apps()` records `attrs['active_users_basis']` = `synthetic estimate` (fallback), `reported` (workbook with `Active Users`) or `not supplied` (workbook without it). `observed` is reserved for a future activity source.
- **Models** carry `record_origin` (`catalog` or `locally registered`).
- `Use Case Stage`, `Segment`, `Active Users` remain optional workbook columns; missing values become `Unknown`/0 and are never invented.

## V1.1 Phase 2 additions (time)
- `get_telemetry(window=None)` takes an optional `TimeWindow`; results add `by_provider`, and stats add `undated_events`. Events without `Timestamp_1` are outside every window.
- Synthetic health is 180 days (was 90) and synthetic baseline failures are lower (~1.2%); synthetic approvals now include older rows, spikes and a zero-approval gap; synthetic models gain four lifecycle date columns. See `docs/METRIC_DEFINITIONS.md` sections 7–8.
- The workbook keeps `Approval date` as the only approval field; it is never treated as activity. Model workbooks may optionally supply any of `last_review_date`, `review_due_date`, `retirement_decision_date`, `migration_date`.
