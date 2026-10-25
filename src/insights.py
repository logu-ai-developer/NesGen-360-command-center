"""Rule-based decision brief and KPI definitions. Deterministic; needs no API key."""
from __future__ import annotations
import pandas as pd
from src.metrics import canonical_use_cases, health_outcomes

# Thresholds used by the decision brief (S1-008..S1-011); change here to retune findings.
AVAILABILITY_TARGET = 98.0
CHARGEBACK_THRESHOLD = 5.0
DORMANT_SHARE_THRESHOLD = 0.10
_ORDER = {'Critical': 0, 'High': 1, 'Medium': 2, 'Low': 3}


def _kpi(definition, formula, source, dataset, metric, caveat=''):
    return {'definition': definition, 'formula': formula, 'source': source, 'dataset': dataset, 'metric': metric, 'caveat': caveat}


KPI_INFO = {
    # Executive overview
    'classified_success': _kpi('Share of classified API calls that completed successfully. It is not verified end-to-end service availability, and events with no timestamp fall outside the selected window and are reported separately.', 'Successful classified calls / (Successful + Failed classified calls) x 100, summed over every event in the window. Unclassified events are excluded from the denominator and reported separately. N/A when there are no classified calls.', 'Platform health', 'health_daily', 'classified_call_success_rate', 'Classified means Body.Tracepoint is FLOW-END (successful) or FLOW-ERROR (failed); an event with neither is Unclassified and is never counted as successful. Target is 98% or higher. Not deduplicated request success.'),
    'models_inventory': _kpi('Models present in the model inventory for the selected provider.', 'Count of model rows; high-risk = rows with risk = High.', 'Model lifecycle', 'models', 'model_rows', 'Inventory presence does not prove a model is operationally available, approved, deployable or suitable.'),
    'active_status_use_cases': _kpi('Canonical use cases whose status field is Active. Reflects the status field, not measured activity.', 'Count of distinct use-case IDs whose normalized status is exactly Active (the source label Operational is treated as Active). Matching is exact after trimming and case-folding, so Inactive is not Active.', 'User adoption', 'applications', 'active_status_use_cases', 'Based on the status field, not measured activity. Rows without a use-case ID are not counted.'),
    'priority_actions': _kpi('Decisions that currently need leadership attention.', 'Number of rule-based findings: classified-call success rate below 98%, provider variance above 5%, models needing review, dormant-status use cases above 10%, open critical alerts.', 'Executive overview', 'alerts + charges + models + applications', 'decision_brief', 'Computed from the decision-brief rules; chargeback and alert inputs are fixed synthetic scenarios.'),
    # Model lifecycle
    'lifecycle_governed': _kpi('Models in the current filter selection.', 'Count of model rows after the risk, stage and search filters.', 'Model lifecycle', 'models', 'model_rows'),
    'industrialized': _kpi('Models approved to operate in production.', 'Count where stage = Industrialized.', 'Model lifecycle', 'models', 'model_rows'),
    'review_due': _kpi('Models whose evidence needs refreshing.', 'Count where lifecycle status contains Review.', 'Model lifecycle', 'models', 'model_rows'),
    'retirement': _kpi('Models that need a retirement or migration decision.', 'Count where migration_required is Assess or Yes.', 'Model lifecycle', 'models', 'model_rows', 'Candidates for a decision, not a confirmed provider retirement.'),
    # Platform health (outcome-based: Body.Tracepoint)
    'classified_calls': _kpi('API calls whose outcome is known (successful or failed).', 'Successful + Failed classified calls. Total events = Successful + Failed + Unclassified.', 'Platform health', 'new_relic', 'classified_calls', 'Unclassified events are excluded here and shown on their own card.'),
    'calls_success': _kpi('Classified calls that completed normally.', 'Count where Body.Tracepoint = FLOW-END; share = successful / classified calls x 100.', 'Platform health', 'new_relic', 'successful_classified_calls'),
    'calls_failed': _kpi('Classified calls that ended in an error flow.', 'Count where Body.Tracepoint = FLOW-ERROR; share = failed / classified calls x 100.', 'Platform health', 'new_relic', 'failed_classified_calls'),
    'calls_success_rate': _kpi('Share of classified calls that completed successfully. Not verified end-to-end service availability.', 'Successful classified calls / (Successful + Failed classified calls) x 100. N/A when there are no classified calls.', 'Platform health', 'new_relic', 'classified_call_success_rate', 'Unclassified events are excluded from the denominator, never counted as successful. Not deduplicated request success.'),
    'unclassified_events': _kpi('Telemetry events with no success or failure marker. Events with no timestamp are outside every time window and are listed separately as undated.', 'Total events - (Successful + Failed classified calls); share = unclassified / total events x 100.', 'Platform health', 'new_relic', 'unclassified_events', 'Typically LogAnalytics-layout rows without Body.Tracepoint. They are disclosed, not discarded and not assumed successful.'),
    'p95_latency': _kpi('Response time that 95% of classified calls stay under, taken per day.', '95th percentile across the daily P95 latency values, shown in seconds.', 'Platform health', 'health_daily', 'maximum_daily_p95_ms', 'A percentile of daily percentiles over classified calls, not the P95 across all calls.'),
    'request_volume': _kpi('Total log events in the window.', 'Sum of daily event counts (successful + failed + unclassified).', 'Platform health', 'health_daily', 'requests', 'Log events are counted; they are not deduplicated requests.'),
    'total_events': _kpi('All telemetry events in the window, classified or not.', 'Successful + Failed + Unclassified events.', 'Platform health', 'new_relic', 'events', 'Events with no timestamp are outside every window and are disclosed separately.'),
    'peak_daily_p95': _kpi('Highest single-day P95 response time in the window.', 'Maximum of the daily P95 latency values, shown in seconds.', 'Platform health', 'health_daily', 'maximum_daily_p95_ms', 'A daily value, not the P95 across all calls. Do not use it for SLA statements.'),
    'p95_true': _kpi('Response time that 95% of classified calls stay under.', 'QUANTILE_CONT(responseTime, 0.95) across all classified calls.', 'Platform health', 'new_relic', 'p95_latency_ms', 'Unlike the daily trend chart, this is the event-level P95 over every classified call, not a percentile of daily P95 values. Use it for SLA statements.'),
    # User adoption
    'use_cases': _kpi('Canonical use cases onboarded to the platform.', 'Count of distinct application / use-case IDs after the sidebar filters. Repeated IDs collapse to the first row; the use-case name is a display label only.', 'User adoption', 'applications', 'canonical_use_cases', 'Rows with no ID are preserved and counted separately, not invented as use cases.'),
    'uc_sandbox': _kpi('Canonical use cases in the Sandbox stage.', 'Count of distinct IDs where use_case_stage = Sandbox.', 'User adoption', 'applications', 'sandbox_use_cases', 'Stage is a portfolio stage, separate from status, approval and activity.'),
    'uc_industrialized': _kpi('Canonical use cases in the Industrialized stage.', 'Count of distinct IDs where use_case_stage = Industrialized.', 'User adoption', 'applications', 'industrialized_use_cases', 'Stage is a portfolio stage, separate from status, approval and activity.'),
    'adoption_new': _kpi('Canonical use cases whose status field is New.', 'Count of distinct IDs where normalized status = New.', 'User adoption', 'applications', 'new_status_use_cases', 'Status field only. Not "newly approved": that needs an approval date inside an explicit period.'),
    'dormant': _kpi('Canonical use cases whose status field is Dormant.', 'Count of distinct IDs where normalized status = Dormant.', 'User adoption', 'applications', 'dormant_status_use_cases', 'Status field only. No validated last-activity timestamp exists, so no inactivity window is claimed.'),
    'adoption_onboarding': _kpi('Canonical use cases whose status field is Onboarding.', 'Count of distinct IDs where normalized status = Onboarding.', 'User adoption', 'applications', 'onboarding_status_use_cases', 'Status field only.'),
    'newly_approved': _kpi('Canonical use cases whose approval date falls inside the selected time window.', 'Count of distinct IDs with Approval date between window start and window end (inclusive); trend compares with the equally long previous window.', 'User adoption', 'applications', 'canonical_use_cases', 'Approval-based trend: approval dates are not activity. Rows without a valid approval date are not counted. The window ends at the latest non-future approval date.'),
    'active_users_estimated': _kpi('Synthetic estimate of active users across canonical use cases.', 'Sum of active_users, generated from expected daily users by the synthetic fallback.', 'User adoption', 'applications', 'active_users', 'Synthetic estimate derived from expected users; not observed identities or measured platform activity.'),
    'active_users_reported': _kpi('Active users as supplied by the source workbook.', 'Sum of the workbook Active Users field across canonical use cases.', 'User adoption', 'applications', 'active_users', 'The application has not independently verified the measurement period, identity definition or deduplication rule. N/A when the workbook has no Active Users field.'),
    'active_users_observed': _kpi('Active users measured from an activity source.', 'Distinct user or client identities active in a stated reporting period, deduplicated.', 'User adoption', 'applications', 'active_users', 'Requires an activity timestamp, identity, reporting period and deduplication rule. No such source is connected in this prototype.'),
    # Chargeback
    'invoice': _kpi('Amount billed by the cloud providers.', 'Sum of provider invoice values for the period.', 'Chargeback', 'charges', 'provider_invoice', 'Fixed synthetic scenario.'),
    'attributed': _kpi('Cost the platform can attribute to applications.', 'Sum of platform-attributed usage values.', 'Chargeback', 'charges', 'attributed_usage', 'Fixed synthetic scenario.'),
    'unexplained': _kpi('Billed amount with no platform attribution.', 'Invoice minus attributed usage.', 'Chargeback', 'charges', 'unexplained_amount', 'Fixed synthetic scenario.'),
    'exceptions': _kpi('Providers whose variance exceeds the review threshold.', 'Count of providers with status = Review (variance above 5%).', 'Chargeback', 'charges', 'maximum_variance_percent', 'Fixed synthetic scenario.'),
    # V1.1 model lifecycle
    'lifecycle_sandbox': _kpi('Models still in sandbox or exploration.', 'Count where governance stage contains Sandbox or Exploration.', 'Model lifecycle', 'models', 'model_rows', 'The current model workbook has no sandbox stage, so 0 is expected for real data.'),
    'models_with_backup': _kpi('Models that have a suggested candidate.', 'Count of models with a derived candidate (same provider and family preferred). Never the same model, a retired, retiring or unsuitable model.', 'Model lifecycle', 'models', 'model_rows', 'A suggested candidate is derived by rule, not source data, and is not an approval or governance endorsement. Confirm with the model owner.'),
    'readiness': _kpi('Illustrative indicator of how prepared a model is for decommissioning.', '35 if a suggested candidate exists + up to 20 for candidate risk (Low 20, Medium 10) + up to 25 for time before retirement + up to 20 for evaluation evidence (Complete 20, Review due 10, Incomplete 0). Current-model quality is not included.', 'Model lifecycle', 'models (derived)', 'decommission_readiness', 'Illustrative, not authoritative: it does not measure migration effort, client impact or approval status.'),
}


