# Review and Validation Record

Traceability for review cycles. This file records what was decided, not how the code works. Test results are real runs only; nothing here is estimated.

## Record 1: Phase 4 review cycle, 2026-10-23

### Scope
- Executive finding narrative.
- Model Inventory & Decisions governance clarity (Phase 4A) and its follow-up decisions.
- Model Evaluation Assistant (Phase 4B), first live Gemini run.
- Review of the "Avg illustrative readiness score" wording.
- Platform Health status assessment (inspection only).

### Implemented decisions
| Decision | Result |
|---|---|
| Findings show summary, impact and recommended action | Done. Rules, thresholds, routing, drawers unchanged |
| Risk, Review and Retirement shown as separate concepts | Done (chips and columns) |
| Attention order: High risk, Overdue review, Retirement candidate, Normal | Done |
| "Suggested candidate" wording; no weak pick | Done |
| Exclusions: same, retired, scheduled, approved retirement, High-risk, incomplete evidence | Done |
| Remove "Replacement candidates requiring review" card | Done; no metric redefined |
| Remove the evaluation score below 70 exclusion | Done; no numeric threshold remains |
| Keep `model_review_priority` unchanged | Done |
| Illustrative Decommission Readiness Score with weights and limitations | Done |
| Model Evaluation Assistant: evidence first, explicit Analyze, advisory notice, fallback | Done |

### Accepted feedback
- Executives need what happened, why it matters and what to do on the card itself.
- Model risk, review obligation, retirement status and replacement suitability must not share one indicator.
- Candidate suitability must use only the approved exclusion rules.
- AI may explain displayed evidence but is never the governance authority.

### Rejected feedback and interim choices
- Counting Medium-risk candidates in the replacement card: an interim choice made during implementation, rejected. The card was removed instead.
- Evaluation score below 70 as an exclusion rule: an implementation choice that was not an approved rule; removed.
- Removing the unused `model_review_priority`: rejected; kept for future review.

### Open review items
- **Readiness wording:** "Avg illustrative readiness score" is potentially misleading for executives. It is on Model Inventory & Decisions, not on the Executive page. Recommended label "Retirement preparedness (illustrative)" with a note that higher means easier to retire; not applied. Awaiting a decision.
- **Live Gemini check:** the first attempt reported `GEMINI_API_KEY is missing` because the app process did not have the key. The user then reported the app running with the key. The outcome of that run (four sections returned, grounding, advisory notice) has not been reported, so it is **not recorded as verified**.
- **Browser review:** not performed for any Phase 4 screen.
- **Stale caption:** the inventory panel caption still describes the older ordering.

### Validation results (full suite)
- Phase 4A: 301 passed, 1 failed (defect in a new test, fixed and re-run alone); then 303 passed after the follow-up decisions.
- Phase 4B: 311 passed.
- Not tested: a live Gemini response, any browser rendering.

### Future backlog (not scheduled)
- Phase 5A Platform Health UX: scope listed in `CLAUDE.md` (Roadmap), pending approval.
- Error Analysis Assistant, remainder of the Model Review Workflow, Scenario Planning: previously listed, no approved scope.

## Record 2: Platform Health assessment, 2026-10-23 (inspection only)

No code, test or documentation was changed by the assessment itself.

- Complete: PH-01, PH-02, PH-03, PH-09, PH-11.
- Partial: PH-04, PH-05, PH-06, PH-07, PH-08, PH-10, PH-12, PH-13, PH-16.
- Missing: PH-14, PH-15, PH-17 (no Error Analysis Assistant exists).
- Closed decisions respected: Services Healthy KPI stays removed; metric names and classification stay frozen; "P95 latency (true)" is a pending rename of an already approved name, not a new decision.
- Open point carried to 5A planning: a true model to provider to error drill-down may need a data-layer change, because the real-telemetry error query has no model column.
