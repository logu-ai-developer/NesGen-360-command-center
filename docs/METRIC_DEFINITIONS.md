# Metric definitions (V1.1 Phase 1)

All values below are computed deterministically in code (`src/metrics.py`, `src/insights.py`, `src/data.py`, `src/query_tools.py`).
No Gemini call is made to calculate a metric or to open a KPI information drawer. The in-card ⓘ text comes from `KPI_INFO` in `src/insights.py`.

## 1. Telemetry outcome classification

Every NewRelic event resolves to exactly one class, using `Body.Tracepoint` (`classify_outcome` / `outcome_sql` in `src/metrics.py`):

| Class | Rule |
|---|---|
| Successful | `Body.Tracepoint = 'FLOW-END'` |
| Failed | `Body.Tracepoint = 'FLOW-ERROR'` |
| Unclassified | anything else, including a missing `Body.Tracepoint` column, a null value, or a different spelling |

An event is **never** assumed successful because it lacks an error marker or because its `SeverityText` is `INFO`. Unclassified events are disclosed, not discarded.

| Quantity | Formula | Denominator |
|---|---|---|
| Total events | Successful + Failed + Unclassified | n/a |
| Classified calls | Successful + Failed | n/a |
| Classified-call success rate | Successful / Classified x 100 | Classified calls |
| Classified-call failure rate | Failed / Classified x 100 | Classified calls |
| Unclassified share | Unclassified / Total events x 100 | Total events |

Zero-denominator behaviour:

- No classified calls: success and failure percentages are **unavailable** (`N/A` in the UI, `null` in tool evidence), never 0% or 100%. The UI shows: *The selected records do not contain enough outcome classification evidence.* No reliability finding is generated.
- No events at all: volume is 0, all percentages are unavailable, no finding is generated.

The same helper feeds: Platform Health Level 1 cards, the daily classified-call success-rate trend (`health_daily.success_rate`, `successful_calls`, `failed_calls`, `unclassified_events`), failures by model, top errors, the Executive reliability finding, `get_platform_report`, `get_decision_brief`, the `new_relic` and `health_daily` query datasets (`classified_call_success_rate`, `successful_classified_calls`, `failed_classified_calls`, `unclassified_events`, `classified_calls`, and the `outcome` dimension).

The Executive card and the Platform Health card are **event-weighted** (sum of daily counts), not a mean of daily percentages. `average_daily_success_rate` (query tool) is the unweighted mean of daily classified-call percentages and is documented as such.

### Classified-call success rate versus non-error event rate

| | Classified-call success rate | Non-error event rate |
|---|---|---|
| Field | `Body.Tracepoint` | `SeverityText` |
| Query metric | `classified_call_success_rate` | `non_error_event_percent` |
| Denominator | Successful + Failed | events that carry a severity |
| No marker/severity | Unclassified (excluded) | excluded |

Neither is verified end-to-end availability or deduplicated request success. They must not be compared directly.

Other telemetry notes: the Level 2 table lists classified calls only (missing model or provider is shown as `Unknown`, so it reconciles to Classified calls). True P95 is over classified calls; the daily-trend P95 is a percentile of daily P95s over classified calls.

## 2. Users: expected, estimated, reported, observed

| Term | When used | Meaning |
|---|---|---|
| Expected daily users | workbook `Expected Daily Users` | planning figure; never called active users |
| **Estimated active users** | synthetic fallback | generated from expected users; *not observed identities or measured platform activity* |
| **Reported active users** | workbook with an `Active Users` field | supplied by the source; measurement period, identity definition and deduplication are not verified by the application. If the workbook has no such field the card shows `N/A` |
| **Observed active users** | not available in this prototype | requires an activity timestamp, a user/client identity, a reporting period and a deduplication rule |

## 3. Stage, status, approval and activity are different things

| Concept | Field | Metric names |
|---|---|---|
| Portfolio stage | `use_case_stage` | Sandbox use cases, Industrialized use cases |
| Portfolio status | `status` (normalized) | Active-status, Dormant-status, New-status, Onboarding-status use cases |
| Approval in a window | `created_date` (`Approval date`) | *Newly approved use cases* (only inside an explicit period; used by `get_onboarding_trend`) |
| Activity in a window | none validated | not calculated; no "monthly active" or "no use in 30 days" claim is made |

Status normalization (`normalize_status`): trim, collapse whitespace, case-fold, then **exact** match against the allow-list `active`, `operational` (alias of Active), `dormant`, `new`, `onboarding`. Anything else, including `Inactive`, `Not Active`, `Newly onboarded` and missing values, is `Unknown` and is preserved as such. Stage uses the allow-list `sandbox`, `industrialized`.

## 4. Canonical use-case identity

- The application / use-case **ID** is the canonical key. The name is a display label; repeated names never merge use cases.
- Rows sharing an ID collapse to the **first row** (documented deduplication rule). The number of surplus rows is reported as the duplicate canonical-ID count.
- Rows with a missing or blank ID are **preserved** in the data and reported as `missing_id_rows`; they are not counted as use cases and no ID is invented. Row counts are only shown when labelled as rows (`application_rows`).
- Portfolio counts, stage, status, region and segment aggregations, the Executive Active-status card, the dormant-status finding and the AI tools all use the canonical set.
- Reconciliation (`canonical_use_cases` metadata, shown in the User Adoption expander): total canonical use cases, count by stage, count by status, unknown status count, duplicate-ID count, missing-ID rows. Stage counts and status counts are separate dimensions; each sums to the canonical total.