# One-line "why it matters" per KPI for the executive drawer; formulas and caveats stay in KPI_INFO ("Metric details").
KPI_WHY = {
    'classified_success': 'Helps identify reliability issues that need operational attention.',
    'models_inventory': 'Shows how many models the platform team is tracking.',
    'active_status_use_cases': 'Shows how much of the portfolio is marked as in use.',
    'priority_actions': 'Tells leadership how many decisions are currently open.',
    'lifecycle_governed': 'Shows how many models match the current filters.',
    'industrialized': 'Shows how many models are cleared for production use.',
    'review_due': 'Flags models whose evidence needs refreshing.',
    'retirement': 'Flags models that need a retirement or migration decision.',
    'classified_calls': 'Gives the volume behind the reliability figures.',
    'calls_success': 'Shows the volume of calls that completed normally.',
    'calls_failed': 'Shows how many calls need investigation.',
    'calls_success_rate': 'Helps identify reliability issues that need operational attention.',
    'unclassified_events': 'Shows how much telemetry is outside the reliability figures.',
    'p95_latency': 'Shows how response time trends day by day.',
    'request_volume': 'Gives context for the size of the telemetry window.',
    'total_events': 'Shows the full telemetry volume behind the classification coverage.',
    'peak_daily_p95': 'Shows the worst single day for response time.',
    'p95_true': 'Shows the response time most users experience at worst.',
    'use_cases': 'Shows how many use cases the platform supports.',
    'uc_sandbox': 'Shows how many use cases are still being tried out.',
    'uc_industrialized': 'Shows how many use cases run in production.',
    'adoption_new': 'Shows how many use cases are recently registered.',
    'newly_approved': 'Shows the pace of onboarding in the selected period.',
    'dormant': 'Shows use cases that may need re-engagement or retirement.',
    'adoption_onboarding': 'Shows how many use cases are still being set up.',
    'active_users_estimated': 'Gives an indicative sense of reach in the demo data.',
    'active_users_reported': 'Gives an indicative sense of reach as reported by the source.',
    'active_users_observed': 'Would show measured reach once an activity source exists.',
    'invoice': 'Shows what the cloud providers billed.',
    'attributed': 'Shows how much of the bill the platform can explain.',
    'unexplained': 'Shows the part of the bill that needs reconciliation.',
    'exceptions': 'Shows providers that need a reconciliation review.',
    'lifecycle_sandbox': 'Shows how many models are still being validated.',
    'models_with_backup': 'Shows how many models have an alternative if retired.',
    'readiness': 'Helps prioritise which models can be retired safely.',
}
for _key, _why in KPI_WHY.items():
    KPI_INFO[_key]['why'] = _why


