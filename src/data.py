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

def synthetic_apps(n=114):
    RNG=np.random.default_rng(360)
    names=['Knowledge Search Engine','AI Service Desk Assistant','Demand Forecast Copilot','Quality Insights Hub','Vendor Performance Analyzer','Document Intelligence','Recipe Assistant','Business Analytics Studio']
    created=pd.Timestamp('2025-11-01')+pd.to_timedelta(RNG.integers(0,350,n),unit='D')
    df=pd.DataFrame({'id':[f'APP-{i+1001}' for i in range(n)],'name':[names[i%len(names)] for i in range(n)],'region':RNG.choice(REGIONS,n,p=[.37,.30,.19,.14]),'environment':RNG.choice(ENVS,n,p=[.63,.21,.16]),'status':['Active']*72+['Dormant']*14+['Onboarding']*17+['New']*11,'provider':RNG.choice(PROVIDERS,n),'Azure':0.437,'AWS':0.345,'GCP':0.218,'expected_daily_users':RNG.integers(200,12000,n),'monthly_requests':RNG.integers(10000,1300000,n),'business_value':RNG.integers(100000,1900000,n),'owner':RNG.choice(['Regional Product','Employee Services','Supply Chain','Marketing','Data & Analytics'],n),'platform':RNG.choice(['Industrialization','Sandbox','NesGen API'],n),'created_date':created,'recertification_status':RNG.choice(['Certified','Pending','Due soon'],n,p=[.61,.24,.15])})
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
