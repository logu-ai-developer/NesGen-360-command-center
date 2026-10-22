from __future__ import annotations
from pathlib import Path
from datetime import date, timedelta
import os, sqlite3
import numpy as np
import pandas as pd
from src.provider import normalize_allocations

ROOT=Path(__file__).resolve().parents[1]
DATA=Path(os.getenv('NESGEN_DATA_DIR', ROOT/'data'))
DB=Path(os.getenv('NESGEN_SQLITE_PATH', DATA/'nesgen360.db'))
MODEL_XLSX=DATA/'Model details Page.xlsx'; HUB_XLSX=DATA/'ML_HUB_synthetic_5000rows.xlsx'
NR_GLOB=str(DATA/'NewRelic'/'*.parquet').replace('\\','/'); LA_GLOB=str(DATA/'LogAnalytics'/'*.parquet').replace('\\','/')
RNG=np.random.default_rng(360)
REGIONS=['Europe','Asia','Americas','AMEA']; PROVIDERS=['Azure','AWS','GCP']; ENVS=['Production','Pre-production','Sandbox']

def synthetic_apps(n=100):
    RNG=np.random.default_rng(360)
    names=['Knowledge Search Engine','AI Service Desk Assistant','Demand Forecast Copilot','Quality Insights Hub','Vendor Performance Analyzer','Document Intelligence','Recipe Assistant','Business Analytics Studio']
    created=pd.Timestamp('2025-11-01')+pd.to_timedelta(RNG.integers(0,350,n),unit='D')
    df=pd.DataFrame({'id':[f'APP-{i+1001}' for i in range(n)],'name':[names[i%len(names)] for i in range(n)],'region':RNG.choice(REGIONS,n,p=[.37,.30,.19,.14]),'environment':RNG.choice(ENVS,n,p=[.63,.21,.16]),'status':['Active']*62+['Dormant']*12+['Onboarding']*15+['New']*11,'provider':RNG.choice(PROVIDERS,n),'Azure':0.437,'AWS':0.345,'GCP':0.218,'expected_daily_users':RNG.integers(200,12000,n),'monthly_requests':RNG.integers(10000,1300000,n),'business_value':RNG.integers(100000,1900000,n),'owner':RNG.choice(['Regional Product','Employee Services','Supply Chain','Marketing','Data & Analytics'],n),'platform':RNG.choice(['Industrialization','Sandbox','NesGen API'],n),'created_date':created,'recertification_status':RNG.choice(['Certified','Pending','Due soon'],n,p=[.61,.24,.15])})
    # V1.1 use-case contract (docs/DATA_CONTRACTS.md): stage, segment, active_users
    df['use_case_stage']=np.where(df.platform=='Sandbox','Sandbox','Industrialized')
    df['segment']=RNG.choice(['B2B','B2C'],n,p=[.6,.4])
    df['active_users']=np.where(df.status.isin(['Active','New']),(df.expected_daily_users*RNG.uniform(.3,.9,n)).astype(int),0)
    return normalize_allocations(df)

def synthetic_models(n=32):
    RNG=np.random.default_rng(361)
    families=['GPT','Claude','Gemini','Llama','Mistral','Embedding','Vision','Speech']; stages=['Exploration','Sandbox validation','Industrialized','Retirement planned']
    df=pd.DataFrame({'id':[f'MOD-{100+i}' for i in range(n)],'name':[f'{families[i%8]} {3+i%5}.{i%3} Enterprise' for i in range(n)],'provider':RNG.choice(PROVIDERS,n,p=[.44,.31,.25]),'model_family':[families[i%8] for i in range(n)],'stage':RNG.choice(stages,n,p=[.19,.25,.44,.12]),'owner':RNG.choice(['Core AI Platform','Model Enablement','Innovation Team','Data Science CoE'],n),'evaluation_score':RNG.integers(62,98,n),'risk':RNG.choice(['Low','Medium','High'],n,p=[.47,.37,.16]),'lifecycle_status':RNG.choice(['Current','Review due','Migration assessment','Retirement approved'],n),'lifecycle_risk':RNG.choice(['Low','Medium','High'],n,p=[.5,.35,.15]),'risk_reason':RNG.choice(['None','Evaluation expires soon','Provider deprecation notice','Owner evidence incomplete'],n),'migration_required':RNG.choice(['No','Assess','Yes'],n,p=[.55,.3,.15]),'next_review_date':pd.date_range('2026-10-20',periods=n,freq='7D'),'retire_date':pd.NaT})
    df.loc[df.stage=='Retirement planned','retire_date']=pd.Timestamp('2027-03-31'); return df

