"""Allowlisted analytical tools. No model-provided SQL, identifiers or paths are executed."""
from __future__ import annotations
import contextvars
import json
import math
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

import duckdb
import pandas as pd
from src import data as dashboard
from src.provider import provider_consumption, normalize_allocations

MAX_ROWS = 100
MAX_BYTES = 12000
TIMEOUT_SECONDS = 10
MAX_SNAPSHOT_ROWS = 100000
_STATE = contextvars.ContextVar('nesgen_query_state', default=None)

class QueryValidationError(ValueError):
    pass

@contextmanager
def query_session(scope=None):
    token = _STATE.set({'frames': {}, 'calls': 0, 'scope':scope or {}})
    try:
        yield
    finally:
        _STATE.reset(token)

def _frame(name):
    state = _STATE.get()
    loaders = {'applications': dashboard.get_apps, 'models': dashboard.get_models,
               'health_daily': dashboard.get_health, 'charges': dashboard.synthetic_charges,
               'alerts': dashboard.synthetic_alerts}
    if state is not None and name in state['frames']:
        return state['frames'][name].copy()
    result = loaders[name]().copy()
    if len(result) > MAX_SNAPSHOT_ROWS:
        raise QueryValidationError('Dashboard snapshot exceeds the configured local row cap')
    if state is not None:
        state['frames'][name] = result.copy()
    return result

# Used by the existing summary functions too: a single question sees one snapshot.
def _scoped(name):
    d=_frame(name);state=_STATE.get();scope=state.get('scope',{}) if state else {}
    unsupported=[]
    for col,value in scope.items():
        if value in ('All','Global',None):continue
        if col=='provider' and name=='applications' and value in ('Azure','AWS','GCP'):
            if value in d:d=d[pd.to_numeric(d[value],errors='coerce').fillna(0)>0]
            else:unsupported.append(col)
        elif col in d:d=d[d[col].astype(str).str.casefold()==str(value).casefold()]
        else:unsupported.append(col)
    d.attrs['unsupported_scope']=unsupported
    return d

def get_apps(): return _scoped('applications')
def get_models(): return _scoped('models')
def get_health(): return _scoped('health_daily')
def synthetic_charges(): return _scoped('charges')
def synthetic_alerts(): return _scoped('alerts')