def executive_focus_bullets(items):
    """Short bullets for the Executive 'Current focus' box: only triggered findings, in severity order."""
    return [i['title'] for i in items[:5]]


def _item(severity, category, title, evidence, source, action, owner, summary='', impact='', recommended_action=''):
    # summary / impact / recommended_action are the one-sentence Executive card narrative (presentation only).
    return {'severity': severity, 'category': category, 'title': title, 'evidence': evidence,
            'source': source, 'action': action, 'owner': owner,
            'summary': summary, 'impact': impact, 'recommended_action': recommended_action}


def build_decision_brief(apps, models, health, charges, alerts):
    """Return findings sorted by severity. Every item carries evidence, source, action and owner."""
    items = []
    if health is not None and len(health):
        o = health_outcomes(health)
        # No classified calls means no measured success rate: say nothing rather than report 0% or 100%.
        if o['classified']:
            rate = o['success_pct']
            daily = pd.to_numeric(health['success_rate'], errors='coerce').dropna()
            worst = float(daily.min()) if len(daily) else rate
            if rate < AVAILABILITY_TARGET or worst < 92:
                sev = 'Critical' if worst < 92 else 'High'
                items.append(_item(sev, 'Reliability', 'Classified-call success rate below target',
                                   f'Classified-call success rate {rate:.2f}% (target {AVAILABILITY_TARGET:.0f}%), worst day {worst:.1f}%; {o["unclassified"]:,} of {o["events"]:,} events unclassified and excluded. Not verified availability.',
                                   'Dashboard: Platform health', 'Investigate the worst-day failure window and confirm the pre-production fix.', 'Platform Support',
                                   summary=(f'{rate:.2f}% classified-call success rate is below the {AVAILABILITY_TARGET:.0f}% target.' if rate < AVAILABILITY_TARGET
                                            else f'Worst-day classified-call success rate fell to {worst:.1f}%.'),
                                   impact=f'{o["failed"]:,} of {o["classified"]:,} classified calls failed.',
                                   recommended_action='Review the dominant failure contributors.'))
    if charges is not None and len(charges):
        over = charges[pd.to_numeric(charges['variance'], errors='coerce') > CHARGEBACK_THRESHOLD]
        for _, r in over.iterrows():
            items.append(_item('High', 'Financial', f'{r["provider"]} usage variance above threshold',
                               f'Variance {float(r["variance"]):.1f}% vs {CHARGEBACK_THRESHOLD:.0f}% threshold (invoice ${float(r["provider_bill"]):,.0f}, attributed ${float(r["platform_usage"]):,.0f}).',
                               'Dashboard: Chargeback', f'Reconcile the {r["provider"]} invoice before allocation is approved.', 'FinOps',
                               summary=f'{r["provider"]} invoice is {float(r["variance"]):.1f}% above attributed usage, over the {CHARGEBACK_THRESHOLD:.0f}% threshold.',
                               impact=f'${float(r["provider_bill"]) - float(r["platform_usage"]):,.0f} of the invoice is not attributed to platform usage.',
                               recommended_action=f'Reconcile the {r["provider"]} invoice before allocation.'))
    if models is not None and len(models):
        risk = models['risk'].astype(str).str.casefold() == 'high'
        review = models['lifecycle_status'].astype(str).str.contains('Review', case=False)
        migrate = models['migration_required'].astype(str).isin(['Assess', 'Yes'])
        n = int((risk | review | migrate).sum())
        if n:
            items.append(_item('Medium', 'Governance', f'{n} models need a governance decision',
                               f'{int(risk.sum())} high risk, {int(review.sum())} review due, {int(migrate.sum())} migration assessments.',
                               'Dashboard: Model lifecycle', 'Assign an accountable owner for review and retirement decisions.', 'Model Enablement',
                               summary=f'{n} models are high risk, due for review or need a migration assessment.',
                               impact=f'{int(risk.sum())} high risk, {int(review.sum())} review due, {int(migrate.sum())} migration assessments await a decision.',
                               recommended_action='Assign an owner for each review and retirement decision.'))
    if apps is not None and len(apps):
        canon, _ = canonical_use_cases(apps)
        dormant = int((canon['status_category'] == 'Dormant').sum())
        share = dormant / len(canon) if len(canon) else 0
        if share > DORMANT_SHARE_THRESHOLD:
            items.append(_item('Medium', 'Adoption', f'{dormant} dormant-status use cases',
                               f'{share:.0%} of {len(canon)} canonical use cases carry Dormant status; status field only, no validated last-activity timestamp.',
                               'Dashboard: User adoption', 'Contact use-case owners to re-engage or retire dormant-status use cases.', 'Regional Product',
                               summary=f'{dormant} use cases ({share:.0%} of the portfolio) carry Dormant status.',
                               impact='Dormant-status use cases may be carrying cost without delivering value.',
                               recommended_action='Contact owners to re-engage or retire them.'))
    if alerts is not None and len(alerts):
        crit = alerts[alerts['severity'].astype(str).str.casefold() == 'critical']
        covered = any(i['category'] == 'Reliability' for i in items)
        for _, r in crit.iterrows():
            if covered and 'failure' in str(r['title']).casefold():
                continue
            items.append(_item('Critical', 'Operations', str(r['title']), f'{r["metric"]} · status {r["status"]}', 'Dashboard: Alerts', 'Confirm ownership and resolution plan.', str(r['owner']),
                               summary=f'Critical alert: {r["title"]}.',
                               impact=f'The alert on {r["metric"]} is {str(r["status"]).lower()}.',
                               recommended_action='Confirm ownership and a resolution plan.'))
    return sorted(items, key=lambda i: _ORDER.get(i['severity'], 9))