def synthetic_health(days=90):
    RNG=np.random.default_rng(362)
    d=pd.date_range(end=pd.Timestamp('2026-10-17'),periods=days)
    requests=RNG.integers(145000,225000,days); failures=np.clip(RNG.normal(2.2,.7,days),.4,7.8); failures[-5]=8.6
    return pd.DataFrame({'date':d,'requests':requests,'success_rate':100-failures,'p95_latency_ms':RNG.integers(1550,3400,days),'cost':RNG.uniform(1900,3300,days),'environment':RNG.choice(['Production','Pre-production'],days,p=[.76,.24])})

def synthetic_charges():
    return pd.DataFrame({'provider':PROVIDERS,'provider_bill':[128400,89640,61250],'platform_usage':[126920,83010,60080],'variance':[1.15,7.40,1.91],'status':['Matched','Review','Matched'],'period':['Oct 2026']*3})

def synthetic_alerts():
    return pd.DataFrame([['ALT-2071','Critical','Elevated pre-production failure rate','Log Analytics','8.6% failures','Platform Support','Open'],['ALT-2064','High','Provider-to-platform usage variance','Reconciliation','7.4% variance','FinOps','Investigating'],['ALT-2058','Medium','Model evaluation nearing expiry','Lifecycle','12 days remaining','Model Enablement','Assigned']],columns=['id','severity','title','source','metric','owner','status'])

def _norm(df):
    df=df.copy();df.columns=[str(c).strip() for c in df.columns];return df


def _column(df,name,default=None):
    return df[name] if name in df else pd.Series(default,index=df.index)

def _number(df,name,default=0):
    return pd.to_numeric(_column(df,name,default),errors='coerce').fillna(default)

def _dates(values):
    return pd.to_datetime(values,errors='coerce',format='mixed',utc=True).dt.tz_localize(None)

def _source(domain,mode,detail,df):
    from src.storage import source
    source(domain,mode,detail,len(df))
    df.attrs.update(source_mode=mode,source_detail=detail)
    return df

def get_apps():
    if HUB_XLSX.exists():
        try:
            x=_norm(pd.read_excel(HUB_XLSX,engine='openpyxl'))
            if not {'Application ID','Region'}.issubset(x.columns):raise ValueError('Missing application identifiers or region')
            out=pd.DataFrame(index=x.index)
            mapping={'id':'Application ID','name':'APM Name','region':'Region','environment':'Environment','status':'LATEST STATUS OF USE CASE','provider':'Models','owner':'Functional Owner','platform':'Platform','recertification_status':'RECERTIFICATION STATUS'}
            for target,source in mapping.items():out[target]=_column(x,source)
            out['name']=out['name'].fillna(_column(x,'Use Case Name','Unnamed'))
            out['status']=out['status'].fillna(_column(x,'Use Case Status','Unknown'))
            # Platform is not an environment: do not silently equate them.
            out['environment']=out['environment'].fillna('Unknown')
            for c in ['region','provider','owner','platform','recertification_status']:out[c]=out[c].fillna('Unknown').astype('string')
            for c in ['Azure','AWS','GCP']:out[c]=_number(x,c)
            out['expected_daily_users']=_number(x,'Expected Daily Users').clip(lower=0)
            out['monthly_requests']=_number(x,'monthly_requests') if 'monthly_requests' in x else out.expected_daily_users*30
            out['request_basis']='measured/source' if 'monthly_requests' in x else 'estimated: expected daily users × 30'
            out['business_value']=_number(x,'Business Value')
            out['created_date']=_dates(_column(x,'Approval date'))
            # V1.1 use-case contract columns; 'Unknown' (never invented) when the workbook lacks them
            out['use_case_stage']=_column(x,'Use Case Stage','Unknown').fillna('Unknown').astype('string')
            out['segment']=_column(x,'Segment','Unknown').fillna('Unknown').astype('string')
            out['active_users']=_number(x,'Active Users')
            out=normalize_allocations(out.dropna(subset=['id']).reset_index(drop=True))
            if out.empty:raise ValueError('No valid application rows')
            return _source('applications','workbook',HUB_XLSX.name,out)
        except Exception as exc:
            return _source('applications','synthetic fallback','Workbook rejected: '+type(exc).__name__,synthetic_apps())
    return _source('applications','synthetic fallback','Workbook not present',synthetic_apps())