def _metric(sql, definition): return (sql, definition)
CATALOG = {
 'applications': {
  'source': 'Dashboard: User adoption',
  'mode': 'dashboard adapter; source/fallback provenance not independently verified',
  'dimensions': ['region', 'environment', 'status', 'platform', 'recertification_status'],
  'numeric': ['expected_daily_users', 'business_value'], 'date': 'created_date',
  'metrics': {
   'application_rows': _metric('COUNT(*)', 'Application rows, not necessarily unique application IDs.'),
   'unique_applications': _metric('COUNT(DISTINCT "id")', 'Distinct non-null application identifiers.'),
   'expected_daily_users': _metric('SUM(TRY_CAST("expected_daily_users" AS DOUBLE))', 'Sum of expected users; not observed active users.'),
   'business_value': _metric('SUM(TRY_CAST("business_value" AS DOUBLE))', 'Sum of workbook business-value field; unit/currency is not inferred.') }},
 'models': {
  'source': 'Dashboard: Model lifecycle', 'mode': 'dashboard adapter; source/fallback provenance not independently verified',
  'dimensions': ['provider','model_family','stage','risk','lifecycle_status','migration_required'],
  'numeric': ['evaluation_score'], 'date': 'next_review_date',
  'metrics': {'model_rows': _metric('COUNT(*)','Model rows in the current catalog.'),
              'average_evaluation': _metric('AVG(TRY_CAST("evaluation_score" AS DOUBLE))','Mean evaluation score; not a lifecycle-risk score.')}},
 'health_daily': {
  'source': 'Dashboard: Platform health', 'mode': 'dashboard daily aggregate adapter; source/fallback provenance not independently verified',
  'dimensions': ['environment'], 'numeric': ['requests','success_rate','p95_latency_ms','cost'], 'date': 'date',
  'metrics': {'daily_rows': _metric('COUNT(*)','Daily aggregate rows.'),
   'requests': _metric('SUM(TRY_CAST("requests" AS DOUBLE))','Sum of requests in daily aggregates.'),
   'average_daily_success_rate': _metric('AVG(TRY_CAST("success_rate" AS DOUBLE))','Unweighted mean of daily success percentages, not an event-weighted success rate.'),
   'maximum_daily_p95_ms': _metric('MAX(TRY_CAST("p95_latency_ms" AS DOUBLE))','Maximum daily P95; not the P95 across all events.'),
   'total_cost': _metric('SUM(TRY_CAST("cost" AS DOUBLE))','Sum of dashboard cost values; source currency is not inferred.')}},
 'provider_usage': {
  'source': 'Dashboard: Executive overview / provider consumption',
  'mode': 'derived from the same dashboard application adapter',
  'dimensions': ['provider','region','environment','status'], 'numeric': ['allocated_monthly_requests'], 'date': 'created_date',
  'metrics': {'allocated_monthly_requests': _metric('SUM(TRY_CAST("allocated_monthly_requests" AS DOUBLE))','Monthly requests multiplied by normalized provider allocation. If monthly_requests was derived from expected users, this is an estimate, not measured telemetry.')}},
 'charges': {
  'source': 'Dashboard: Chargeback', 'mode': 'existing synthetic scenario adapter',
  'dimensions': ['provider','status','period'], 'numeric': ['provider_bill','platform_usage','variance'], 'date': None,
  'metrics': {'provider_invoice': _metric('SUM(TRY_CAST("provider_bill" AS DOUBLE))','Sum of scenario provider invoice values.'),
   'attributed_usage': _metric('SUM(TRY_CAST("platform_usage" AS DOUBLE))','Sum of scenario attributed usage values.'),
   'unexplained_amount': _metric('SUM(TRY_CAST("provider_bill" AS DOUBLE)-TRY_CAST("platform_usage" AS DOUBLE))','Invoice less attributed usage.'),
   'maximum_variance_percent': _metric('MAX(TRY_CAST("variance" AS DOUBLE))','Largest stored provider variance; not a weighted total variance.')}},
 'alerts': {
  'source': 'Dashboard: Executive overview / alerts', 'mode': 'existing synthetic scenario adapter',
  'dimensions': ['severity','status','source'], 'numeric': [], 'date': None,
  'metrics': {'alert_rows': _metric('COUNT(*)','Alert records; no owner or free-text payload is returned.')}},
 'sqlite_charges': {
  'source': 'SQLite: provider_charges or charges', 'mode': 'read-only SQLite snapshot, separate from dashboard scenario adapter',
  'dimensions': ['provider','status','period'], 'numeric': ['provider_bill','platform_usage','variance'], 'date': None,
  'metrics': {}},
 'sqlite_alerts': {
  'source': 'SQLite: operational_alerts or alerts', 'mode': 'read-only SQLite snapshot, separate from dashboard scenario adapter',
  'dimensions': ['severity','status','source'], 'numeric': [], 'date': None, 'metrics': {}},
 'new_relic': {
  'source': 'Parquet: NewRelic', 'mode': 'direct local Parquet, no fallback',
  'dimensions': ['provider','environment','model','service','severity'],
  'numeric': ['latency_ms','total_tokens','total_cost'], 'date': 'event_time',
  'metrics': {'events': _metric('COUNT(*)','Log-event count, not deduplicated requests.'),
   'total_tokens': _metric('SUM("total_tokens")','Sum of logged tokens; duplicate events may double-count.'),
   'total_cost': _metric('SUM("total_cost")','Sum of logged cost values; duplicate events may double-count.'),
   'average_latency_ms': _metric('AVG("latency_ms")','Mean responseTime across log events.'),
   'p95_latency_ms': _metric('QUANTILE_CONT("latency_ms",0.95)','P95 across non-null responseTime values in matching events.'),
   'non_error_event_percent': _metric("100.0*AVG(CASE WHEN \"severity\" IS NULL THEN NULL WHEN UPPER(\"severity\") IN ('ERROR','FATAL') THEN 0.0 ELSE 1.0 END)", 'Percentage of non-ERROR/FATAL events among events with severity; not verified request success.')}},
 'log_analytics': {
  'source': 'Parquet: LogAnalytics', 'mode': 'direct local Parquet, no fallback',
  'dimensions': ['environment','model','service'], 'numeric': ['latency_ms','total_tokens'], 'date': 'event_time',
  'metrics': {'events': _metric('COUNT(*)','Log-event count, not deduplicated requests.'),
   'total_tokens': _metric('SUM("total_tokens")','Sum of logged tokens.'),
   'average_latency_ms': _metric('AVG("latency_ms")','Mean numeric response time; unit must match the source contract.'),
   'p95_latency_ms': _metric('QUANTILE_CONT("latency_ms",0.95)','P95 of numeric response time in matching events.')}}
}
CATALOG['sqlite_charges']['metrics'] = CATALOG['charges']['metrics']
CATALOG['sqlite_alerts']['metrics'] = CATALOG['alerts']['metrics']

