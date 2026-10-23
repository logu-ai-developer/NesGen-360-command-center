# POC limitations
- No live Gemini/model availability test. The V0 model ID is retained, not endorsed.
- Token estimates are approximate. Provider quotas remain authoritative. Local counters do not cover other apps sharing the key/project.
- Query interruption is best effort, not an OS sandbox; Excel loading is not covered by the DuckDB timer.
- Execution labels confirm retrieval, not every generated sentence. Hallucination/prompt-injection risk is reduced, not eliminated.
- Supported structured-query scope dimensions are enforced; unsupported scope is disclosed. Summary tools do not support every dimension.
- Source confidentiality/synthetic classification requires operator review.
- Legacy dashboard telemetry requests/success fields count log events/non-error events, not deduplicated request success.
- Provider allocation from expected users is estimated; approval-date filters select cohorts, not consumption dates.
- Dormancy threshold is stored but does not reclassify workbook status without activity timestamps.
- No authentication/RBAC. Localhost only. Production identity, audit, privacy and managed secrets/storage remain future work.
- Streamlit 1.66.0 is pinned but unavailable from the sandbox mirror; page tests used 1.53.1. Windows, Docker and actual source files require local validation.

## V1.1 Phase 1 status (earlier statements above are superseded where noted)
- Telemetry rows without `Body.Tracepoint` are Unclassified and excluded from classified-call rates; the "non-error event" proxy is no longer used for the daily trend or Executive card. The classified-call success rate is still not verified availability or deduplicated request success.
- Dormant/New/Active labels are status-field counts. No validated last-activity timestamp exists, so no dormancy window, monthly activity or "new this month" claim is made. The stored dormancy threshold still does not reclassify anything.
- Active users are Estimated (synthetic) or Reported (workbook, unverified); no Observed active-user source is connected.
- "Services healthy 41 / 43" was removed. No service inventory, health formula, evaluation period, threshold or evaluation timestamp exists.
- Rows with no application ID are not counted as use cases; they are reported. Duplicate IDs collapse to the first row.
- Not yet implemented (later phases): 1/3/6-month duration filters, six-month datasets, executive section redesign, Leadership action queue changes, model risk-row styling, new AI assistants, decommission-readiness formula redesign.
- `src/core.py` (legacy, not imported by the app) still contains a severity-based success query; it was left untouched.

## V1.1 Phase 2 status
- Time windows are anchored to the latest non-future date of each source, so different sources can end on different days (shown on every page).
- The real telemetry spans 7 days (2026-07-01 to 07-07), so 1, 3 and 6 months give identical results on it; 1,000,000 unclassified events have no timestamp and are excluded from windowed views. The windowing is demonstrated by the synthetic datasets.
- Lifecycle windows are disclosed in a caption but do not filter the lifecycle KPIs. Status counts, inventory, chargeback and alerts are snapshots.
- No activity timestamps exist; approval dates are not activity.
- The AI assistant tools keep their own `date_range` parameters and do not follow the sidebar window.