def normalize_model_dates(df):
    d=df.copy()
    for col in ['retire_date','next_review_date']:
        d[col]=_dates(_column(d,col))
    return d

def get_models():
    mode='synthetic fallback';detail='Workbook not present';out=synthetic_models()
    if MODEL_XLSX.exists():
        try:
            x=_norm(pd.read_excel(MODEL_XLSX,engine='openpyxl'))
            if not {'Model Name','Cloud Provider'}.issubset(x):raise ValueError('Missing model name/provider')
            out=pd.DataFrame(index=x.index);out['id']=['MOD-'+str(i+100) for i in range(len(x))]
            mapping={'name':'Model Name','provider':'Cloud Provider','model_family':'Model Family','stage':'governance_stage','owner':'accountable_owner','risk':'risk','lifecycle_status':'lifecycle_status','lifecycle_risk':'lifecycle_risk','risk_reason':'risk_reason','migration_required':'migration_required','next_review_date':'next_review_date','retire_date':'Retire Date','environment':'Environment'}
            for target,source in mapping.items():out[target]=_column(x,source)
            out['evaluation_score']=_number(x,'evaluation_score',75).clip(0,100)
            for col in ['name','provider','model_family','stage','owner','risk','lifecycle_status','lifecycle_risk','risk_reason','migration_required','environment']:out[col]=out[col].fillna('Unknown').astype('string')
            if out.empty:raise ValueError('Empty workbook')
            mode='workbook';detail=MODEL_XLSX.name
        except Exception as exc:out=synthetic_models();detail='Workbook rejected: '+type(exc).__name__
    from src.storage import local_models
    local=local_models()
    if local:out=pd.DataFrame(out.to_dict('records')+local)
    return _source('models',mode,detail,normalize_model_dates(out))

def get_health():
    files=list((DATA/'NewRelic').glob('*.parquet'))
    if files:
        try:
            import duckdb
            with duckdb.connect(config={'memory_limit':'512MB','threads':'2'}) as c:
                c.read_parquet([str(p) for p in files],union_by_name=True).create_view('events')
                d=c.execute('''SELECT TRY_CAST(substr("Timestamp_1",1,10) AS DATE) date,
                    COUNT(*) requests,
                    100.0*AVG(CASE WHEN coalesce("SeverityText",'INFO') NOT IN ('ERROR','FATAL') THEN 1 ELSE 0 END) success_rate,
                    quantile_cont(TRY_CAST("Attributes.BusinessKeys.responseTime" AS DOUBLE),.95) p95_latency_ms,
                    SUM(TRY_CAST("Attributes.BusinessKeys.total_cost" AS DOUBLE)) total_cost
                    FROM events GROUP BY 1 ORDER BY 1''').df()
            d=d.rename(columns={'total_cost':'cost'}).dropna(subset=['date'])
            if d.empty:raise ValueError('No valid telemetry dates')
            d.attrs['metric_note']='requests counts log events; success_rate is non-error event percentage, not deduplicated request success'
            return _source('health','parquet','NewRelic aggregate',d)
        except Exception as exc:return _source('health','synthetic fallback','Parquet rejected: '+type(exc).__name__,synthetic_health())
    return _source('health','synthetic fallback','Parquet not present',synthetic_health())


