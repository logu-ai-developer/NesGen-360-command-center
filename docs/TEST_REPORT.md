> **Superseded (2026-10-23):** this is the V1.0 rebuild report. Current validated test counts are in the Phase History of `CLAUDE.md` (latest full run: 311 passed).

# Rebuild validation report
Date: 2026-10-20. Baseline: uploaded nesgen360-final-project-bundle.txt.

78 automated tests passed. Includes 20 AppTest checks: ten fallback pages and ten pages with mocked Excel-backed data (5,000 applications and a model source). Other tests cover generated synthetic Parquet fixtures, approved SQLite snapshots, exact dates, parameterized filters, row/payload limits, model-review evidence, SDK schema generation without network, registration, settings, data-folder replacement, scope/history and two model requests counted as two reservations.

Runtime: Python 3.12; pandas 2.3.3; NumPy 2.3.3; PyArrow 21.0.0; DuckDB 1.4.1; google-genai 2.29.0. Page tests used Streamlit 1.53.1 because the sandbox mirror lacked 1.66.0. requirements.txt retains streamlit==1.66.0. Exact full clean dependency installation was not validated.

Not tested: live personal API key, Gemini model availability, actual user workbooks/3M-row telemetry, Windows batch execution, Docker build, hard OS-level query sandbox, pixel-level visual comparison. Source-backed page checks use mocks, not the user's files.