def executive_focus(items):
    if not items:
        return 'No decisions require leadership attention against the current thresholds.'
    top = items[:3]
    return 'Focus on: ' + '; '.join(i['title'].lower() for i in top) + '.'


def priority_breakdown(items):
    if not items:
        return 'No open findings'
    counts = {}
    for i in items:
        counts[i['category']] = counts.get(i['category'], 0) + 1
    return ' · '.join(f'{v} {k.lower()}' for k, v in counts.items())


# ---- Phase 3: executive navigation and model review ordering (presentation only) --------------------
SEVERITY_ICONS = {'Critical': '🔴', 'High': '🟠', 'Medium': '🟡', 'Low': '🟢'}
FINDING_TARGETS = {'Reliability': 'Platform health', 'Operations': 'Platform health', 'Governance': 'Model lifecycle',
                   'Adoption': 'User adoption', 'Financial': 'Chargeback'}
RISK_BADGES = {'high': '🔴 High', 'medium': '🟡 Medium', 'low': '🟢 Low'}
RISK_COLORS = {'high': '#df4b55', 'medium': '#f2a93b', 'low': '#39b98a'}
REVIEW_PRIORITY_LABELS = {1: 'High risk + overdue review', 2: 'High risk', 3: 'Review due', 4: 'Migration required', 5: ''}


