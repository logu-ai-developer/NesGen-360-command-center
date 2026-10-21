# NesGen 360° Operations & Governance Command Center

**Colleague handover guide | Current V1 source snapshot | Local innovation-challenge POC**

> Start here if you are receiving this project for the first time. This guide describes the supplied code, including login, role checks, the audience-oriented AI Assistant and request locking. It does not certify production readiness or claim a fresh runtime test.
>
> Use synthetic or explicitly approved sanitized data only. AI responses require human review. Keep the app bound to localhost unless an approved deployment and identity review has been completed.

## Contents

1. [Purpose and audience](#1-purpose-and-audience)
2. [Implemented scope and boundaries](#2-implemented-scope-and-boundaries)
3. [Prerequisites](#3-prerequisites)
4. [First-time Windows setup](#4-first-time-windows-setup)
5. [Login, registration and roles](#5-login-registration-and-roles)
6. [Everyday startup and shutdown](#6-everyday-startup-and-shutdown)
7. [Repository structure and module responsibilities](#7-repository-structure-and-module-responsibilities)
8. [Data placement and contracts](#8-data-placement-and-contracts)
9. [Metric definitions and interpretation](#9-metric-definitions-and-interpretation)
10. [Configuration reference](#10-configuration-reference)
11. [AI Assistant operation and examples](#11-ai-assistant-operation-and-examples)
12. [Architecture and persistence](#12-architecture-and-persistence)
13. [Responsible AI, security and privacy](#13-responsible-ai-security-and-privacy)
14. [Tests and validation status](#14-tests-and-validation-status)
15. [Troubleshooting](#15-troubleshooting)
16. [Backup, reset and sharing](#16-backup-reset-and-sharing)
17. [Linux/macOS and Docker](#17-linuxmacos-and-docker)
18. [Demo walkthrough and handover checklist](#18-demo-walkthrough-and-handover-checklist)
19. [Known limitations and documentation reconciliation](#19-known-limitations-and-documentation-reconciliation)
20. [Production roadmap](#20-production-roadmap)

---

## 1. Purpose and audience

NesGen 360 brings model governance, platform health, application onboarding, provider allocation and chargeback scenarios into a single decision-support experience. The POC demonstrates how stakeholders can spend less time assembling disconnected reports and more time reviewing evidence and assigning actions.

Intended audiences:

- **NesGen Platform Team:** reliability signals, telemetry analysis, model readiness and governance review.
- **Regional Product Owners & Managers:** application onboarding, regional portfolios, expected reach and recertification.
- **Business Stakeholders:** prioritized issues, operational context and decision summaries.
- **Chargeback / FinOps reviewers:** provider invoice versus attributed-usage scenarios and unexplained amounts.

Stakeholder group is descriptive. It is not employment verification, a permission boundary or a regional data-access restriction.

## 2. Implemented scope and boundaries

### Pages

| Page | What colleagues can do | Important qualification |
|---|---|---|
| Executive overview | Review portfolio KPIs, reliability trends, weighted provider shares and the action queue | Some KPIs and priority scenarios are fixed demo values; not every sidebar filter applies to every panel |
| Model lifecycle | Filter models, inspect evaluation scores, risk, review dates and migration decisions | Evaluation score and lifecycle risk are different fields; review candidates are not verified provider retirements |
| Platform health | Inspect daily health trends and operational scenarios | New Relic log-event proxies are not verified end-to-end availability or deduplicated request success |
| User adoption | Inspect applications, status-based regional counts, expected users and recertification | Workbook status and approval dates do not establish observed activity or sustained adoption |
| Chargeback | Compare synthetic provider bills and attributed usage; apply a configured review threshold | No live MuleSoft or provider-billing connector is implemented |
| AI assistant | Ask questions through approved read-only local tools | Model calls require a valid OS API key, network access and an available configured model |
| Administration | Save settings, register local models, inspect source status and manage end-user activation | Admin only; writes are checked in backend actions as well as navigation |
| Solution design | Explain the target architecture and production roadmap | Target services are not automatically implemented integrations |
| Requirements | Inspect POC versus production commitments | Implemented means local prototype capability, not production approval |
| Demo & tests | Follow the demonstration flow and checklist | Checkboxes and KPI labels are not live proof that tests ran |

Admins can access all ten routes. End users do not receive the Administration route.

### Current implementation versus future integration

Implemented: local Excel adapters, local Parquet analysis, SQLite persistence, deterministic synthetic fallbacks, local username/password login, two roles, model registration, settings, read-only AI tools, per-model-request quota reservations and a per-session UI request gate.

Not implemented as live integrations: provider invoice ingestion, MuleSoft reconciliation, live New Relic/Log Analytics API collection, enterprise SSO/MFA, enterprise identity verification, production audit retention and managed operational storage.

**The supplied text bundle is a source snapshot, not a runnable repository by itself.** Colleagues need the complete current repository and any approved source data. The text bundle does not include the actual Excel/Parquet datasets or the operational database.

## 3. Prerequisites

- Python **3.11 or newer**. The Dockerfile uses Python 3.12; Python 3.12 is a practical baseline for a consistent handover.
- A writable project/data directory and permission to create a local virtual environment.
- Access to the approved Python package source for installation.
- PowerShell or Command Prompt on Windows. Administrator elevation is not part of the supplied setup steps, although company device policies can still restrict installation or network access.
- An approved `GEMINI_API_KEY` and model access **only if the AI Assistant will be used**. Dashboard pages can operate without a model API key using local data/fallbacks.
- A browser and local port **8505** available.

Pinned dependencies in the supplied `requirements.txt`:

```text
streamlit==1.66.0
pandas==2.3.3
numpy==2.3.3
plotly==6.3.1
duckdb==1.4.1
openpyxl==3.1.5
pyarrow==21.0.0
google-genai==2.29.0
pytest==8.4.2
tzdata>=2025.2
```

A virtual environment isolates dependencies; it does not grant network access, administrative privileges or model entitlement. Large Parquet scans depend on available RAM, CPU, storage speed and source schema. No hardware sizing or large-file performance guarantee is established by this handover.

## 4. First-time Windows setup

### Step 1: Extract the complete current repository

Use a fresh folder. Do not copy another person's `.venv`, API key or account database. Open a terminal in the directory containing `app.py` and `requirements.txt`.

```powershell
Set-Location "C:\path\to\nesgen-360-final"
py --version
```

If `py` is unavailable but Python is installed, use `python` in the environment-creation command below.

### Step 2: Create the virtual environment and install dependencies

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Using the explicit virtual-environment executable avoids PowerShell activation-policy issues. Activation is optional:

```powershell
.\.venv\Scripts\Activate.ps1
```

If activation is blocked, continue using `.\.venv\Scripts\python.exe`; changing company execution policies is not required for these instructions.

### Step 3: Place approved data, or start with synthetic fallback

See [Data placement and contracts](#8-data-placement-and-contracts). Missing workbooks and dashboard-health Parquet can fall back to synthetic data. Direct AI telemetry queries do not fabricate fallback telemetry.

### Step 4: Initialize operational tables

```powershell
.\.venv\Scripts\python.exe scripts\bootstrap.py
```

This creates the data/telemetry folders, operational/usage schema and missing synthetic snapshot tables. It does not drop existing tables. Authentication tables are initialized when the authentication module is used.

### Step 5: Create the first Admin locally

```powershell
.\.venv\Scripts\python.exe scripts\setup_admin.py
```

- Accept `admin_123` or choose another username.
- Choose a **new password of 15–128 characters** and confirm it.
- Password entry is hidden by the terminal prompt.
- No default Admin password is supplied.
- Setup refuses a second administrator and does not overwrite an existing account.
- If an active Admin already exists, use the existing authorized account. Do not delete the database to force setup.

Do not use passwords shown in examples, tests, screenshots or chat. The test-only credentials in `tests/` are not production/demo accounts created in your real database.

### Step 6: Configure the AI key locally, if required

The application reads `GEMINI_API_KEY` from the **OS environment**, not from `secrets.toml`. Use your organization's approved local secret-handling method. On Windows, a user environment variable can be configured locally without placing the value in the repository. After a persistent environment change, reopen the terminal/IDE so the new process inherits it.

Check presence without printing the value:

```powershell
if ($env:GEMINI_API_KEY) { "Key configured" } else { "Key missing" }
```

Do not print the key, paste it into the README, commit it, or include it in screenshots or a project bundle. Each colleague should use an approved credential rather than receiving the sender's key.

### Step 7: Validate and test

```powershell
.\.venv\Scripts\python.exe scripts\validate_environment.py
.\.venv\Scripts\python.exe -m pytest -q
```

The validator reports Python/package versions, configured model, key presence and source-file availability. It does **not** validate API-key authorization, model availability or data confidentiality. Tests use temporary databases and synthetic/mocked sources. Password hashing makes authentication tests slower.

### Step 8: Start the app

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port=8505 --server.address=127.0.0.1
```

Open **http://localhost:8505** and sign in. Without a configured API key, use the dashboard pages and defer the AI Assistant.

## 5. Login, registration and roles

### End-user registration

After the first Admin exists, select **Create demo account**:

1. Choose a username, for example `end_user_123`.
2. Enter a display name.
3. Select a stakeholder group.
4. Optionally enter an email address; it is not verified.
5. Choose and confirm a password of 15–128 characters.
6. Acknowledge the demo/confidentiality notice.
7. Create the account, then sign in.

Usernames are normalized to lowercase and must be 3–40 characters using letters, digits, underscores, dots or hyphens, with a letter/digit/underscore first. Registration always assigns `end_user`; users cannot self-select Admin. An existing username cannot be overwritten to reset its password.

### Permissions

| Capability | End user | Admin |
|---|---|---|
| View non-Administration dashboard routes | Yes | Yes |
| Use filters and AI Assistant | Yes, subject to shared limits | Yes, subject to shared limits |
| Save governance settings / disable AI | No | Yes |
| Register a local model | No | Yes |
| View demo user management | No | Yes |
| Activate/deactivate end-user accounts | No | Yes |
| Create another Admin through the UI | No | No |

All end users see the same permitted datasets. Region/provider filters are analytical scope, **not row-level security**. The Chargeback “Run reconciliation” button displays a scenario result; it is not a live financial write or invoice approval.

### Sessions and account management

- Inactivity timeout: **30 minutes**; absolute lifetime: **8 hours**.
- Expiry is checked on the next interaction/rerun. Already rendered content is not remotely erased at the exact timeout second.
- Logout revokes the token and clears Streamlit state, including chat history.
- Admin deactivation revokes the end user's existing sessions.
- The UI supports end-user activation/deactivation, not role promotion, account deletion or password recovery.
- There is no persistent “remember me” implementation.

Passwords use PBKDF2-HMAC-SHA256 with 600,000 iterations and a random 16-byte salt. Session tokens are random; only their hashes are stored in SQLite. Login errors are generic. Per-username and global login throttles are local POC controls, not a hardened identity gateway.

## 6. Everyday startup and shutdown

After first-time setup, use:

```powershell
.\run_local.bat
```

The Windows launcher:

1. Reuses `.venv`, or creates it using `py`/`python`.
2. Checks Python 3.11+.
3. Installs `requirements.txt`.
4. Runs bootstrap and environment validation.
5. Runs the test suite.
6. Starts Streamlit on `127.0.0.1:8505` only if earlier steps succeed.

**The launcher does not run `setup_admin.py` automatically.** If the login page reports first-time setup, run that command locally and refresh.

For a quicker restart after dependencies and tests are already checked, use the direct Streamlit command from Step 8. Stop the server with **Ctrl+C** in its terminal. Log out before handing the browser to another demo participant.

## 7. Repository structure and module responsibilities

```text
nesgen-360-final/
├── app.py
├── requirements.txt
├── run_local.bat
├── run_local.sh
├── Dockerfile
├── docker-compose.yml
├── README.md
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml                 # local non-secret settings; no API key
├── data/
│   ├── nesgen360.db                 # runtime state; sensitive after accounts exist
│   ├── Model details Page.xlsx
│   ├── ML_HUB_synthetic_5000rows.xlsx
│   ├── NewRelic/
│   │   └── *.parquet
│   └── LogAnalytics/
│       └── *.parquet
├── scripts/
│   ├── bootstrap.py
│   ├── setup_admin.py
│   ├── validate_environment.py
│   └── reset_demo_data.py
├── src/
│   ├── data.py
│   ├── provider.py
│   ├── storage.py
│   ├── config.py
│   ├── components.py
│   ├── auth.py
│   ├── auth_ui.py
│   ├── agent.py
│   ├── assistant_insights.py
│   ├── assistant_ui.py
│   ├── query_tools.py
│   ├── request_gate.py
│   ├── usage.py
│   ├── core.py
│   └── README_PATCH.md
├── tests/
│   ├── conftest.py
│   ├── test_agent_evidence_fix.py
│   ├── test_assistant_audience_patch.py
│   ├── test_final.py
│   ├── test_login_patch.py
│   ├── test_pages.py
│   ├── test_rebuild.py
│   ├── test_request_lock_patch.py
│   └── test_structured_queries.py
└── docs/
    └── architecture, data contracts, security, demo and validation notes
```

The `data/` tree describes expected runtime placement, not proof that these binary files were included in the text bundle. A `.venv/` and caches are generated locally and should not be shared.

| Module | Responsibility |
|---|---|
| `app.py` | Login gate, role-aware navigation, sidebar scope and ten page routes |
| `data.py` | Canonical Excel/health adapters, source-status recording and synthetic datasets |
| `provider.py` | Normalize provider weights and calculate allocated monthly request shares |
| `storage.py` | Settings, local model records, source status and protected Admin writes |
| `auth.py` / `auth_ui.py` | Credentials, sessions, permissions, registration, login/logout and user management |
| `agent.py` | Chat tool loop, evidence tracking, routing, final summarization and safe error classification |
| `assistant_insights.py` | Onboarding trends, chargeback/health reports and decision briefs |
| `assistant_ui.py` | Audience examples, chat state, request submission and incident messages |
| `request_gate.py` | Process-local, per-session overlap protection and frozen pending requests |
| `query_tools.py` | Approved dataset catalog, parameterized aggregate queries and bounded results |
| `usage.py` | Durable per-model-call reservations and question-level usage records |
| `config.py` | Environment/TOML/default configuration resolution |
| `components.py` | Shared page components, CSS and safe page-error display |
| `core.py` | Legacy compatibility helpers; not the current app's primary data/bootstrap path |

Do not substitute `src/core.py` bootstrap/reset functions for `scripts/bootstrap.py`. Legacy helpers have different schemas and behavior.

## 8. Data placement and contracts

### Locations and overrides

Default data root is the repository's `data/` directory. Optional environment overrides:

- `NESGEN_DATA_DIR`: approved data-root directory.
- `NESGEN_SQLITE_PATH`: operational SQLite database path.

Set overrides before starting the process; prefer absolute paths. A different SQLite path means a different set of accounts, settings, local models and quota counters. These path overrides are not model-supplied tool parameters.

### ML Hub application workbook

Filename: **`ML_HUB_synthetic_5000rows.xlsx`**. The adapter reads the first worksheet by default and trims column-header whitespace.

Required columns:

```text
Application ID
Region
```

Recognized optional fields:

```text
APM Name
Use Case Name
Environment
LATEST STATUS OF USE CASE
Use Case Status
Models
Functional Owner
Platform
RECERTIFICATION STATUS
Azure
AWS
GCP
Expected Daily Users
monthly_requests
Business Value
Approval date
```

Behavior:

- `APM Name` falls back to `Use Case Name`; status falls back to `Use Case Status`.
- Missing environment is `Unknown`. Platform is not silently treated as environment.
- Missing numeric fields become zero; expected daily users are clipped at zero.
- Missing `monthly_requests` is estimated as expected daily users × 30.
- Approval dates normalize to UTC-derived timezone-naive datetimes; invalid dates become `NaT`.
- Rows without an application ID are removed. Duplicate IDs are not automatically deduplicated.
- An invalid/empty source returns a complete synthetic fallback and records a rejection category.

### Model workbook

Filename: **`Model details Page.xlsx`**. Required columns:

```text
Model Name
Cloud Provider
```

Recognized optional fields:

```text
Model Family
governance_stage
accountable_owner
risk
lifecycle_status
lifecycle_risk
risk_reason
migration_required
next_review_date
Retire Date
Environment
evaluation_score
```

Use the exact `Retire Date` header for this snapshot. Dates normalize to datetimes; missing/unparseable values become `NaT`. Evaluation scores default to 75 if absent and are clipped to 0–100. Local Admin-registered models are appended from SQLite; registration does not edit the Excel workbook. Automatically generated workbook model IDs depend on row order and are not a durable source-system identity contract.

### Telemetry Parquet

Files are read from the immediate `NewRelic/` and `LogAnalytics/` folders using `*.parquet`; nested partition discovery is not implemented by these globs.

Approved direct-query mappings:

| Dataset | Canonical field | Source column |
|---|---|---|
| New Relic | event_time | `Timestamp_1` |
| New Relic | provider | `Attributes.BusinessKeys.provider` |
| New Relic | environment | `Attributes.BusinessKeys.environment` |
| New Relic | model | `Attributes.BusinessKeys.model` |
| New Relic | service | `Attributes.BusinessKeys.service` |
| New Relic | severity | `SeverityText` |
| New Relic | latency_ms | `Attributes.BusinessKeys.responseTime` |
| New Relic | total_tokens | `Attributes.BusinessKeys.total_tokens` |
| New Relic | total_cost | `Attributes.BusinessKeys.total_cost` |
| Log Analytics | event_time | `TimeGenerated` |
| Log Analytics | environment | `environment_s` |
| Log Analytics | model | `model_s` |
| Log Analytics | service | `service_s` |
| Log Analytics | latency_ms | `responseTime_d` |
| Log Analytics | total_tokens | `usage_total_tokens_d` |

`get_health()` uses New Relic daily aggregates only. It does not merge both telemetry systems. Log Analytics is available through its direct AI query dataset. Missing required health fields can trigger a synthetic dashboard fallback; missing direct-query fields return a query error or make the metric unavailable.

Environment labels are not universally mapped. For example, `PROD`, `Production`, `NONPROD` and `Pre-production` may not match across sources. Check the source's actual labels before interpreting an empty filtered result.

### Fallback and provenance

- Applications: valid workbook, otherwise deterministic synthetic fallback.
- Models: valid workbook, otherwise synthetic fallback; append local model registrations.
- Dashboard health: valid New Relic aggregate, otherwise synthetic fallback.
- Chargeback and alerts: existing synthetic scenario adapters.
- Direct `new_relic` / `log_analytics` queries: local Parquet only, **no synthetic telemetry substitution**.
- SQLite snapshots: read-only and separate from dashboard scenarios; do not silently merge them.

Admins should inspect **Administration → Data sources** after copying data. File existence alone does not establish successful loading, freshness, confidentiality classification or correctness. Some tools retain generic provenance labels even when the adapter records more detail.

## 9. Metric definitions and interpretation

### Provider allocation

For each application, nonnegative Azure/AWS/GCP weights are normalized to sum to one. If all weights are zero, the code tries provider-name matching; if no provider is recognized, it allocates one third to each provider.

```text
Allocated monthly requests for provider P
  = sum(application monthly_requests × normalized allocation for P)

Provider share (%)
  = provider allocated monthly requests / total allocated monthly requests × 100
```

The equal-split fallback is an assumption, not measured usage. If monthly requests came from expected users × 30, the provider chart is also an estimate. Approval-date filtering selects application cohorts; it does not measure consumption during that date window.

### Onboarding versus adoption

The AI trend tool counts approval-date rows and distinct application IDs separately. It does not infer actual active users from expected users. Portfolio totals are separate from window totals. Daily, weekly and monthly buckets include zeros; boundary weeks/months can be partial.

- “Last N days” in the dedicated onboarding tool ends **today UTC**, inclusive.
- “Latest available N days” in that tool ends at the latest **non-future** approval date.
- Future-dated approvals are excluded and counted in a warning.
- No matching rows means no matching records in this source, not proof that no real-world onboarding occurred.

The general structured-query tool has different behavior: its omitted `as_of` defaults to `latest`, and its generic latest anchor can include future source dates. Prefer the dedicated onboarding examples for the documented non-future behavior; inspect returned date metadata for custom queries.

### Health

New Relic `requests` counts log events. `success_rate` is the non-ERROR/FATAL event percentage in the dashboard adapter, not verified availability. Null severity handling differs between the dashboard adapter and direct-query metric. A mean of daily percentages is unweighted; maximum daily P95 is not P95 over all events. The legacy page's P95 display is also derived from daily P95 values, not recomputed from raw events.

### Chargeback and alerts

Unexplained amount is provider bill minus attributed usage. The review rule compares the **stored variance percentage** with the configured threshold using `>`; it does not recalculate a weighted overall variance. The UI displays dollar-style labels, while the AI tool does not independently verify currency. Current chargeback records are scenarios, not live invoices or verified MuleSoft records.

Open scenario alerts have no verified event timestamp. Do not describe the 8.6% failure or 7.4% variance scenario as an incident that occurred today without timestamped evidence.

### Model-review candidates

The named review tool selects candidates matching any of:

- High dashboard risk.
- A lifecycle status containing “review”.
- Next review date reached.
- Migration marked `Yes` or `Assess`.

These are POC review rules, not a provider deprecation determination or failed-evaluation verdict. Results are capped at 30 models and 12,000 UTF-8 bytes. Check truncation metadata.

## 10. Configuration reference

### Precedence

For non-secret settings, `src/config.py` resolves:

```text
OS environment variable → .streamlit/secrets.toml → DEFAULTS in src/config.py
```

Integer settings must contain valid integers. A malformed TOML file or invalid value can stop startup. The API key is handled separately through the OS environment.

The current bundle contains `.streamlit/secrets.toml`, but does **not** contain a `secrets.toml.example` section. Do not rely on an older README's copy-from-example command unless that file exists in the repository you received. You can create a local TOML using this non-secret reference:

```toml
GEMINI_MODEL="gemini-3.5-flash-lite"
AGENT_REQUESTS_PER_MINUTE=8
AGENT_REQUESTS_PER_DAY=300
AGENT_TOKENS_PER_MINUTE=100000
AGENT_MAX_INPUT_TOKENS=6000
AGENT_MAX_OUTPUT_TOKENS=600
AGENT_MAX_TOOL_ROUNDS=6
AGENT_MAX_HISTORY_MESSAGES=6
AGENT_MAX_RETRIES=0
AGENT_COOLDOWN_SECONDS=8
AGENT_REQUEST_TIMEOUT_SECONDS=30
```

The timeout is supplied by `DEFAULTS` in the current bundle even though it is absent from the bundled TOML. The model string is the configured identifier in the supplied code, **not independently verified model availability**. Retain the identifier approved and working for your project; do not uppercase or otherwise transform it for API calls.

| Setting | Current value | Scope / meaning |
|---|---:|---|
| `AGENT_REQUESTS_PER_MINUTE` | 8 | Rolling 60-second local model-request reservations, shared by users of this DB |
| `AGENT_REQUESTS_PER_DAY` | 300 | Local daily model-request reservations, using America/Los_Angeles date |
| `AGENT_TOKENS_PER_MINUTE` | 100000 | Rolling local token reservations; approximate input plus output allowance |
| `AGENT_MAX_INPUT_TOKENS` | 6000 | Approximate input budget for each model request, including instructions, schemas, history and evidence |
| `AGENT_MAX_OUTPUT_TOKENS` | 600 | Output allowance per model response, not a total for the whole user question |
| `AGENT_MAX_TOOL_ROUNDS` | **6** | Tool-execution cycles per user question; up to **7 model requests** |
| `AGENT_MAX_HISTORY_MESSAGES` | 6 | Recent individual messages, not six complete conversations; content is bounded per message |
| `AGENT_MAX_RETRIES` | 0 | Configuration intent; current agent has no automatic retry loop and does not use this value to enable retries |
| `AGENT_COOLDOWN_SECONDS` | 8 | UI cooldown after a handled failure; a rejected submission during cooldown is not automatically queued |
| `AGENT_REQUEST_TIMEOUT_SECONDS` | 30 | SDK HTTP timeout in seconds; not a hard end-to-end deadline for all local loading/tool work |

A tool round can contain several local tool calls. With six rounds, one complex question can consume seven of the eight local model requests permitted in a rolling minute. Subsequent questions may hit RPM even if only one user is present. The final allowed model request has tools disabled to encourage summarization. The Python `ask()` default argument remains three rounds, but the current UI explicitly passes the configured value of six.

Input tokens are estimated from UTF-8 bytes/3. Displayed input/output totals accumulate across model requests, so the displayed total can exceed the per-request limit. Reservations retain the larger of reserved and actual usage in the minute budget. Failed/in-flight reservations count. Local limits are not provider quota guarantees, do not cover other applications sharing the API project and do not guarantee zero billing. No paid-provider fallback is implemented.

Other fixed code limits include 12 non-cached tool executions per question, 8 structured queries per question, 100 query-result rows, 12,000 result bytes and 100,000 dashboard/SQLite snapshot rows. The structured DuckDB query uses 256 MB / two threads and a best-effort 10-second interrupt timer. The separate dashboard health adapter uses a 512 MB setting. These are not hard OS-level isolation guarantees.

Admin settings saved in SQLite: chargeback threshold, dormancy days and AI-disabled flag. Dormancy days are stored but do not reclassify workbook statuses without activity timestamps.

## 11. AI Assistant operation and examples

### What happens when a question is submitted

```text
Explicit Send / Analyze action
  → freeze question, scope and model in a pending request
  → acquire per-session process-local gate
  → retrieve local evidence / approved tool results
  → reserve quota before each model request
  → Chat model requests allowlisted tools if needed
  → execute bounded local queries and reuse duplicate results
  → return narrative or a clearly labeled evidence-only fallback
  → append actual local tool/source footer
  → record usage and release the gate
```

The integration uses `client.chats.create()` and `chat.send_message()`. Hidden SDK automatic function execution is disabled; the application controls the function loop and counts each model request. Metadata-only calls do not count as factual data retrieval.

The 4:1 page layout has chat on the left and audience-specific examples on the right. Changing Audience or Suggested question does **not** submit a model request. During a request, Send, Analyze, Audience, Suggested question and Clear are disabled. The pending request is consumed before the model call so a widget rerun cannot replay it automatically.

The gate is **per session and per Python process**, not a global queue, distributed lock or background job system. Different sessions can run concurrently subject to the shared SQLite quotas. An interrupted UI run may leave provider completion unknown; no automatic replay is attempted.

### Questions to try

**Platform Team**

```text
What requires attention today in Platform health?
Which models require governance review?
Show platform health summary.
Using New Relic, compare event counts and P95 latency by provider for the latest available seven days.
```

**Regional Product Owners & Managers**

```text
What was the onboarding trend in the last 10 days?
What was the onboarding trend in the last 90 days?
What was the onboarding trend in the latest available 90 days?
Show weekly onboarding approvals for Europe over the last 90 days.
Count applications by region and recertification status.
```

**Business Stakeholders**

```text
What requires action today?
Which provider has the highest consumption?
Summarize the top operational, governance and reconciliation issues requiring a decision.
```

**Chargeback / FinOps**

```text
Using Chargeback, compare provider invoices and attributed usage.
Which providers exceed the configured reconciliation threshold?
Show unexplained amounts by provider.
Is this reconciliation based on live MuleSoft records or a synthetic scenario?
```

Exact supported templates can prefetch evidence locally before the first model request. Other questions use model-selected structured tools and may require more calls. Examples are not a promise of available data. New Relic questions require compatible Parquet. Explicit Chargeback questions are source-restricted by a keyword-based rule; nuanced cross-source questions still need review.

### Scope and sources

The sidebar passes provider, region and environment to the agent. Supported structured-query dimensions are enforced locally; unsupported scope is reported in structured results. Not every summary propagates all unsupported-scope metadata. Do not assume every KPI or answer reflects all three filters.

Approved query datasets:

```text
applications
models
health_daily
provider_usage
charges
alerts
sqlite_charges
sqlite_alerts
new_relic
log_analytics
```

Auth/profile/session tables are not in the query catalog. Arbitrary SQL, model-supplied file paths, raw telemetry-message exports, filesystem execution and agent mutations are not tools.

The “Verified local tools” footer means local data tools executed. It does **not** prove every generated sentence is correct. A bounded evidence-only fallback is not a completed model narrative. Check dates, source mode, filters, units and truncation before acting.

## 12. Architecture and persistence

```text
Local Excel workbooks ──┐
Local Parquet files ────┼→ Canonical adapters / DuckDB aggregates
Synthetic scenarios ───┘                ↓
                           Streamlit pages + approved AI tools
                                        ↓
                              Human review and decisions

SQLite: local accounts, sessions, settings, registered models,
source status, usage reservations and separate synthetic snapshots
```

SQLite tables include:

- `local_models`, `app_settings`, `source_status`, `build_metadata`.
- `agent_usage`: question-level status, duration and token fields.
- `provider_calls`: individual model-request reservations and actual usage.
- `auth_users`, `auth_sessions`, `auth_attempts`.
- Bootstrap snapshots: `applications`, `models`, `platform_health_daily`, `provider_charges`, `operational_alerts`.

Snapshots are seeded only if absent; they are not automatically refreshed from Excel/Parquet. Current dashboard pages use adapters, not necessarily those snapshots. The database is not an import destination for millions of telemetry rows in this architecture.

Logs use safe categories, tool names, counts and incident IDs rather than raw prompts, keys or source records. Some schema fields such as `tool_names` exist but are not populated by every UI call; do not describe the current usage table as a complete production audit trail. Chat history lives in Streamlit session state rather than a durable chat-history table.

## 13. Responsible AI, security and privacy

### Controls present

- Login before page access and backend Admin checks for settings/model-registration writes.
- End-user-only self-registration and local first-Admin setup.
- Salted password hashes, hashed session tokens, expiry, logout and account deactivation.
- Allowlisted read-only AI tools, parameterized filter values and bounded query results.
- No arbitrary SQL, agent record changes, web browsing or paid-provider fallback.
- Explicit metric/source caveats, human review and confidentiality notices.
- Shared local quota reservations and per-session overlap protection.

### Boundaries to communicate in the challenge

- Local login is not enterprise SSO, MFA, identity proofing or a security certification.
- No email verification, password-recovery workflow, breach-password screening or production audit-retention policy is implemented.
- Account/global throttles can cause shared-demo denial of service; they are not a production gateway.
- People who can edit Python files or SQLite are trusted local operators and can bypass app controls.
- SQLite profile fields are not encrypted by this code. Protect local storage and backups.
- Approved aggregates and recent chat text are sent to the configured external model service when AI is used. Local source files are not automatically safe merely because the app labels the demo synthetic.
- Prompt instructions reduce unsupported output and prompt-injection risk; they do not eliminate them.
- Profiles are not automatically inserted into AI prompts, but users can still type personal/confidential data into chat. Do not do so.
- DuckDB interruption is best effort and does not cancel all Excel-loading work.
- Remote use needs HTTPS, an approved identity/deployment design and privacy/security review. Do not expose this directly to the internet.

## 14. Tests and validation status

Run the complete suite from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Or run focused groups:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_login_patch.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_pages.py tests/test_rebuild.py tests/test_final.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_agent_evidence_fix.py tests/test_assistant_audience_patch.py tests/test_structured_queries.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_request_lock_patch.py
```

Coverage in the supplied tests includes date boundaries, future approvals, source routing, provider weighting, SQL-like input rejection, generated Parquet fixtures, result limits, persistence, roles, session expiry, request locking and mocked model calls.

`tests/conftest.py` redirects operational/source paths to temporary locations. Legacy dashboard tests use an explicit test Admin and a test-only gate replacement; login tests exercise the real gate. Those fixtures are not a production login bypass. The suite is not a live model integration or actual-data validation run.

### Historical reports versus this snapshot

Bundled reports record earlier milestones: **78** rebuild tests, **94** AI-update tests and **115** login-update tests. Those are historical results, not a fresh result for this exact bundle. The current source adds request-lock tests and other edits. This README was prepared by source review only; no new pass count is claimed.

Earlier page reports used Streamlit **1.53.1** because the sandbox mirror lacked pinned **1.66.0**. Exact clean installation of the current requirements, live model access, actual user datasets, Windows interactive setup, Docker execution and production security were not established by those reports. Run and record your local result before the demo.

## 15. Troubleshooting

### Python is not found, but `py --version` works

Use `py -3 -m venv .venv`, then the explicit `.venv` executable. Do not copy an old virtual environment. If neither launcher works, install/use an approved Python runtime through your organization's process.

### PowerShell blocks activation

Use `.\.venv\Scripts\python.exe` directly. Activation is optional; do not change company policy just to run the app.

### Dependency installation fails

Confirm Python version, approved package index, proxy and network access. Do not silently change pinned versions and claim the original validation still applies. Record any approved dependency changes and rerun tests. Streamlit 1.66.0 was unavailable from the earlier sandbox mirror; that is not proof it is unavailable in your environment.

### First-time setup appears on the login page

Run `scripts/setup_admin.py` with the same Python environment and data/DB path used by the app. Refresh afterward. The launcher does not create an Admin automatically.

### Admin already exists / password forgotten

Setup intentionally refuses another Admin. Use the authorized account or a controlled local recovery process. Do not delete the operational DB as a shortcut: it also contains settings, models and usage records. No self-service password reset is implemented.

### Sign-in fails after repeated attempts

Wait for the local throttle window/block to expire, then verify credentials. Usernames are case-normalized; passwords are not. An inactive account cannot log in. Do not bypass throttles by modifying the DB during a shared demo.

### API key missing or authentication rejected

Check key presence without printing it, restart the terminal/IDE after environment changes and confirm the model/project entitlement. The key must be in the OS environment. A valid-looking model string or key-presence check does not establish authorization.

### Network reset / WinError 10054

The UI classifies connection-reset errors as network failures and records a safe incident ID. Check the approved network/proxy path, wait for cooldown and retry deliberately once. No automatic retry or paid fallback is attempted. Do not paste keys or full sensitive exception dumps into support messages.

### Quota or input-budget warning

A question can use several model requests. With six rounds, up to seven requests can be consumed. Wait for the rolling window, clear conversation to reduce context, or narrow the question. Raising tool rounds does not raise RPM/RPD/provider limits. Provider-side limits remain authoritative.

### Audience changes appear to do nothing

This is intentional: selecting an audience or question only changes examples. Click Analyze or submit chat to run a question. During execution, controls are disabled. Submissions during cooldown are rejected rather than automatically replayed; wait and submit again.

### No answer / evidence-only output

Check whether a data tool ran, whether the source exists and whether requested dimensions/metrics are supported. A model can fail to finish a narrative within its budget even after data retrieval. Evidence-only output is explicitly labeled; do not treat it as a complete analytical conclusion.

### Data unexpectedly looks synthetic

Check exact filenames, first-sheet headers, approved source labels and Administration → Data sources. A schema error can cause a complete dashboard fallback. Direct telemetry queries return errors instead of fallback data. Fixed scenario alerts and chargeback remain synthetic even when workbooks are present.

### Empty filtered data

Confirm environment/region/provider values in the source. Environment aliases are not universally normalized. A missing `Environment` column becomes `Unknown`; selecting Production can exclude all such rows. Not every dataset supports every sidebar dimension.

### Date window is empty

“Last N days” ends today UTC in the dedicated onboarding tool. The synthetic health series ends on **October 17, 2026** and does not roll forward daily. Ask for the latest available period explicitly if appropriate; do not silently substitute old data for today.

### Port 8505 is occupied

Stop your previous app terminal with Ctrl+C. To inspect the listener on Windows:

```powershell
Get-NetTCPConnection -LocalPort 8505 -State Listen |
    Select-Object LocalAddress, LocalPort, OwningProcess
```

Inspect the owning process before stopping anything. Alternatively start on another local port and use the matching browser address:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port=8506 --server.address=127.0.0.1
```

### Database locked / page cannot render

Avoid multiple writers, manual DB edits or backups while the app is running. Stop duplicate app instances and retry. For a page error, capture the page, filters and safe local diagnostic category. Do not assume the error handler successfully switched to fallback; it only displays a safe error for an unhandled render failure.

## 16. Backup, reset and sharing

### Before sharing with a colleague

Share the complete current code, this README, requirements, scripts, tests and approved demo data through an approved channel. Do not send only `app.py`; it imports the `src/` modules.

Exclude:

```text
.venv/
venv/
__pycache__/
.pytest_cache/
.git/
.env and secret-bearing local files
personal API keys or passwords
old ZIPs/backups
account-bearing nesgen360.db
unapproved source data or telemetry
```

Review `.streamlit/secrets.toml` before sharing. The current bundle uses it for non-secret settings, but the filename alone does not guarantee future contents are safe. Prefer a sanitized configuration example for colleagues; this bundle does not include one automatically. Inspect `.gitignore`/`.dockerignore` in the actual repo; they were not included as sections in the supplied text snapshot, so exclusion rules were not verified here.

Do not distribute your populated SQLite DB. A colleague can run bootstrap and create a new Admin locally. If sharing an intentionally sanitized DB, review its tables first and ensure no accounts, session hashes, profiles, confidential records or unwanted usage history remain. Never remove your working DB just to prepare a handover copy.

### Backup and data replacement

Stop the app before copying the SQLite file. Back up approved workbooks/Parquet and the operational DB separately. Preserve the DB if accounts, settings and local models must survive. Replacing the whole data folder with one lacking the DB creates a fresh operational state and requires Admin setup again. This also resets local quota history; it does not reset provider-side quotas and must not be used to evade them.

### Explicit demo reset

```powershell
.\.venv\Scripts\python.exe scripts\reset_demo_data.py --confirm-reset
```

This local operator command deletes **local model registrations and app settings only**. It retains source files, authentication records and usage counters. It is not a complete demo anonymization, account reset or password-recovery tool. The command is a trusted local maintenance action, not a public UI/agent operation.

## 17. Linux/macOS and Docker

### Linux/macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/bootstrap.py
.venv/bin/python scripts/setup_admin.py
.venv/bin/python scripts/validate_environment.py
.venv/bin/python -m pytest -q
.venv/bin/python -m streamlit run app.py --server.port=8505 --server.address=127.0.0.1
```

After initial setup, `sh run_local.sh` runs installation, bootstrap, validation, tests and startup. Set the API key using an approved local environment mechanism before using AI.

### Docker Compose (optional; validate locally)

The supplied Compose file publishes `127.0.0.1:8505`, passes the OS API key/model and mounts `./data:/app/data`. The container listens on all interfaces internally, while the host port publication is localhost-only.

```bash
docker compose build
docker compose run --rm nesgen360 python scripts/bootstrap.py
docker compose run --rm nesgen360 python scripts/setup_admin.py
docker compose up
```

Use an interactive terminal for the Admin password prompt. Existing Admin setup is not repeated. The mounted DB retains local state. The Docker startup command runs bootstrap and Streamlit; it does not run the full test suite automatically.

The Dockerfile uses `COPY . .`. Verify effective `.dockerignore` rules before building so keys, account databases, `.venv`, unapproved data and backups do not enter image layers. Do not push an image until that review is complete. Docker build/run and remote deployment security were not validated by this README.

## 18. Demo walkthrough and handover checklist

### Suggested 5-minute story

1. Sign in as an end user and show that Administration is unavailable.
2. Open Executive overview and explain the unified decision view, source mode and estimate boundaries.
3. Inspect Platform health; identify the scenario signal without claiming a verified incident today.
4. Open Chargeback; compare scenario invoices/attributed usage and explain the configured threshold.
5. Inspect Model lifecycle; show a review candidate and the rule behind it.
6. Open User adoption; distinguish approval counts, status labels and expected users from observed activity.
7. Ask one short AI example. Show period, source/tool footer and human-review boundary. Keep a non-AI fallback ready.
8. Log out, then sign in as Admin to demonstrate protected settings/model registration if time permits.

Do not memorize fixed application/model totals as acceptance criteria; valid workbook sources and local registrations change them. The 8.6% reliability and 7.4% variance values are demo scenarios, not proof of current production incidents.

### Colleague acceptance checklist

- [ ] Complete current repository received, not only a text bundle or patch.
- [ ] Python version and dependencies installed in a fresh `.venv`.
- [ ] Approved data placement and source schema confirmed.
- [ ] Bootstrap completed; first Admin created locally.
- [ ] End-user registration, login, logout and role restrictions checked.
- [ ] API key configured privately, or AI explicitly excluded from the demo.
- [ ] Exact working model ID and current six-round setting understood.
- [ ] All accessible pages checked; Admin checks Administration separately.
- [ ] Local tests run and results recorded for this exact snapshot.
- [ ] AI audience selection does not submit a request; explicit submission works once.
- [ ] Date anchors, fallback/source mode and metric caveats understood.
- [ ] No secrets, account DB, `.venv` or unapproved datasets included in the shared package.
- [ ] Localhost-only demo and non-production status clearly stated.

## 19. Known limitations and documentation reconciliation

This README follows executable code in `nesgen360-final-project-bundle-v1.txt` when older documentation conflicts. It changes documentation only, not application behavior.

| Older statement / display | Current interpretation |
|---|---|
| “No authentication/RBAC” in older README/security notes | Local login and Admin/end-user checks are implemented; enterprise identity and granular data authorization are not |
| “No live LLM” in the older demo script | A real Chat API integration exists and can run with a valid key; historical automated model tests were mocked |
| Three tool rounds in older docs / UI help | Current TOML and `config.py` set **six**, allowing up to seven model requests per question |
| 78 / 94 / 115 tests passed | Historical milestones, not a fresh pass count for this request-lock snapshot |
| Copy `secrets.toml.example` | That example is not included in this text snapshot; create sanitized non-secret config if needed |
| All sidebar filters apply globally | Application/model/health panels and tools support different dimensions; inspect each source and returned scope |
| “Monthly active”, “New this month”, “Dormant 30 days” | Current page logic uses status-string matches, not a validated activity/date-window calculation; “Inactive” can also match a substring search for “Active” |
| Availability / request success | Telemetry fields are log-event proxies; no verified end-to-end availability calculation is established |
| “P95 latency” across the period | Some page calculations aggregate daily P95 values; use direct event-level P95 for that distinct metric |
| “Today’s focus” / fixed priority count / 41 of 43 services | Scenario or fixed UI values, not universally recomputed live facts |
| Dollar labels / “NesGen / MuleSoft” in Chargeback | Presentation labels for a synthetic scenario, not verified currency or a live MuleSoft integration |
| Data/source labels certify sanitization | Operators must verify classification and approval; the code cannot certify arbitrary files |

Additional implementation cautions:

- The UI limit help still illustrates three rounds; Administration's 300/day and 100,000/minute denominators are hard-coded displays and can become stale if configuration changes.
- `source_status` records the latest adapter load, not a freshness SLA or a full lineage/audit history.
- Some unsupported-scope metadata is not surfaced by summary tools. Model page filtering is primarily provider plus its local risk/stage/search controls; not all global filters are applied.
- The request gate is not distributed and does not serialize all users. Navigating away or interrupting a run can leave provider completion unknown.
- The current logout CSS is key-scoped in `src/auth_ui.py`: yellow/red normally and blue/yellow on hover. It is a UI customization, not a permission control; CSS/DOM behavior can vary with Streamlit versions.
- Large telemetry files, actual workbook contracts, exact dependency installation and deployment behavior need local validation. Do not infer a successful 3M-row run from synthetic fixture tests.

## 20. Production roadmap

Before a shared pilot or production use:

1. Agree on KPI definitions, ownership, source schemas, environment mapping and freshness SLAs.
2. Replace demo login with approved enterprise identity, MFA and granular authorization.
3. Use approved managed secret handling and a reviewed model/provider deployment.
4. Add governed ingestion for telemetry, onboarding activity and provider/MuleSoft billing evidence.
5. Replace scenario labels with measured, timestamped and reconciled data products.
6. Move operational state to approved managed storage with backup/recovery and access controls.
7. Add distributed concurrency control, production observability and complete audit/retention policies.
8. Perform privacy, Responsible AI, security, performance and operational-readiness reviews.
9. Revalidate all documentation and tests against the actual deployment and datasets.

---

### Documentation basis

Prepared from the 47-file source snapshot `nesgen360-final-project-bundle-v1.txt`. Primary references are `app.py`, `src/config.py`, `src/data.py`, `src/provider.py`, `src/agent.py`, `src/assistant_insights.py`, `src/assistant_ui.py`, `src/request_gate.py`, `src/query_tools.py`, `src/auth.py`, `src/auth_ui.py`, `src/storage.py`, `src/usage.py`, startup/setup scripts and the supplied tests. Historical results are attributed to the bundled reports, not presented as a new validation run.

**Handover rule:** if a future code change alters setup, permissions, metrics, limits, data contracts or deployment behavior, update this README and rerun the relevant tests before sharing the repository again.