## 5. Source-mode vocabulary

`workbook`, `parquet`, `synthetic fallback`, `synthetic scenario`, `derived from workbook`, `derived from parquet`, `locally registered`, `unclassified telemetry present`.

- *synthetic fallback*: generated because a compatible source could not be loaded.
- *synthetic scenario*: intentionally fixed demonstration records (chargeback, alerts, and the Priority-actions card that depends on them).
- *derived from workbook / parquet*: calculated from those records (for example model backup and readiness).
- *locally registered*: created through the local POC model-registration workflow (`record_origin = 'locally registered'`).
- *unclassified telemetry present*: shown when telemetry contains Unclassified events.

A badge shows data origin only. It does not indicate freshness, data correctness, confidentiality approval, production status, a live integration or source certification. Each KPI drawer says so.

## 6. Removed or renamed KPIs

| Before | After |
|---|---|
| Platform availability | Classified-call success rate |
| Governed models (Executive) | Models in inventory |
| Monthly active apps / Monthly active use cases | Active-status use cases |
| New this month | New-status use cases |
| Dormant use cases ("No use in 30 days") | Dormant-status use cases |
| Active platform users | Estimated / Reported active users |
| Total API calls / Successful calls / Failed calls | Total / Successful / Failed classified calls |
| Daily success rate | Classified-call success rate (daily trend: "Daily classified-call success rate (%)") |
| Services healthy 41 / 43 | **Removed.** It was a hardcoded illustration, not derived from a service inventory, health formula, evaluation period, threshold or timestamp. Nothing replaces it in Phase 1; the AI policy states that no service-health inventory exists. |
| Priority actions (AI tool value `3`) | Count of current decision-brief findings |

Lifecycle page labels (for example "Governed models") are unchanged in Phase 1.

## 7. Time windows (V1.1 Phase 2)

One module, `src/timewindow.py`, defines every period. Pages and tools do not compute their own dates.

| Sidebar option | Definition | `window_label` |
|---|---|---|
| 1 Month | 30 days | Last 30 days |
| 3 Months | 90 days | Last 90 days |
| 6 Months (default) | 180 days | Last 180 days |

Fixed day counts, never calendar months. `resolve_window` returns `window_start`, `window_end`, `window_days`, `window_label`. Both ends are inclusive, so a window covers exactly `window_days` calendar days. Dates after `window_end`, missing dates and unparseable dates are outside every window. `previous_window` is the equally long window ending the day before `window_start` (used only for trend direction).

**Anchor.** `window_end` is the latest non-future date of the source being windowed (telemetry: event timestamp; approvals: approval date; lifecycle: review/retirement/migration dates), not the wall clock. This keeps windows on real data that is not current and keeps synthetic data deterministic. The end date is always shown. Forward-looking planning dates (`next_review_date`, `retire_date`) never set the anchor.

**What is windowed.**

| Area | Date field | Windowed |
|---|---|---|
| Platform Health (cards, True P95, daily trend, failures by model and provider, most frequent errors) | event timestamp (`Timestamp_1`) | yes, one window for the whole page |
| Executive: Classified-call success rate, Unclassified events, Priority-action reliability finding, trend chart | event timestamp | yes |
| Executive and User Adoption: Newly approved use cases, approval-based trend | approval date | yes |
| Model lifecycle: lifecycle dates in window (shown in the caption) | last review / review due / next review / retirement decision / retire date / migration date | disclosed only; KPIs stay an inventory snapshot |
| Models in inventory, Active/Dormant/New/Onboarding-status counts, chargeback, alerts | none | no (snapshots, labelled as such) |

**Events with no timestamp.** They cannot be placed in any window. They are excluded from the windowed view and reported ("N events have no event timestamp…"); the un-windowed total still contains them. In the current Parquet the 1,000,000 unclassified rows have no timestamp.

**Newly approved use cases** = distinct canonical IDs whose approval date falls in the window. Approval dates are not activity; no activity metric is derived from them. Rows without a valid approval date are counted separately ("Use cases without approval date").

**Trend helpers** (deterministic, no model call): `period_counts` (zero-filled 7-day buckets from `window_start`; the last may be shorter), `rolling_counts`, `period_total`, `period_average`, `trend_direction` (`increasing` / `decreasing` / `stable`; relative tolerance 5%, or an absolute tolerance in percentage points for rates; `None` when a value is unavailable). The Executive success rate uses 0.5 points as "stable".

## 8. Synthetic time coverage (fixed anchor 2026-10-17, seeds 362–365)

- **Platform health** (`synthetic_health`, 180 days): healthy baseline (~1.2% failures); degraded period 100–125 days before the anchor; recovery 70–99; error spikes 150–151 and the planted 8.6% day at 4; latency spikes 140–142 (and ×1.5 in the degraded period); unclassified-event spikes 160–164 and 30–32.
- **Approvals** (`synthetic_apps`, 100 use cases): 20 older than 180 days, spikes at 100–106 and 12–16 days before the anchor, a zero-approval gap at 40–69. Approval dates only; no activity timestamps.
- **Lifecycle** (`synthetic_models`): new `last_review_date`, `review_due_date`, `retirement_decision_date`, `migration_date` within the 180 days. Existing `next_review_date` and `retire_date` are unchanged.