# ---- V1.1: platform-health drill-down (S: reviewer Level 1/2/3) -------------------------------
# Call = a NewRelic event classified by Body.Tracepoint (FLOW-END = success, FLOW-ERROR = failure).
# Events without a Tracepoint (e.g. LogAnalytics-schema rows) are reported as 'unclassified', not as successes.
import functools
SYNTH_MODELS=[('GPT-5.1','Azure OpenAI'),('Claude Sonnet 5.5','AWS Bedrock'),('Gemini 2.5 Pro','GCP Vertex AI'),('GPT-4o','Azure OpenAI'),('Claude 3.5 Sonnet','AWS Bedrock'),('Gemini 2.0 Flash','GCP Vertex AI')]

def _telemetry_signature():
    return tuple((p.name,p.stat().st_mtime_ns) for p in sorted((DATA/'NewRelic').glob('*.parquet')))

@functools.lru_cache(maxsize=2)
def _telemetry(signature):
    import duckdb
    files=[str(DATA/'NewRelic'/n) for n,_ in signature]
    with duckdb.connect(config={'memory_limit':'512MB','threads':'2'}) as c:
        c.read_parquet(files,union_by_name=True).create_view('raw')
        cols={r[0] for r in c.execute('DESCRIBE raw').fetchall()}
        need={'Body.Tracepoint','Attributes.BusinessKeys.model','Attributes.BusinessKeys.provider','Attributes.BusinessKeys.client_id','Attributes.BusinessKeys.responseTime','Error.errorCode','Error.errorMessage.errorMessage','Error.errorMessage.errorSource'}
        if not need.issubset(cols):raise ValueError('Telemetry schema lacks call/error fields')
        c.execute('''CREATE VIEW ev AS SELECT "Body.Tracepoint" tp,"Attributes.BusinessKeys.model" model,"Attributes.BusinessKeys.provider" provider,
            "Attributes.BusinessKeys.client_id" client,TRY_CAST("Attributes.BusinessKeys.responseTime" AS DOUBLE) rt,
            TRY_CAST("Error.errorCode" AS INTEGER) code,"Error.errorMessage.errorMessage" msg,"Error.errorMessage.errorSource" src FROM raw''')
        total,ok,bad,unclassified,p95=c.execute('''SELECT COUNT(*) FILTER (WHERE tp IN ('FLOW-END','FLOW-ERROR')),COUNT(*) FILTER (WHERE tp='FLOW-END'),
            COUNT(*) FILTER (WHERE tp='FLOW-ERROR'),COUNT(*) FILTER (WHERE tp IS NULL OR tp NOT IN ('FLOW-END','FLOW-ERROR')),
            quantile_cont(rt,.95) FILTER (WHERE tp IN ('FLOW-END','FLOW-ERROR')) FROM ev''').fetchone()
        by_model=c.execute('''SELECT model,provider,COUNT(*) calls,COUNT(*) FILTER (WHERE tp='FLOW-ERROR') failures FROM ev
            WHERE tp IN ('FLOW-END','FLOW-ERROR') AND model IS NOT NULL GROUP BY 1,2 ORDER BY failures DESC''').df()
        errors=c.execute('''SELECT code error_code,msg error_message,src error_source,COUNT(*) occurrences FROM ev WHERE tp='FLOW-ERROR'
            GROUP BY 1,2,3 ORDER BY occurrences DESC LIMIT 100''').df()
        clients=c.execute('''SELECT model,COUNT(DISTINCT client) unique_clients FROM ev WHERE model IS NOT NULL GROUP BY 1''').df()
    by_model['failure_rate']=100.0*by_model.failures/by_model.calls
    stats={'total':int(total),'success':int(ok),'failed':int(bad),'unclassified':int(unclassified),'p95_ms':float(p95) if p95==p95 and p95 is not None else None}
    return stats,by_model,errors,clients