PARQUET_FIELDS = {
 'new_relic': {
  'event_time': ('Timestamp_1','TIMESTAMP'), 'provider': ('Attributes.BusinessKeys.provider','VARCHAR'),
  'environment': ('Attributes.BusinessKeys.environment','VARCHAR'), 'model': ('Attributes.BusinessKeys.model','VARCHAR'),
  'service': ('Attributes.BusinessKeys.service','VARCHAR'), 'severity': ('SeverityText','VARCHAR'),
  'latency_ms': ('Attributes.BusinessKeys.responseTime','DOUBLE'),
  'total_tokens': ('Attributes.BusinessKeys.total_tokens','DOUBLE'), 'total_cost': ('Attributes.BusinessKeys.total_cost','DOUBLE')},
 'log_analytics': {
  'event_time': ('TimeGenerated','TIMESTAMP'), 'environment': ('environment_s','VARCHAR'),
  'model': ('model_s','VARCHAR'), 'service': ('service_s','VARCHAR'),
  'latency_ms': ('responseTime_d','DOUBLE'), 'total_tokens': ('usage_total_tokens_d','DOUBLE')}
}

def _qid(s): return '"'+s.replace('"','""')+'"'

def _json(value):
    # Strict JSON, finite numbers, bounded categorical strings.
    def clean(v):
        if isinstance(v, dict): return {str(k):clean(x) for k,x in v.items()}
        if isinstance(v, (list,tuple)): return [clean(x) for x in v]
        if isinstance(v, float) and not math.isfinite(v): return None
        if isinstance(v, str): return v[:200]
        if v is pd.NaT or v is pd.NA: return None
        if hasattr(v,'isoformat'): return v.isoformat()
        if hasattr(v,'item'): return clean(v.item())
        return v
    return json.dumps(clean(value),ensure_ascii=False,allow_nan=False)

def _dataset(name):
    if name not in CATALOG: raise QueryValidationError('Unknown dataset. Call list_datasets first.')
    return CATALOG[name]

def _sqlite_frame(dataset):
    candidates = ['provider_charges','charges'] if dataset=='sqlite_charges' else ['operational_alerts','alerts']
    db = Path(dashboard.DB).resolve()
    if not db.is_file(): raise QueryValidationError('SQLite source is unavailable; no fallback used.')
    with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True,timeout=3) as c:
        c.execute('PRAGMA query_only=ON')
        tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        table=next((x for x in candidates if x in tables),None)
        if not table: raise QueryValidationError('Approved SQLite table is unavailable.')
        available={r[1] for r in c.execute('PRAGMA table_info('+_qid(table)+')')}
        spec=CATALOG[dataset]
        cols=[x for x in spec['dimensions']+spec['numeric'] if x in available]
        if not cols: raise QueryValidationError('Approved SQLite columns are missing.')
        d=pd.read_sql_query('SELECT '+','.join(map(_qid,cols))+' FROM '+_qid(table)+' LIMIT '+str(MAX_SNAPSHOT_ROWS+1),c)
    if len(d)>MAX_SNAPSHOT_ROWS: raise QueryValidationError('SQLite snapshot exceeds local row cap.')
    return d

def _load_frame(name):
    if name.startswith('sqlite_'): return _sqlite_frame(name)
    if name=='provider_usage':
        d=normalize_allocations(get_apps())
        m=pd.to_numeric(d['monthly_requests'],errors='coerce').fillna(0)
        pieces=[]
        for provider in ['Azure','AWS','GCP']:
            p=d[[x for x in ['region','environment','status','created_date'] if x in d]].copy()
            p['provider']=provider
            p['allocated_monthly_requests']=m*pd.to_numeric(d[provider],errors='coerce').fillna(0)
            pieces.append(p)
        return pd.concat(pieces,ignore_index=True)
    return _frame(name)

