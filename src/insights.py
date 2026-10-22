"""Rule-based decision brief and KPI definitions. Deterministic; needs no API key."""
from __future__ import annotations
import pandas as pd

# Thresholds used by the decision brief (S1-008..S1-011); change here to retune findings.
AVAILABILITY_TARGET = 98.0
CHARGEBACK_THRESHOLD = 5.0
DORMANT_SHARE_THRESHOLD = 0.10
_ORDER = {'Critical': 0, 'High': 1, 'Medium': 2, 'Low': 3}


def _kpi(definition, formula, source, dataset, metric, caveat=''):
    return {'definition': definition, 'formula': formula, 'source': source, 'dataset': dataset, 'metric': metric, 'caveat': caveat}


KPI_INFO = {
    # Executive overview
    'availability': _kpi('Share of platform events that completed without an error.', 'Mean of daily success rate (%) across the selected window.', 'Platform health', 'health_daily', 'average_daily_success_rate', 'Unweighted mean of daily values, not event-weighted. Target is 98% or higher.'),
    'governed_models': _kpi('Models registered in the governance catalog for the selected provider.', 'Count of model rows; high-risk = rows with risk = High.', 'Model lifecycle', 'models', 'model_rows'),
    'monthly_active_apps': _kpi('Applications showing a sustained-use status.', 'Count of applications whose status contains Active or Operational.', 'User adoption', 'applications', 'application_rows', 'Based on the workbook status field, not measured activity.'),
    'priority_actions': _kpi('Decisions that currently need leadership attention.', 'Number of rule-based findings: availability below 98%, provider variance above 5%, models needing review, dormant apps above 10%, open critical alerts.', 'Executive overview', 'alerts + charges + models + applications', 'decision_brief'),
    # Model lifecycle
    'lifecycle_governed': _kpi('Models in the current filter selection.', 'Count of model rows after the risk, stage and search filters.', 'Model lifecycle', 'models', 'model_rows'),
    'industrialized': _kpi('Models approved to operate in production.', 'Count where stage = Industrialized.', 'Model lifecycle', 'models', 'model_rows'),
    'review_due': _kpi('Models whose evidence needs refreshing.', 'Count where lifecycle status contains Review.', 'Model lifecycle', 'models', 'model_rows'),
    'retirement': _kpi('Models that need a retirement or migration decision.', 'Count where migration_required is Assess or Yes.', 'Model lifecycle', 'models', 'model_rows', 'Candidates for a decision, not a confirmed provider retirement.'),
    # Platform health
    'success_rate': _kpi('Share of events that completed without an error.', 'Mean of daily success rate (%). Target is 98% or higher.', 'Platform health', 'health_daily', 'average_daily_success_rate', 'Unweighted mean of daily values.'),
    'p95_latency': _kpi('Response time that 95% of requests stay under.', '95th percentile across the daily P95 latency values, shown in seconds.', 'Platform health', 'health_daily', 'maximum_daily_p95_ms', 'A percentile of daily percentiles, not the P95 across all events.'),
    'request_volume': _kpi('Total requests handled in the window.', 'Sum of daily request counts.', 'Platform health', 'health_daily', 'requests', 'Log events are counted; they are not deduplicated requests.'),
    'services_healthy': _kpi('Services with no open reliability alert.', 'Illustrative value in this prototype; no service inventory is connected.', 'Platform health', 'not connected', 'n/a', 'Illustrative only.'),
    # User adoption
    'onboarded': _kpi('Applications onboarded in the selected scope.', 'Count of application rows after the sidebar filters.', 'User adoption', 'applications', 'application_rows'),
    'adoption_active': _kpi('Onboarded applications that are in sustained use.', 'Count where status contains Active or Operational; activation = active / onboarded.', 'User adoption', 'applications', 'application_rows'),
    'adoption_new': _kpi('Applications newly onboarded this month.', 'Count where status contains New.', 'User adoption', 'applications', 'application_rows', 'Based on workbook status, not approval date.'),
    'dormant': _kpi('Applications with no use in the dormancy window.', 'Count where status contains Dormant (30-day default).', 'User adoption', 'applications', 'application_rows'),
    # Chargeback
    'invoice': _kpi('Amount billed by the cloud providers.', 'Sum of provider invoice values for the period.', 'Chargeback', 'charges', 'provider_invoice'),
    'attributed': _kpi('Cost the platform can attribute to applications.', 'Sum of platform-attributed usage values.', 'Chargeback', 'charges', 'attributed_usage'),
    'unexplained': _kpi('Billed amount with no platform attribution.', 'Invoice minus attributed usage.', 'Chargeback', 'charges', 'unexplained_amount'),
    'exceptions': _kpi('Providers whose variance exceeds the review threshold.', 'Count of providers with status = Review (variance above 5%).', 'Chargeback', 'charges', 'maximum_variance_percent'),
    # V1.1 platform-health drill-down
    'api_calls': _kpi('Total API calls handled by the gateway in the telemetry window.', 'Count of events classified by Body.Tracepoint (FLOW-END or FLOW-ERROR).', 'Platform health', 'new_relic', 'events', 'Events without a Tracepoint are excluded and shown as unclassified.'),
    'calls_success': _kpi('Calls that completed normally.', 'Count where Body.Tracepoint = FLOW-END; share = successful / total calls.', 'Platform health', 'new_relic', 'events'),
    'calls_failed': _kpi('Calls that ended in an error flow.', 'Count where Body.Tracepoint = FLOW-ERROR; share = failed / total calls.', 'Platform health', 'new_relic', 'events'),
    'p95_true': _kpi('Response time that 95% of calls stay under.', 'QUANTILE_CONT(responseTime, 0.95) across all classified calls.', 'Platform health', 'new_relic', 'p95_latency_ms', 'Unlike the daily trend chart, this is a true P95 over every call, not a percentile of daily P95 values.'),
    # V1.1 model lifecycle
    'lifecycle_sandbox': _kpi('Models still in sandbox or exploration.', 'Count where governance stage contains Sandbox or Exploration.', 'Model lifecycle', 'models', 'model_rows', 'The current model workbook has no sandbox stage, so 0 is expected for real data.'),
    'models_with_backup': _kpi('Models that have a suggested replacement.', 'Count of models with a derived replacement (same provider and family preferred, retiring later, not already retired).', 'Model lifecycle', 'models', 'model_rows', 'Replacement is derived by rule, not source data. Confirm with the model owner.'),
    'readiness': _kpi('How ready a model is to be decommissioned safely.', '40% evaluation score + 20 if a backup exists + 15 replacement risk (Low 15, Medium 8, High 0) + 15 time to retire + 10 evidence status.', 'Model lifecycle', 'models', 'decommission_readiness', 'Composite for prioritisation; not a formal risk rating.'),
    # V1.1 adoption by use case
    'use_cases': _kpi('Use cases onboarded to the platform.', 'Count of unique application / use-case IDs after the sidebar filters.', 'User adoption', 'applications', 'unique_applications'),
    'uc_sandbox': _kpi('Use cases still in sandbox.', 'Count where use_case_stage = Sandbox.', 'User adoption', 'applications', 'application_rows'),
    'uc_industrialized': _kpi('Use cases running industrialized.', 'Count where use_case_stage = Industrialized.', 'User adoption', 'applications', 'application_rows'),
    'platform_users': _kpi('Active users across onboarded use cases.', 'Sum of active_users.', 'User adoption', 'applications', 'active_users', 'Source field active_users; falls back to synthetic when the workbook lacks it.'),
}