def finding_target(item):
    """Page that holds the evidence for an Executive finding."""
    return FINDING_TARGETS.get(item['category'], 'Executive overview')


def model_review_priority(models, today=None):
    """Rank per model: 1 high risk + overdue review, 2 high risk, 3 review due, 4 migration required, 5 the rest.

    Overdue = next_review_date earlier than `today` (default: today, UTC). Presentation order only; no rule or score changes.
    """
    today = pd.Timestamp(today) if today is not None else pd.Timestamp.now(tz='UTC').tz_localize(None).normalize()
    risk = models['risk'].astype(str).str.casefold() == 'high' if 'risk' in models else pd.Series(False, index=models.index)
    due = pd.to_datetime(models['next_review_date'], errors='coerce') < today if 'next_review_date' in models else pd.Series(False, index=models.index)
    review = models['lifecycle_status'].astype(str).str.contains('Review', case=False) if 'lifecycle_status' in models else pd.Series(False, index=models.index)
    migrate = models['migration_required'].astype(str).isin(['Assess', 'Yes']) if 'migration_required' in models else pd.Series(False, index=models.index)
    rank = pd.Series(5, index=models.index)
    for value, mask in ((4, migrate), (3, review), (2, risk), (1, risk & due)):
        rank[mask] = value
    return rank