@contextmanager
def _connection(name):
    spec=_dataset(name)
    c=duckdb.connect(':memory:',config={'memory_limit':'256MB','threads':'2',
                      'autoinstall_known_extensions':'false','autoload_known_extensions':'false'})
    timer=threading.Timer(TIMEOUT_SECONDS,c.interrupt);timer.daemon=True;timer.start()
    try:
        if name in PARQUET_FIELDS:
            folder=Path(dashboard.DATA)/('NewRelic' if name=='new_relic' else 'LogAnalytics')
            root=Path(dashboard.DATA).resolve()
            files=sorted(folder.glob('*.parquet'))
            if not files: raise QueryValidationError('Parquet source is unavailable; no fallback used.')
            for f in files:
                if not f.resolve().is_relative_to(root): raise QueryValidationError('Parquet file outside approved data root.')
            c.read_parquet([str(f.resolve()) for f in files],union_by_name=True).create_view('_raw')
            available={r[0] for r in c.execute('DESCRIBE _raw').fetchall()}
            select=[]
            for alias,(source,kind) in PARQUET_FIELDS[name].items():
                if source in available: select.append('TRY_CAST('+_qid(source)+' AS '+kind+') AS '+_qid(alias))
            if not select: raise QueryValidationError('No approved telemetry columns found.')
            c.execute('CREATE VIEW dataset AS SELECT '+','.join(select)+' FROM _raw')
        else:
            d=_load_frame(name)
            allowed=set(spec['dimensions']+spec['numeric']+(['id'] if name=='applications' else [])+([spec['date']] if spec['date'] else []))
            d=d[[x for x in d.columns if x in allowed]].copy()
            if spec['date'] and spec['date'] in d:
                d[spec['date']]=pd.to_datetime(d[spec['date']],errors='coerce',utc=True,format='mixed').dt.tz_localize(None)
            c.register('dataset',d)
        columns={r[0] for r in c.execute('DESCRIBE dataset').fetchall()}
        yield c,columns
    finally:
        timer.cancel();c.close()

def list_datasets() -> str:
    """List approved analytical datasets. No filesystem paths or raw records are exposed."""
    return _json({'datasets':[{'dataset':n,'source':s['source'],'mode':s['mode']} for n,s in CATALOG.items()],
                  'privacy':'Aggregate queries only; no arbitrary SQL or raw-record export.'})

def describe_dataset(dataset: str) -> str:
    """Describe available dimensions, metrics, date column and approved filter fields."""
    try:
        s=_dataset(dataset)
        with _connection(dataset) as (c,cols):
            metrics={k:v[1] for k,v in s['metrics'].items() if all(x in cols for x in _metric_columns(v[0]))}
            return _json({'dataset':dataset,'source':s['source'],'mode':s['mode'],
                          'dimensions':[x for x in s['dimensions'] if x in cols],
                          'numeric_filters':[x for x in s['numeric'] if x in cols],
                          'date_column':s['date'] if s['date'] in cols else None,'metrics':metrics,
                          'limits':{'rows':MAX_ROWS,'result_bytes':MAX_BYTES,'query_timeout_seconds':TIMEOUT_SECONDS}})
    except Exception as e: return _error(e)

def _metric_columns(expr):
    import re
    return re.findall(r'"([A-Za-z_][A-Za-z_0-9]*)"',expr)

def get_metric_definition(dataset: str, metric: str) -> str:
    """Explain an allowlisted metric. Does not execute a query."""
    try:
        s=_dataset(dataset)
        if metric not in s['metrics']: raise QueryValidationError('Unknown metric for dataset.')
        return _json({'dataset':dataset,'metric':metric,'definition':s['metrics'][metric][1],'source':s['source']})
    except Exception as e:return _error(e)

def _error(exc):
    # Never forward raw SQL, local paths, or backend exception strings.
    if isinstance(exc,QueryValidationError):
        msg=str(exc)
        if len(msg)>200:msg='Invalid structured query.'
    elif isinstance(exc,duckdb.InterruptException):msg='Query exceeded local time limit.'
    else:msg='Local dataset query failed. Check source schema or availability.'
    return _json({'status':'error','message':msg,'rows':[]})