def _synthetic_telemetry():
    h=synthetic_health();total=int(h.requests.sum());bad=int((h.requests*(100-h.success_rate)/100).sum())
    rng=np.random.default_rng(363);w=rng.dirichlet(np.ones(len(SYNTH_MODELS)))
    by_model=pd.DataFrame({'model':[m for m,_ in SYNTH_MODELS],'provider':[p for _,p in SYNTH_MODELS],'calls':(w*total).astype(int)})
    f=rng.dirichlet(np.ones(len(SYNTH_MODELS)))
    by_model['failures']=(f*bad).astype(int);by_model['failure_rate']=100.0*by_model.failures/by_model.calls
    errors=pd.DataFrame({'error_code':[503,429,400,403],'error_message':['Model unavailable','Rate limit exceeded','Content filter violation','Internal server error'],'error_source':['Azure OpenAI','AWS Bedrock','GCP Vertex AI','Azure OpenAI'],'occurrences':[int(bad*x) for x in (.3,.28,.22,.2)]})
    clients=pd.DataFrame({'model':by_model.model,'unique_clients':rng.integers(20,400,len(by_model))})
    stats={'total':total,'success':total-bad,'failed':bad,'unclassified':0,'p95_ms':float(h.p95_latency_ms.quantile(.95))}
    return stats,by_model,errors,clients

def get_telemetry():
    """Return dict(stats, by_model, errors, clients, mode). Falls back to labelled synthetic data."""
    try:
        sig=_telemetry_signature()
        if not sig:raise FileNotFoundError('no parquet')
        stats,by_model,errors,clients=_telemetry(sig);mode='parquet'
    except Exception:
        stats,by_model,errors,clients=_synthetic_telemetry();mode='synthetic'
    return {'stats':stats,'by_model':by_model,'errors':errors,'clients':clients,'mode':mode}

# ---- V1.1: model lifecycle intelligence -------------------------------------------------------
_RISK_POINTS={'low':15,'medium':8,'high':0}
_EVIDENCE_POINTS={'current':10,'review due':5,'action required':0}

def lifecycle_category(stage):
    s=str(stage).casefold()
    if 'sandbox' in s or 'exploration' in s:return 'Sandbox'
    if 'retire' in s:return 'Retirement'
    return 'Industrialized'

def enrich_models(models,clients=None,today=None):
    """Add category, unique clients, suggested replacement and decommission readiness (0-100).

    Replacement is DERIVED (not source data): another model, preferably same provider and family,
    that is not retiring sooner and not already retired/imminent; best evaluation score wins.
    Readiness = 40% evaluation score + 20 backup exists + 15 replacement risk + 15 time to retire + 10 evidence."""
    d=models.copy();today=pd.Timestamp(today or pd.Timestamp.now().normalize())
    d['lifecycle_category']=d['stage'].map(lifecycle_category)
    cl=dict(zip(clients.model,clients.unique_clients)) if clients is not None and len(clients) else {}
    d['unique_clients']=d['name'].map(cl)
    gone=d['lifecycle_status'].astype(str).str.contains('Retired|imminent',case=False)
    repl=[];rrisk=[];why=[]
    for i,r in d.iterrows():
        pool=d[(d.index!=i)&~gone]
        if pd.notna(r['retire_date']):pool=pool[pool['retire_date'].isna()|(pool['retire_date']>r['retire_date'])]
        same=pool[pool['provider']==r['provider']];fam=same[same['model_family']==r['model_family']]
        pick=fam if len(fam) else (same if len(same) else pool)
        if len(pick):
            b=pick.sort_values('evaluation_score',ascending=False).iloc[0];repl.append(b['name']);rrisk.append(str(b['risk']))
            why.append('same provider and family' if len(fam) else ('same provider' if len(same) else 'other provider'))
        else:repl.append(None);rrisk.append(None);why.append(None)
    d['suggested_replacement']=repl;d['replacement_risk']=rrisk;d['replacement_basis']=why;d['has_backup']=d['suggested_replacement'].notna()
    days=(d['retire_date']-today).dt.days
    time_pts=(days.clip(lower=90,upper=365)-90)/275*15
    time_pts=time_pts.fillna(15)
    ev=d.get('evaluation_evidence_status',pd.Series('current',index=d.index)).astype(str).str.casefold().map(_EVIDENCE_POINTS).fillna(5) if 'evaluation_evidence_status' in d else pd.Series(5,index=d.index)
    d['decommission_readiness']=(0.4*d['evaluation_score'].astype(float)+d['has_backup']*20+d['replacement_risk'].astype(str).str.casefold().map(_RISK_POINTS).fillna(0)+time_pts+ev).round(0).clip(0,100)
    return d
