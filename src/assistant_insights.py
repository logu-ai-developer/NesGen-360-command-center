"""Bounded audience-oriented evidence. Reuses existing adapters; no new source access."""
import pandas as pd
from src.query_tools import get_apps,get_models,get_health,synthetic_charges,synthetic_alerts
from src.storage import get_setting
from src.insights import build_decision_brief
from src.metrics import health_outcomes,canonical_use_cases,NO_CLASSIFIED_NOTE

def today_utc():
    return pd.Timestamp.now(tz='UTC').tz_localize(None).normalize()

def _mode(d):
    return {'source_mode':d.attrs.get('source_mode','not independently verified'),
            'source_detail':d.attrs.get('source_detail','existing dashboard adapter')}

def get_onboarding_trend(days: int=90, region: str='Global', anchor: str='today', bucket: str='auto'):
    """Approval-date onboarding trend, not actual user activity. Default current UTC date.

    anchor=today or latest; latest excludes future-dated approvals. bucket=day,
    week, month or auto. Counts rows and unique IDs separately. Portfolio statuses
    are not reported as window activity. Maximum 100 buckets.
    """
    if type(days) is not int or not 1<=days<=3650:return {'status':'error','message':'days must be 1..3650'}
    if anchor not in ('today','latest') or bucket not in ('auto','day','week','month'):
        return {'status':'error','message':'Invalid date anchor or bucket'}
    d=get_apps().copy();provenance=_mode(d)
    if region!='Global':d=d[d.region.astype(str).str.casefold()==region.casefold()]
    dates=pd.to_datetime(d.created_date,errors='coerce',utc=True).dt.tz_localize(None)
    today=today_utc();future=dates>=today+pd.Timedelta(days=1)
    available=dates[~future].dropna()
    if anchor=='latest' and available.empty:return {'status':'error','source':'Dashboard: User adoption','message':'No non-future approval dates available'}
    end=today if anchor=='today' else available.max().normalize()
    start=end-pd.Timedelta(days=days-1)
    valid=dates.between(start,end+pd.Timedelta(days=1),inclusive='left')
    portfolio=canonical_use_cases(d)[1]
    w=d.loc[valid].copy();w['approval_date']=dates[valid]
    if bucket=='auto':bucket='day' if days<=31 else 'week' if days<=180 else 'month'
    frequency={'day':'D','week':'W-SUN','month':'M'}[bucket]
    periods=pd.period_range(start,end,freq=frequency)
    if len(periods)>100:return {'status':'error','message':'More than 100 buckets; choose a coarser bucket'}
    w['period']=w.approval_date.dt.to_period(frequency)
    rows=w.groupby('period').size().reindex(periods,fill_value=0)
    unique=w.groupby('period')['id'].nunique().reindex(periods,fill_value=0)
    buckets=[{'period':str(p),'approval_rows':int(rows[p]),'unique_application_ids':int(unique[p])} for p in periods]
    return {'status':'ok','source':'Dashboard: User adoption',**provenance,
        'metric':'Application approvals, not observed adoption or active users',
        'date_range':{'start':str(start.date()),'end':str(end.date()),'anchor':anchor,'inclusive_days':days},
        'future_dated_rows_excluded':int(future.sum()),'invalid_date_rows':int(dates.isna().sum()),
        'days':days,'window_approval_rows':len(w),'window_unique_applications':int(w.id.nunique()),
        'portfolio_rows_in_scope':len(d),'portfolio_use_cases_in_scope':portfolio['canonical_use_cases'],
        'portfolio_rows_without_id':portfolio['missing_id_rows'],'bucket':bucket,'buckets':buckets,
        'notes':['Zero buckets are included. Boundary weeks/months may be partial.',
                 'Approval dates cannot establish sustained usage. Missing rows do not prove no real-world onboarding.']}