# ---- Model Inventory & Decisions: separate status concepts (presentation only) -----------------------
ATTENTION_LABELS = {1: 'High risk', 2: 'Overdue review', 3: 'Retirement candidate', 4: ''}
REVIEW_BADGES = {'Overdue': '⏰ Overdue', 'Review due': '🕒 Review due', 'Current': '✔ Current'}
RETIREMENT_BADGES = {'Candidate': '◐ Candidate', 'Scheduled': '▣ Scheduled', 'Retired': '■ Retired', 'None': '○ None'}
# Distinct palettes per concept so one colour never stands for two concepts (risk: red/amber/green; review: blue/grey; retirement: purple/grey).
REVIEW_COLORS = {'Overdue': '#1768ff', 'Review due': '#6a8fd8', 'Current': '#65758a'}
RETIREMENT_COLORS = {'Candidate': '#7a5af8', 'Scheduled': '#5b3fc4', 'Retired': '#65758a', 'None': '#65758a'}


def model_attention_rank(models):
    """Rank per model: 1 high risk, 2 overdue review, 3 retirement candidate (or scheduled), 4 normal.

    Needs the review_status / retirement_status columns added by enrich_models. Presentation order only.
    """
    idx = models.index
    risk = models['risk'].astype(str).str.casefold() == 'high' if 'risk' in models else pd.Series(False, index=idx)
    overdue = models['review_status'] == 'Overdue' if 'review_status' in models else pd.Series(False, index=idx)
    retire = models['retirement_status'].isin(['Candidate', 'Scheduled']) if 'retirement_status' in models else pd.Series(False, index=idx)
    rank = pd.Series(4, index=idx)
    for value, mask in ((3, retire), (2, overdue), (1, risk)):
        rank[mask] = value
    return rank
