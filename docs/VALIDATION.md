> **Superseded (2026-10-23):** this is the V1.0 rebuild report. Current validated test counts are in the Phase History of `CLAUDE.md` (latest full run: 311 passed).

# Rebuild validation report
Date: 2026-10-20. Baseline: uploaded nesgen360-final-project-bundle.txt.

78 automated tests passed. Includes 20 AppTest checks: ten fallback pages and ten pages with mocked Excel-backed data (5,000 applications and a model source). Other tests cover generated synthetic Parquet fixtures, approved SQLite snapshots, exact dates, parameterized filters, row/payload limits, model-review evidence, SDK schema generation without network, registration, settings, data-folder replacement, scope/history and two model requests counted as two reservations.

Runtime: Python 3.12; pandas 2.3.3; NumPy 2.3.3; PyArrow 21.0.0; DuckDB 1.4.1; google-genai 2.29.0. Page tests used Streamlit 1.53.1 because the sandbox mirror lacked 1.66.0. requirements.txt retains streamlit==1.66.0. Exact full clean dependency installation was not validated.

Not tested: live personal API key, Gemini model availability, actual user workbooks/3M-row telemetry, Windows batch execution, Docker build, hard OS-level query sandbox, pixel-level visual comparison. Source-backed page checks use mocks, not the user's files.

## V1.1 Phase 1 (metric correctness and honest labelling)
Earlier counts above (78, 94, 115, and 133 for the pre-Phase-1 local snapshot) are results from earlier snapshots and are kept for history.

Command: `..\.venv\Scripts\python.exe -m pytest -q` (from `nesgen-360-final-v1`). Python 3.12.10, Streamlit 1.66.0.
Result after Phase 1: **201 passed, 0 failed, 0 skipped** (133 existing + 68 new in `tests/test_phase1_metrics.py`; `test_v11_data.py` and `test_insights.py` assertions were updated for the renamed stats keys and the outcome-count columns).
Tests use mocked/synthetic sources (generated Parquet and workbook fixtures, Streamlit AppTest); no real workbook and no Gemini call. A guard fixture fails the test if Gemini is reached while pages render.
Not performed: an interactive browser session (no browser tool was available), live Gemini, Docker, Windows batch startup, actual-data validation of the invalid `ML_HUB_synthetic_5000rows.xlsx`. A headless `streamlit run` boot check returned HTTP 200 / health `ok`.

## V1.1 Phase 2 (time intelligence foundation)
Command: `..\.venv\Scripts\python.exe -m pytest -q` (from `nesgen-360-final-v1`). Python 3.12.10, Streamlit 1.66.0.
Result: **263 passed, 0 failed, 0 skipped** (207 existing + 56 in `tests/test_phase2_time.py`). Earlier counts (133, 201, 207) are results from earlier snapshots.
Sources: synthetic data and generated Parquet/workbook fixtures; no Gemini call (guard fixture). Additionally, windowed telemetry was run once against the real `data/NewRelic` Parquet: all three windows anchor on 2026-07-07, 2,000,000 classified calls reconcile between daily trend and cards, 1,000,000 undated events are disclosed.
Not performed: interactive browser session (no browser tool available); headless server boot check only.