def _item(severity, category, title, evidence, source, action, owner):
    return {'severity': severity, 'category': category, 'title': title, 'evidence': evidence,
            'source': source, 'action': action, 'owner': owner}


def build_decision_brief(apps, models, health, charges, alerts):
    """Return findings sorted by severity. Every item carries evidence, source, action and owner."""
    items = []
    if health is not None and len(health):
        avail = float(pd.to_numeric(health['success_rate'], errors='coerce').mean())
        worst = float(pd.to_numeric(health['success_rate'], errors='coerce').min())
        if avail < AVAILABILITY_TARGET or worst < 92:
            sev = 'Critical' if worst < 92 else 'High'
            items.append(_item(sev, 'Reliability', 'Platform reliability below target',
                               f'Average availability {avail:.2f}% (target {AVAILABILITY_TARGET:.0f}%), worst day {worst:.1f}%.',
                               'Dashboard: Platform health', 'Investigate the worst-day failure window and confirm the pre-production fix.', 'Platform Support'))
    if charges is not None and len(charges):
        over = charges[pd.to_numeric(charges['variance'], errors='coerce') > CHARGEBACK_THRESHOLD]
        for _, r in over.iterrows():
            items.append(_item('High', 'Financial', f'{r["provider"]} usage variance above threshold',
                               f'Variance {float(r["variance"]):.1f}% vs {CHARGEBACK_THRESHOLD:.0f}% threshold (invoice ${float(r["provider_bill"]):,.0f}, attributed ${float(r["platform_usage"]):,.0f}).',
                               'Dashboard: Chargeback', f'Reconcile the {r["provider"]} invoice before allocation is approved.', 'FinOps'))
    if models is not None and len(models):
        risk = models['risk'].astype(str).str.casefold() == 'high'
        review = models['lifecycle_status'].astype(str).str.contains('Review', case=False)
        migrate = models['migration_required'].astype(str).isin(['Assess', 'Yes'])
        n = int((risk | review | migrate).sum())
        if n:
            items.append(_item('Medium', 'Governance', f'{n} models need a governance decision',
                               f'{int(risk.sum())} high risk, {int(review.sum())} review due, {int(migrate.sum())} migration assessments.',
                               'Dashboard: Model lifecycle', 'Assign an accountable owner for review and retirement decisions.', 'Model Enablement'))
    if apps is not None and len(apps):
        dormant = int(apps['status'].astype(str).str.contains('Dormant', case=False, na=False).sum())
        share = dormant / len(apps)
        if share > DORMANT_SHARE_THRESHOLD:
            items.append(_item('Medium', 'Adoption', f'{dormant} dormant applications',
                               f'{share:.0%} of {len(apps)} onboarded applications show no recent use.',
                               'Dashboard: User adoption', 'Contact application owners to re-engage or retire dormant applications.', 'Regional Product'))
    if alerts is not None and len(alerts):
        crit = alerts[alerts['severity'].astype(str).str.casefold() == 'critical']
        covered = any(i['category'] == 'Reliability' for i in items)
        for _, r in crit.iterrows():
            if covered and 'failure' in str(r['title']).casefold():
                continue
            items.append(_item('Critical', 'Operations', str(r['title']), f'{r["metric"]} · status {r["status"]}', 'Dashboard: Alerts', 'Confirm ownership and resolution plan.', str(r['owner'])))
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
