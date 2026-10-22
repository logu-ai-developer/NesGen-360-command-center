# Data contracts
ML Hub requires Application ID and Region. Optional APM Name/Use Case Name, Environment, Platform, status fields, Models, Azure/AWS/GCP, Expected Daily Users, Business Value, Approval date, Functional Owner and RECERTIFICATION STATUS. Environment is not inferred from Platform. Missing optional values are Unknown/zero/NaT. monthly_requests uses supplied canonical values or expected_daily_users × 30.

Models require Model Name and Cloud Provider. Optional governance_stage, accountable_owner, evaluation_score, risk, lifecycle_status, migration_required, next_review_date, Retire Date, Model Family and Environment. Dates normalize to datetime64. Evaluation score is distinct from lifecycle risk.

Parquet mappings are in query_tools.py PARQUET_FIELDS. Direct missing sources return an error, not invented telemetry. Dashboard health can fall back explicitly. SQLite schema is initialized non-destructively; synthetic snapshots are seeded only if absent.

## V1.1 use-case contract (User adoption workbook)
Optional columns read by `get_apps()`; missing columns become `Unknown`/0, never invented:
`Use Case Stage` (Sandbox | Industrialized), `Segment` (B2B | B2C), `Active Users` (number), plus the existing `Application ID`, `APM Name`, `Region`, `LATEST STATUS OF USE CASE`, `Approval date`.
Note: `ML_HUB_synthetic_5000rows.xlsx` currently contains a NewRelic parquet file, not a workbook, so the app uses the 100-row synthetic fallback until a valid file is supplied.