def query_dashboard(query_json: str) -> str:
    """Run a read-only aggregate query. Pass a JSON object, never SQL.

    Fields: dataset (required), dimensions (up to 2), metrics (1 to 6),
    filters (up to 8 objects: column, op, value), date_range (start/end ISO dates
    or days integer and as_of='latest'/'today'), limit (1..100).
    Allowed filter ops: eq, ne, in, gt, gte, lt, lte. All dimensions, metrics
    and filter columns must come from describe_dataset. Dates use inclusive
    calendar days; 'latest' anchors to the latest date in the selected dataset.
    Example: {"dataset":"applications","dimensions":["region"],
    "metrics":["unique_applications"],"filters":[{"column":"status",
    "op":"eq","value":"Active"}],"limit":20}.
    """
    try:
        state=_STATE.get()
        if state is not None:
            state['calls']+=1
            if state['calls']>8:raise QueryValidationError('Per-question query budget exhausted.')
        if not isinstance(query_json,str) or len(query_json)>8000:raise QueryValidationError('Query JSON exceeds input limit.')
        q=json.loads(query_json)
        if not isinstance(q,dict):raise QueryValidationError('Query must be a JSON object.')
        if set(q)-{'dataset','dimensions','metrics','filters','date_range','limit'}:raise QueryValidationError('Unsupported query field; SQL and paths are not accepted.')
        name=q.get('dataset');s=_dataset(name)
        dims=q.get('dimensions',[]);metrics=q.get('metrics',[]);filters=q.get('filters',[]);limit=q.get('limit',20)
        if not isinstance(dims,list) or len(dims)>2 or len(set(dims))!=len(dims):raise QueryValidationError('Use up to two unique dimensions.')
        if not isinstance(metrics,list) or not 1<=len(metrics)<=6 or len(set(metrics))!=len(metrics):raise QueryValidationError('Use one to six unique metrics.')
        if not isinstance(filters,list) or len(filters)>8:raise QueryValidationError('Use up to eight filters.')
        if type(limit) is not int or not 1<=limit<=MAX_ROWS:raise QueryValidationError('Limit must be 1..100.')
        if any(x not in s['dimensions'] for x in dims):raise QueryValidationError('Unapproved dimension.')
        if any(x not in s['metrics'] for x in metrics):raise QueryValidationError('Unapproved metric.')
        with _connection(name) as (c,cols):
            if any(x not in cols for x in dims):raise QueryValidationError('Requested dimension is absent from this source.')
            for m in metrics:
                if any(x not in cols for x in _metric_columns(s['metrics'][m][0])):raise QueryValidationError('Metric source column is missing.')
            where=[];params=[]
            unsupported_scope=[]
            state=_STATE.get();scope=state.get('scope',{}) if state else {}
            for col,value in scope.items():
                if value in ('All','Global',None):continue
                if col in s['dimensions'] and col in cols:
                    where.append('LOWER(CAST('+_qid(col)+' AS VARCHAR))=LOWER(?)');params.append(str(value))
                elif name=='applications' and col=='provider':
                    # Canonical app provider is a multi-model string; require explicit allocation dataset.
                    unsupported_scope.append('provider: use provider_usage for allocation scope')
                else:unsupported_scope.append(col)
            for f in filters:
                if not isinstance(f,dict) or set(f)!={'column','op','value'}:raise QueryValidationError('Invalid filter structure.')
                col=f['column'];op=f['op'];v=f['value']
                if col not in s['dimensions']+s['numeric'] or col not in cols:raise QueryValidationError('Unapproved filter column.')
                expr=_qid(col)
                if col in s['numeric']:expr='TRY_CAST('+expr+' AS DOUBLE)'
                if op=='in':
                    if not isinstance(v,list) or not 1<=len(v)<=20:raise QueryValidationError('IN requires 1..20 scalar values.')
                    values=v
                else:values=[v]
                if any(not isinstance(x,(str,int,float,bool)) or isinstance(x,str) and len(x)>160 for x in values):raise QueryValidationError('Filter values must be bounded scalars.')
                if col in s['numeric']:
                    try:values=[float(x) for x in values]
                    except Exception:raise QueryValidationError('Numeric filter requires numeric values.')
                    if any(not math.isfinite(x) for x in values):raise QueryValidationError('Numeric filter must be finite.')
                if op=='in':where.append(expr+' IN ('+','.join('?' for _ in values)+')');params+=values
                else:
                    operators={'eq':'=','ne':'<>','gt':'>','gte':'>=','lt':'<','lte':'<='}
                    if op not in operators:raise QueryValidationError('Unapproved filter operator.')
                    where.append(expr+operators[op]+'?');params+=values
            effective=None
            dr=q.get('date_range')
            if dr is not None:
                datecol=s['date']
                if not datecol or datecol not in cols:raise QueryValidationError('This dataset has no approved date column.')
                if not isinstance(dr,dict):raise QueryValidationError('Invalid date_range.')
                if 'days' in dr:
                    if set(dr)-{'days','as_of'}:raise QueryValidationError('Do not mix days with explicit dates.')
                    days=dr['days'];anchor=dr.get('as_of','latest')
                    if type(days) is not int or not 1<=days<=3650 or anchor not in ('latest','today'):raise QueryValidationError('Invalid days/as_of.')
                    if anchor=='today':end=pd.Timestamp.now(tz='UTC').tz_localize(None).normalize()
                    else:
                        value=c.execute('SELECT MAX(TRY_CAST('+_qid(datecol)+' AS TIMESTAMP)) FROM dataset').fetchone()[0]
                        if value is None:raise QueryValidationError('No valid source dates for latest-date anchor.')
                        end=pd.Timestamp(value).normalize()
                    start=end-pd.Timedelta(days=days-1)
                else:
                    if set(dr)!={'start','end'}:raise QueryValidationError('Provide both start and end dates.')
                    try:
                        start=pd.Timestamp(dr['start']);end=pd.Timestamp(dr['end'])
                        if pd.isna(start) or pd.isna(end):raise QueryValidationError()
                        if start.tzinfo:start=start.tz_convert('UTC').tz_localize(None)
                        if end.tzinfo:end=end.tz_convert('UTC').tz_localize(None)
                        start=start.normalize();end=end.normalize()
                    except Exception:raise QueryValidationError('Invalid start/end date.')
                    anchor='explicit'
                    if start>end or (end-start).days>3650:raise QueryValidationError('Invalid date range span.')
                where.append('TRY_CAST('+_qid(datecol)+' AS TIMESTAMP)>=? AND TRY_CAST('+_qid(datecol)+' AS TIMESTAMP)<?')
                params += [start.to_pydatetime(),(end+pd.Timedelta(days=1)).to_pydatetime()]
                effective={'column':datecol,'start':str(start.date()),'end':str(end.date()),'anchor':anchor,'inclusive_days':(end-start).days+1}
            select=[_qid(x) for x in dims]+[s['metrics'][x][0]+' AS '+_qid(x) for x in metrics]
            sql='SELECT '+','.join(select)+' FROM dataset'
            if where:sql+=' WHERE '+' AND '.join('('+x+')' for x in where)
            if dims:sql+=' GROUP BY '+','.join(_qid(x) for x in dims)
            sql+=' ORDER BY '+_qid(metrics[0])+' DESC LIMIT '+str(limit+1)
            records=c.execute(sql,params).df().to_dict('records')
            truncated=len(records)>limit;records=records[:limit]
            payload={'status':'ok','dataset':name,'source':s['source'],'mode':s['mode'],
                     'classification':'Local dashboard data; synthetic status is not independently verified. Only approved demo/sanitized sources may be used.',
                     'filters':filters,'sidebar_scope':scope,'unsupported_scope':unsupported_scope,'date_range':effective,'metric_definitions':{x:s['metrics'][x][1] for x in metrics},
                     'rows':records,'truncated':truncated}
            while len(_json(payload).encode('utf-8'))>MAX_BYTES and payload['rows']:
                payload['rows'].pop();payload['truncated']=True
            if len(_json(payload).encode('utf-8'))>MAX_BYTES:raise QueryValidationError('Result metadata exceeds payload limit.')
            return _json(payload)
    except Exception as e:return _error(e)