def get_chargeback_report(provider: str='All'):
    """Chargeback invoice and attributed-usage scenario, not request consumption.

    Uses existing dashboard chargeback scenario and configured threshold. No live
    MuleSoft or provider-billing connector is implied. Currency is not inferred.
    """
    d=synthetic_charges().copy();threshold=float(get_setting('chargeback_threshold',5))
    if provider!='All':d=d[d.provider.astype(str).str.casefold()==provider.casefold()]
    rows=[]
    for _,r in d.iterrows():
        rows.append({'provider':str(r.provider),'period':str(r.get('period','Unknown')),
            'provider_invoice':float(r.provider_bill),'attributed_usage':float(r.platform_usage),
            'unexplained_amount':float(r.provider_bill-r.platform_usage),
            'stored_variance_percent':float(r.variance),'review_required':bool(r.variance>threshold)})
    return {'status':'ok','source':'Dashboard: Chargeback','source_mode':'synthetic scenario',
        'metric':'Invoice and attributed usage amounts; NOT requests or actual token consumption',
        'currency':'Not independently verified','threshold_percent':threshold,
        'live_mulesoft_reconciliation':False,'providers':rows,
        'note':'Consumption is ambiguous here. State the amount metric used; do not substitute Executive overview request shares.'}

def get_platform_report(days: int=7, anchor: str='today'):
    """Daily dashboard health evidence with explicit period and alert freshness limits."""
    if type(days) is not int or not 1<=days<=3650 or anchor not in ('today','latest'):
        return {'status':'error','message':'Invalid days/anchor'}
    d=get_health().copy();provenance=_mode(d)
    dates=pd.to_datetime(d.date,errors='coerce',utc=True).dt.tz_localize(None)
    today=today_utc();future=dates>=today+pd.Timedelta(days=1)
    valid_dates=dates[~future].dropna()
    if anchor=='latest' and valid_dates.empty:return {'status':'error','message':'No non-future health dates available'}
    end=today if anchor=='today' else valid_dates.max().normalize();start=end-pd.Timedelta(days=days-1)
    w=d[(dates>=start)&(dates<end+pd.Timedelta(days=1))]
    metrics=None
    if not w.empty:
        o=health_outcomes(w);daily=pd.to_numeric(w.success_rate,errors='coerce').dropna();p95=pd.to_numeric(w.p95_latency_ms,errors='coerce').max()
        metrics={'daily_rows':len(w),'events_in_scope':o['events'],'classified_calls':o['classified'],
            'successful_classified_calls':o['success'],'failed_classified_calls':o['failed'],'unclassified_events':o['unclassified'],
            # None = unavailable: no classified calls (or no events), not a measured 0%.
            'classified_call_success_rate_percent':o['success_pct'],'classified_call_failure_rate_percent':o['failure_pct'],
            'unclassified_event_percent':o['unclassified_pct'],
            'unweighted_average_daily_classified_success_percent':float(daily.mean()) if len(daily) else None,
            'maximum_daily_p95_ms':None if pd.isna(p95) else float(p95),
            'unclassified_telemetry_present':o['unclassified']>0}
        if not o['classified']:metrics['rate_unavailable_reason']=NO_CLASSIFIED_NOTE
    return {'status':'ok','source':'Dashboard: Platform health',**provenance,
        'days':days,'date_range':{'start':str(start.date()),'end':str(end.date()),'anchor':anchor},
        'future_dated_rows_excluded':int(future.sum()),'metrics':metrics,
        'alerts':_alert_rows(), 'alert_freshness':'Scenario alerts have no verified event timestamp; occurrence today is NOT verified.',
        'metric_note':'Classified-call success rate = successful / (successful + failed) x 100. Unclassified events are excluded from the denominator and never counted as successful. This is not verified end-to-end availability. Event counts are not deduplicated requests; maximum daily P95 is not global event P95.'}

def _alert_rows():
    d=synthetic_alerts().copy()
    # Department ownership only; do not send personal owner fields.
    allowed=['id','severity','title','source','metric','status']
    return d[[c for c in allowed if c in d]].head(10).fillna('Unknown').to_dict('records')

def get_decision_brief():
    """Open scenario actions for stakeholders, with no claim they occurred today."""
    findings=build_decision_brief(get_apps(),get_models(),get_health(),synthetic_charges(),synthetic_alerts())
    return {'status':'ok','source':'Dashboard: Executive overview / open scenarios',
        'source_mode':'synthetic scenario','as_of':str(today_utc().date()),
        'alerts':_alert_rows(),'freshness':'No verified event timestamp. These are open scenario records, not verified events today.',
        # Same rule-based findings as the Executive overview; chargeback and alert inputs are synthetic scenarios.
        'findings':[{k:i[k] for k in ('severity','category','title','evidence','source')} for i in findings[:10]],
        'suggested_actions_are_recommendations':True,
        'recommendations':['Investigate the open reliability scenario with platform support.',
            'Review invoice-to-attributed-usage gaps with FinOps.',
            'Review model evidence and ownership before a lifecycle decision.']}
