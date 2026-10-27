from __future__ import annotations
from pathlib import Path
from datetime import date, timedelta
import os, sqlite3, hashlib
import numpy as np
import pandas as pd
from src.provider import normalize_allocations
from src.metrics import outcome_sql,outcome_summary

ROOT=Path(__file__).resolve().parents[1]
DATA=Path(os.getenv('NESGEN_DATA_DIR', ROOT/'data'))
DB=Path(os.getenv('NESGEN_SQLITE_PATH', DATA/'nesgen360.db'))
MODEL_XLSX=DATA/'Model details Page.xlsx'; HUB_XLSX=DATA/'ML_HUB_synthetic_5000rows.xlsx'
NR_GLOB=str(DATA/'NewRelic'/'*.parquet').replace('\\','/'); LA_GLOB=str(DATA/'LogAnalytics'/'*.parquet').replace('\\','/')
RNG=np.random.default_rng(360)
REGIONS=['Europe','Asia','Americas','AMEA']; PROVIDERS=['Azure','AWS','GCP']; ENVS=['Production','Pre-production','Sandbox']

SYNTH_END=pd.Timestamp('2026-10-17')   # fixed anchor: synthetic data never drifts with the wall clock

UNDATED_K=5   # WS-4 (UA-09): fixed number of demo use cases with no approval date, so the "without approval date" path is visible

def _synthetic_approval_dates(n):
    """Deterministic approval dates (approval dates only, never activity): ~20% older than 180 days, two approval spikes
    (days 100-106 and 12-16 before SYNTH_END) and the rest spread over the window with a zero-approval gap on days 40-69.
    UNDATED_K of the already-out-of-window older rows then become NaT (WS-4/UA-09) so demo shows undated use cases."""
    rng=np.random.default_rng(364)
    older=round(n*.20);spike_a=round(n*.22);spike_b=round(n*.14);rest=n-older-spike_a-spike_b
    allowed=np.array([x for x in range(180) if not 40<=x<=69])
    offsets=np.concatenate([rng.integers(181,360,older),rng.integers(100,107,spike_a),rng.integers(12,17,spike_b),rng.choice(allowed,rest)])
    rng.shuffle(offsets)
    created=np.asarray(SYNTH_END-pd.to_timedelta(offsets,unit='D'),dtype='datetime64[ns]')
    # Convert only rows already older than every approval window (offset>=181) to undated. The RNG stream, draw sizes and
    # shuffle are untouched, so the 30/90/180-day window counts and the canonical total are preserved; just a few
    # older-dated rows lose their date. Done after the dates are fully generated (Option C).
    created[np.where(offsets>=181)[0][:UNDATED_K]]=np.datetime64('NaT')
    return created

def synthetic_apps(n=100):
    RNG=np.random.default_rng(360)
    names=['Knowledge Search Engine','AI Service Desk Assistant','Demand Forecast Copilot','Quality Insights Hub','Vendor Performance Analyzer','Document Intelligence','Recipe Assistant','Business Analytics Studio']
    RNG.integers(0,350,n)   # original draw kept so every other synthetic column is unchanged
    created=_synthetic_approval_dates(n)
    df=pd.DataFrame({'id':[f'APP-{i+1001}' for i in range(n)],'name':[names[i%len(names)] for i in range(n)],'region':RNG.choice(REGIONS,n,p=[.37,.30,.19,.14]),'environment':RNG.choice(ENVS,n,p=[.63,.21,.16]),'status':['Active']*62+['Dormant']*12+['Onboarding']*15+['New']*11,'provider':RNG.choice(PROVIDERS,n),'Azure':0.437,'AWS':0.345,'GCP':0.218,'expected_daily_users':RNG.integers(200,12000,n),'monthly_requests':RNG.integers(10000,1300000,n),'business_value':RNG.integers(100000,1900000,n),'owner':RNG.choice(['Regional Product','Employee Services','Supply Chain','Marketing','Data & Analytics'],n),'platform':RNG.choice(['Industrialization','Sandbox','NesGen API'],n),'created_date':created,'recertification_status':RNG.choice(['Certified','Pending','Due soon'],n,p=[.61,.24,.15])})
    # V1.1 use-case contract (docs/DATA_CONTRACTS.md): stage, segment, active_users
    df['use_case_stage']=np.where(df.platform=='Sandbox','Sandbox','Industrialized')
    df['segment']=RNG.choice(['B2B','B2C'],n,p=[.6,.4])
    # Synthetic ESTIMATE derived from expected users; not observed identities or measured activity.
    df['active_users']=np.where(df.status.isin(['Active','New']),(df.expected_daily_users*RNG.uniform(.3,.9,n)).astype(int),0)
    df=normalize_allocations(df);df.attrs['active_users_basis']='synthetic estimate'
    return df

# Realistic illustrative model catalogue (name, provider, family). Names match the synthetic telemetry model names where
# possible so cross-domain joins (model -> telemetry footprint) line up. Illustrative synthetic only, never a real source.
MODEL_CATALOG=[('GPT-5.1','Azure','GPT'),('GPT-5','Azure','GPT'),('GPT-4.1','Azure','GPT'),('GPT-4o','Azure','GPT'),
               ('GPT-4o mini','Azure','GPT'),('o3','Azure','O-Series'),('o3-mini','Azure','O-Series'),('o1','Azure','O-Series'),
               ('Phi-4','Azure','Phi'),('text-embedding-3-large','Azure','Embedding'),('DALL-E 3','Azure','Vision'),
               ('Claude Opus 5.5','AWS','Claude'),('Claude Sonnet 5.5','AWS','Claude'),('Claude Haiku 5.5','AWS','Claude'),
               ('Claude 3.7 Sonnet','AWS','Claude'),('Claude 3.5 Sonnet','AWS','Claude'),('Claude 3.5 Haiku','AWS','Claude'),
               ('Titan Text G1','AWS','Titan'),('Llama 3.1 70B','AWS','Llama'),('Mistral Large 2','AWS','Mistral'),
               ('Cohere Command R+','AWS','Cohere'),
               ('Gemini 2.5 Pro','GCP','Gemini'),('Gemini 2.5 Flash','GCP','Gemini'),('Gemini 2.0 Pro','GCP','Gemini'),
               ('Gemini 2.0 Flash','GCP','Gemini'),('Gemini 1.5 Pro','GCP','Gemini'),('Gemini 1.5 Flash','GCP','Gemini'),
               ('PaLM 2','GCP','PaLM'),('Imagen 3','GCP','Vision'),('Chirp 2','GCP','Speech'),('Codey','GCP','Code'),('MedLM','GCP','Gemini')]

def synthetic_models(n=32):
    """Deterministic, illustrative model inventory shaped for the demo: 14 Industrialized, 12 Sandbox, 6 Retirement
    (lifecycle_category derives from stage; the three add up to the total). Realistic names from MODEL_CATALOG.
    Illustrative synthetic only, never a real source."""
    RNG=np.random.default_rng(361)
    cat=MODEL_CATALOG[:n]; m=len(cat)
    names=[c[0] for c in cat]; providers=[c[1] for c in cat]; families=[c[2] for c in cat]
    # Retiring set: for n=32, 6 named models — 4 in large families (they get a same-family replacement -> amber) and 2
    # High-risk singleton-family models (no same-family option -> no replacement -> red). Category target: 14
    # Industrialized / 12 Sandbox / 6 Retirement. For other n, fall back to a deterministic ~6/32 retiring share.
    RETIRING_AMBER=['GPT-4o mini','o1','Claude 3.5 Haiku','Gemini 1.5 Flash']; RETIRING_RED=['Titan Text G1','PaLM 2']
    retiring_names=set(RETIRING_AMBER)|set(RETIRING_RED)
    if m>=32:
        is_retiring=np.array([nm in retiring_names for nm in names]); target_sand=12
    else:
        is_retiring=np.zeros(m,dtype=bool); is_retiring[RNG.permutation(m)[:max(1,round(m*6/32))]]=True; target_sand=max(0,m-max(1,round(m*14/32))-int(is_retiring.sum()))
    stage=np.array(['Industrialized']*m,dtype=object); stage[is_retiring]='Retirement planned'
    non_ret=np.where(~is_retiring)[0]; n_sand=min(len(non_ret),target_sand)
    stage[non_ret[RNG.permutation(len(non_ret))[:n_sand]]]='Sandbox validation'   # deterministic sandbox split among the active models
    stage=list(stage); stage_arr=np.array(stage,dtype=object)
    retiring=stage_arr=='Retirement planned'; indus=stage_arr=='Industrialized'; ind_idx=np.where(indus)[0]
    risk=RNG.choice(['Low','Medium','High'],m,p=[.55,.35,.10])
    risk[np.isin(names,RETIRING_RED)]='High'                                       # the 2 red retiring models are High-risk singletons (no replacement)
    risk[np.isin(names,RETIRING_AMBER)]='Medium'                                   # the 4 amber retiring models keep a same-family replacement
    lifecycle_status=np.array(['Current']*m,dtype=object); lifecycle_status[retiring]='Retirement approved'
    lifecycle_status[ind_idx[RNG.permutation(len(ind_idx))[:3]]]='Review due'      # 3 industrialized models due for review
    # Migration aligns exactly with the retiring models, so the Retirement category, the Retirement/migrate lens and the
    # decommission traffic-light all reflect the same 6 models (they tally).
    migration=np.array(['No']*m,dtype=object); migration[retiring]='Yes'
    retire_date=np.where(retiring,np.datetime64('2027-03-31'),np.datetime64('NaT')).astype('datetime64[ns]')
    df=pd.DataFrame({'id':[f'MOD-{100+i}' for i in range(m)],'name':names,'provider':providers,'model_family':families,
        'stage':stage,'owner':RNG.choice(['Core AI Platform','Model Enablement','Innovation Team','Data Science CoE'],m),
        'evaluation_score':RNG.integers(68,98,m),'risk':risk,'lifecycle_status':lifecycle_status,'lifecycle_risk':risk,
        'risk_reason':RNG.choice(['None','Evaluation expires soon','Provider deprecation notice','Owner evidence incomplete'],m),
        'migration_required':migration,'next_review_date':pd.date_range('2026-10-20',periods=m,freq='7D'),'retire_date':retire_date})
    # Illustrative Internal/External replacement availability, mostly Internal so the decommission traffic-light is green-dominant.
    df['availability']=np.where(RNG.random(m)<.82,'Internal','External')
    # Lifecycle dates spread over the 180 days before SYNTH_END (next_review_date / retire_date untouched).
    drng=np.random.default_rng(365)
    def within(mask):
        mask=np.asarray(mask); out=pd.Series(pd.NaT,index=df.index,dtype='datetime64[ns]')
        out[mask]=SYNTH_END-pd.to_timedelta(drng.integers(0,180,int(mask.sum())),unit='D')
        return out
    df['last_review_date']=within(np.ones(m,dtype=bool))
    df['review_due_date']=within(df.lifecycle_status.str.contains('Review').to_numpy())
    df['retirement_decision_date']=within((df.stage.eq('Retirement planned')|df.lifecycle_status.eq('Retirement approved')).to_numpy())
    df['migration_date']=within(df.migration_required.isin(['Assess','Yes']).to_numpy())
    return df

def synthetic_health(days=180):
    """Deterministic daily telemetry (seed 362). Scenarios are placed by days before SYNTH_END: degraded period (100-125),
    recovery (70-99), error spikes (150-151, plus the planted 8.6% day at 4), latency spikes (140-142 and the degraded
    period) and unclassified-event spikes (160-164 and 30-32)."""
    RNG=np.random.default_rng(362)
    d=pd.date_range(end=SYNTH_END,periods=days)
    requests=RNG.integers(145000,225000,days);failures=np.clip(RNG.normal(1.2,.4,days),.3,4.0)
    latency=RNG.integers(1550,3400,days).astype(float);cost=RNG.uniform(1900,3300,days);env=RNG.choice(['Production','Pre-production'],days,p=[.76,.24])
    off=days-1-np.arange(days)
    degraded=(off>=100)&(off<=125);recovery=(off>=70)&(off<=99)
    failures=np.where(degraded,failures+4.5,failures)
    failures=np.where(recovery,failures+3.0*(off-70)/29,failures)
    failures=np.where(np.isin(off,[150,151]),9.5,failures);failures[off==4]=8.6
    latency=np.where(degraded,latency*1.5,latency);latency=np.where((off>=140)&(off<=142),latency*2.2,latency)
    unclassified_share=np.zeros(days);unclassified_share[(off>=160)&(off<=164)]=.30;unclassified_share[(off>=30)&(off<=32)]=.22
    unclassified=np.round(requests*unclassified_share).astype(int);classified=requests-unclassified
    failed=np.round(classified*np.clip(failures,0,15)/100).astype(int)
    return pd.DataFrame({'date':d,'requests':requests,'successful_calls':classified-failed,'failed_calls':failed,'unclassified_events':unclassified,'success_rate':100*(classified-failed)/classified,'p95_latency_ms':latency.astype(int),'cost':cost,'environment':env})

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
            # Rows without an application ID are preserved (never dropped or invented); canonical counts disclose them.
            out=normalize_allocations(out.reset_index(drop=True))
            if out.empty:raise ValueError('No valid application rows')
            out.attrs['active_users_basis']='reported' if 'Active Users' in x else 'not supplied'
            return _source('applications','workbook',HUB_XLSX.name,out)
        except Exception as exc:
            return _source('applications','synthetic fallback','Workbook rejected: '+type(exc).__name__,synthetic_apps())
    return _source('applications','synthetic fallback','Workbook not present',synthetic_apps())

def normalize_model_dates(df):
    d=df.copy()
    for col in ['retire_date','next_review_date','last_review_date','review_due_date','retirement_decision_date','migration_date']:
        d[col]=_dates(_column(d,col))
    return d

def get_models(demo=False):
    """Model inventory. demo=True returns the deterministic synthetic scenario inventory (the POC default, so the whole
    app runs on one consistent synthetic dataset); demo=False reads the real workbook when present (kept for the hidden
    real-data path and the metric-correctness tests)."""
    out=synthetic_models();mode='synthetic scenario' if demo else 'synthetic fallback';detail=('Demo Scenario Data: deterministic synthetic model inventory' if demo else 'Workbook not present')
    if not demo and MODEL_XLSX.exists():
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
    out['record_origin']='catalog'
    if local:
        out=pd.DataFrame(out.to_dict('records')+[{**r,'record_origin':'locally registered'} for r in local])
        detail+=f' + {len(local)} locally registered'
    return _source('models',mode,detail,normalize_model_dates(out))

def get_health(demo=False):
    """Daily health frame. demo=True returns the deterministic synthetic scenario (never real telemetry) and, unlike a
    fallback, does not overwrite the recorded source status of the real adapter."""
    if demo:
        d=synthetic_health();d.attrs.update(source_mode='synthetic scenario',source_detail='Demo Scenario Data: deterministic synthetic telemetry')
        return d
    files=list((DATA/'NewRelic').glob('*.parquet'))
    if files:
        try:
            import duckdb
            with duckdb.connect(config={'memory_limit':'512MB','threads':'2'}) as c:
                c.read_parquet([str(p) for p in files],union_by_name=True).create_view('raw')
                # Same canonical classification as the Level 1 cards (src/metrics.py); a row without a
                # Tracepoint marker is Unclassified, never assumed successful.
                tp='"Body.Tracepoint"' if 'Body.Tracepoint' in {r[0] for r in c.execute('DESCRIBE raw').fetchall()} else 'CAST(NULL AS VARCHAR)'
                c.execute(f'''CREATE VIEW events AS SELECT TRY_CAST(substr("Timestamp_1",1,10) AS DATE) AS event_day,{outcome_sql(tp)} AS outcome,
                    TRY_CAST("Attributes.BusinessKeys.responseTime" AS DOUBLE) AS rt,TRY_CAST("Attributes.BusinessKeys.total_cost" AS DOUBLE) AS cost FROM raw''')
                d=c.execute('''SELECT event_day AS date,COUNT(*) AS requests,
                    COUNT(*) FILTER (WHERE outcome='Successful') successful_calls,
                    COUNT(*) FILTER (WHERE outcome='Failed') failed_calls,
                    COUNT(*) FILTER (WHERE outcome='Unclassified') unclassified_events,
                    100.0*COUNT(*) FILTER (WHERE outcome='Successful')/NULLIF(COUNT(*) FILTER (WHERE outcome<>'Unclassified'),0) success_rate,
                    quantile_cont(rt,.95) FILTER (WHERE outcome<>'Unclassified') p95_latency_ms,
                    SUM(cost) total_cost
                    FROM events GROUP BY 1 ORDER BY 1''').df()
            d=d.rename(columns={'total_cost':'cost'}).dropna(subset=['date'])
            if d.empty:raise ValueError('No valid telemetry dates')
            d.attrs['metric_note']='requests counts log events; success_rate is the daily classified-call success rate (successful / (successful + failed) x 100, NULL when a day has no classified calls); unclassified events are excluded from the denominator; not verified availability or deduplicated request success'
            return _source('health','parquet','NewRelic aggregate',d)
        except Exception as exc:return _source('health','synthetic fallback','Parquet rejected: '+type(exc).__name__,synthetic_health())
    return _source('health','synthetic fallback','Parquet not present',synthetic_health())


# ---- V1.1: platform-health drill-down (S: reviewer Level 1/2/3) -------------------------------
# Call = a NewRelic event classified by Body.Tracepoint (FLOW-END = success, FLOW-ERROR = failure).
# Events without a Tracepoint (e.g. LogAnalytics-schema rows) are reported as 'unclassified', not as successes.
import functools
SYNTH_MODELS=[('GPT-5.1','Azure OpenAI'),('Claude Sonnet 5.5','AWS Bedrock'),('Gemini 2.5 Pro','GCP Vertex AI'),('GPT-4o','Azure OpenAI'),('Claude 3.5 Sonnet','AWS Bedrock'),('Gemini 2.0 Flash','GCP Vertex AI')]
# Review item 8: a fixed, consistent synthetic error taxonomy (code, message, category, source). The category is the
# structure the Error Analysis Assistant reasons over; shares (below) drive both the error table and the error->model
# breakdown so they stay internally consistent. Real telemetry is never categorised this way (real-honest).
ERROR_CATALOG=[(503,'Model unavailable','Upstream provider error','Azure OpenAI'),
               (429,'Rate limit exceeded','Rate limit / Quota','AWS Bedrock'),
               (400,'Content filter violation','Bad request / Validation','GCP Vertex AI'),
               (500,'Internal server error','Server error','Azure OpenAI')]
ERROR_SHARES=(.30,.28,.22,.20)
# Static reference (standard meaning + typical mitigation) per error code, for the Platform Health "Error code reference"
# table. General knowledge of standard API error codes; not a per-environment root-cause claim.
ERROR_CODE_REFERENCE={
    400:('Request rejected as invalid or blocked by a content filter.','Validate and sanitise inputs; adjust the prompt or content-filter rules.'),
    401:('Authentication failed (missing or invalid credentials).','Check and rotate the API key or token; confirm the credential is authorised.'),
    403:('Authorisation denied for the requested resource.','Confirm the caller has access to the model/region; review role assignments.'),
    408:('The request timed out before completing.','Add a timeout with retry and backoff; reduce payload size.'),
    429:('Caller exceeded the allowed request or token rate (rate limit / quota).','Add client-side backoff with jitter; request a quota increase; NesGen platform team to increase the deployment quota for the expected traffic.'),
    500:('Provider hit an unexpected internal server error.','Retry with backoff; if it persists, raise it with the provider.'),
    503:('Model or upstream provider temporarily unavailable.','Retry with backoff and fail over to a healthy model or region.'),
    504:('Upstream gateway timed out.','Retry with backoff; check provider status and reduce request size.'),
}

def error_reference_table(errors):
    """A 6-column reference for the error codes present in `errors`: Error code, Message, Category, Occurrences,
    Meaning and How to reduce. Meaning/How to reduce come from the static ERROR_CODE_REFERENCE (general knowledge)."""
    if errors is None or not len(errors):
        return pd.DataFrame(columns=['Error code','Message','Category','Occurrences','Meaning','How to reduce'])
    df=errors.copy()
    def _ref(code,i):
        try:return ERROR_CODE_REFERENCE.get(int(code),('Not catalogued','Review the error message and source as logged.'))[i]
        except (TypeError,ValueError):return 'Not catalogued' if i==0 else 'Review the error message and source as logged.'
    out=pd.DataFrame({'Error code':df.error_code,'Message':df.get('error_message',''),
                      'Category':df.get('error_category','Not available'),'Occurrences':df.get('occurrences',0),
                      'Meaning':[_ref(c,0) for c in df.error_code],'How to reduce':[_ref(c,1) for c in df.error_code]})
    return out.reset_index(drop=True)

def error_breakdown_table(breakdown,provider=None,top=20):
    """Real per-(provider, model, error code) failure breakdown with the code meaning, for the Platform Health error
    table. Occurrences = failed classified calls with that error code on that model. `provider` scopes to one provider.
    Available only for synthetic/demo telemetry (real telemetry does not link errors to a model/provider)."""
    cols=['Provider','Model','Error code','Message','Failed occurrences','Meaning']
    if breakdown is None or not len(breakdown):
        return pd.DataFrame(columns=cols)
    df=breakdown.copy()
    if provider and str(provider)!='All providers':
        df=df[df.provider.astype(str)==str(provider)]
    df=df.sort_values('occurrences',ascending=False).head(top)
    def _mean(code):
        try:return ERROR_CODE_REFERENCE.get(int(code),('Not catalogued',''))[0]
        except (TypeError,ValueError):return 'Not catalogued'
    out=pd.DataFrame({'Provider':df.provider,'Model':df.model,'Error code':df.error_code,'Message':df.error_message,
                      'Failed occurrences':df.occurrences,'Meaning':[_mean(c) for c in df.error_code]})
    return out.reset_index(drop=True)

def _telemetry_signature():
    return tuple((p.name,p.stat().st_mtime_ns) for p in sorted((DATA/'NewRelic').glob('*.parquet')))

@functools.lru_cache(maxsize=4)
def _telemetry(signature,start=None,end=None):
    """Aggregates for the optional inclusive [start, end] event-date window (ISO dates). Events with no timestamp cannot
    be placed in a window: they are excluded from it and reported as stats['undated_events']."""
    import duckdb
    files=[str(DATA/'NewRelic'/n) for n,_ in signature]
    with duckdb.connect(config={'memory_limit':'512MB','threads':'2'}) as c:
        c.read_parquet(files,union_by_name=True).create_view('raw')
        cols={r[0] for r in c.execute('DESCRIBE raw').fetchall()}
        need={'Timestamp_1','Body.Tracepoint','Attributes.BusinessKeys.model','Attributes.BusinessKeys.provider','Attributes.BusinessKeys.client_id','Attributes.BusinessKeys.responseTime','Error.errorCode','Error.errorMessage.errorMessage','Error.errorMessage.errorSource'}
        if not need.issubset(cols):raise ValueError('Telemetry schema lacks call/error fields')
        c.execute('''CREATE VIEW evall AS SELECT TRY_CAST(substr("Timestamp_1",1,10) AS DATE) AS day,"Body.Tracepoint" AS tp,"Attributes.BusinessKeys.model" model,"Attributes.BusinessKeys.provider" provider,
            "Attributes.BusinessKeys.client_id" client,TRY_CAST("Attributes.BusinessKeys.responseTime" AS DOUBLE) rt,
            TRY_CAST("Error.errorCode" AS INTEGER) code,"Error.errorMessage.errorMessage" msg,"Error.errorMessage.errorSource" src FROM raw''')
        undated=c.execute('SELECT COUNT(*) FROM evall WHERE day IS NULL').fetchone()[0]
        where=f"WHERE day BETWEEN DATE '{pd.Timestamp(start).date()}' AND DATE '{pd.Timestamp(end).date()}'" if start and end else ''
        c.execute(f'CREATE VIEW ev AS SELECT * FROM evall {where}')
        ok,bad,unclassified,p95=c.execute(f'''SELECT COUNT(*) FILTER (WHERE o='Successful'),COUNT(*) FILTER (WHERE o='Failed'),
            COUNT(*) FILTER (WHERE o='Unclassified'),quantile_cont(rt,.95) FILTER (WHERE o<>'Unclassified')
            FROM (SELECT {outcome_sql('tp')} o,rt FROM ev)''').fetchone()
        # Missing model/provider stays visible as 'Unknown' so the tables reconcile to classified calls.
        by_model=c.execute(f'''SELECT coalesce(model,'Unknown') model,coalesce(provider,'Unknown') provider,COUNT(*) calls,
            COUNT(*) FILTER (WHERE tp='FLOW-ERROR') failures FROM ev
            WHERE {outcome_sql('tp')}<>'Unclassified' GROUP BY 1,2 ORDER BY failures DESC''').df()
        by_provider=c.execute(f'''SELECT coalesce(provider,'Unknown') provider,COUNT(*) calls,COUNT(*) FILTER (WHERE tp='FLOW-ERROR') failures FROM ev
            WHERE {outcome_sql('tp')}<>'Unclassified' GROUP BY 1 ORDER BY failures DESC''').df()
        errors=c.execute('''SELECT code error_code,msg error_message,src error_source,COUNT(*) occurrences FROM ev WHERE tp='FLOW-ERROR'
            GROUP BY 1,2,3 ORDER BY occurrences DESC LIMIT 100''').df()
        clients=c.execute('''SELECT model,COUNT(DISTINCT client) unique_clients FROM ev WHERE model IS NOT NULL GROUP BY 1''').df()
    for frame in (by_model,by_provider):frame['failure_rate']=100.0*frame.failures/frame.calls
    stats={**outcome_summary(ok,bad,unclassified),'p95_ms':float(p95) if p95 is not None and p95==p95 else None,'undated_events':int(undated)}
    return stats,by_model,by_provider,errors,clients

def _synthetic_telemetry(window=None):
    h=synthetic_health()
    if window is not None:h=h[window.mask(h.date)]
    total=int(h.requests.sum());unc=int(h.unclassified_events.sum());bad=int(h.failed_calls.sum());classified=total-unc
    rng=np.random.default_rng(363);w=rng.dirichlet(np.ones(len(SYNTH_MODELS)))
    calls=(w*classified).astype(int)
    if classified:calls[-1]+=classified-calls.sum()
    by_model=pd.DataFrame({'model':[m for m,_ in SYNTH_MODELS],'provider':[p for _,p in SYNTH_MODELS],'calls':calls})
    f=rng.dirichlet(np.ones(len(SYNTH_MODELS)))
    failures=(f*bad).astype(int)
    if bad:failures[-1]+=bad-failures.sum()
    by_model['failures']=failures
    by_model=by_model[by_model.calls>0].reset_index(drop=True)
    by_model['failure_rate']=100.0*by_model.failures/by_model.calls
    by_provider=by_model.groupby('provider',as_index=False)[['calls','failures']].sum().sort_values('failures',ascending=False)
    by_provider['failure_rate']=100.0*by_provider.failures/by_provider.calls
    # Review item P4.2 (2026-10-26): each model exhibits a DETERMINISTIC SUBSET of error codes (not every code), so the
    # Error Analysis Assistant only ever shows a model's real codes (e.g. a model with no 500 never shows one).
    # error_breakdown carries code, message and category per provider+model; the window-wide `errors` table is derived
    # from it so the two always agree.
    _nc=len(ERROR_CATALOG);rows=[]
    for r in by_model.itertuples():
        f=int(r.failures)
        if f<=0:continue
        mi=next((j for j,(mn,_) in enumerate(SYNTH_MODELS) if mn==r.model),0)
        idxs=[mi%_nc,(mi+2)%_nc]                                  # two distinct codes per model
        alloc=[int(f*w) for w in (.6,.4)];alloc[-1]+=f-sum(alloc)
        for ci,n in zip(idxs,alloc):
            if n>0:
                code,msg,cat,_=ERROR_CATALOG[ci];rows.append((r.model,r.provider,code,msg,cat,int(n)))
    error_breakdown=pd.DataFrame(rows,columns=['model','provider','error_code','error_message','error_category','occurrences'])
    _src={c:s for c,_,_,s in ERROR_CATALOG}
    if len(error_breakdown):
        errors=error_breakdown.groupby(['error_code','error_message','error_category'],as_index=False).occurrences.sum().sort_values('occurrences',ascending=False).reset_index(drop=True)
        errors['error_source']=errors.error_code.map(_src);errors=errors[['error_code','error_message','error_category','error_source','occurrences']]
    else:
        errors=pd.DataFrame(columns=['error_code','error_message','error_category','error_source','occurrences'])
    clients=pd.DataFrame({'model':[m for m,_ in SYNTH_MODELS],'unique_clients':rng.integers(20,400,len(SYNTH_MODELS))})
    stats={**outcome_summary(classified-bad,bad,unc),'p95_ms':float(h.p95_latency_ms.quantile(.95)) if len(h) else None,'undated_events':0}
    return stats,by_model,by_provider,errors,clients,error_breakdown

def get_telemetry(window=None,demo=False):
    """Return dict(stats, by_model, by_provider, errors, clients, error_breakdown, mode) for the optional TimeWindow.

    error_breakdown (error category x provider x model) is populated only for the synthetic/demo telemetry, which carries a
    consistent error taxonomy; the real telemetry aggregates are not categorised, so there it is None (real-honest)."""
    start,end=(str(window.window_start.date()),str(window.window_end.date())) if window is not None else (None,None)
    if demo:
        stats,by_model,by_provider,errors,clients,error_breakdown=_synthetic_telemetry(window)
        return {'stats':stats,'by_model':by_model,'by_provider':by_provider,'errors':errors,'clients':clients,'error_breakdown':error_breakdown,'mode':'synthetic scenario'}
    try:
        sig=_telemetry_signature()
        if not sig:raise FileNotFoundError('no parquet')
        stats,by_model,by_provider,errors,clients=_telemetry(sig,start,end);mode='parquet';error_breakdown=None
    except Exception:
        stats,by_model,by_provider,errors,clients,error_breakdown=_synthetic_telemetry(window);mode='synthetic fallback'
    return {'stats':stats,'by_model':by_model,'by_provider':by_provider,'errors':errors,'clients':clients,'error_breakdown':error_breakdown,'mode':mode}

# ---- V1.1: model lifecycle intelligence -------------------------------------------------------
_RISK_POINTS={'low':20,'medium':10,'high':0}
_EVIDENCE_POINTS={'current':20,'review due':10,'action required':0}
_EVIDENCE_LABELS={'current':'Complete','review due':'Review due','action required':'Incomplete'}
# Illustrative Decommission Readiness Score: factor -> maximum points (sums to 100). Current-model quality is deliberately excluded.
SCORE_WEIGHTS={'Replacement candidate exists':35,'Candidate risk level':20,'Time before retirement':25,'Evaluation evidence status':20}
NO_CANDIDATE='No suitable candidate identified'

def lifecycle_category(stage):
    s=str(stage).casefold()
    if 'sandbox' in s or 'exploration' in s:return 'Sandbox'
    if 'retire' in s:return 'Retirement'
    return 'Industrialized'

def _has(series,pattern):return series.astype(str).str.contains(pattern,case=False,na=False)

def review_status(d,today):
    """Review obligation only: Overdue (next review date passed), Review due (status says so), else Current."""
    due=pd.to_datetime(d['next_review_date'],errors='coerce')<today if 'next_review_date' in d else pd.Series(False,index=d.index)
    flagged=_has(d['lifecycle_status'],'Review') if 'lifecycle_status' in d else pd.Series(False,index=d.index)
    return pd.Series(np.select([due,flagged],['Overdue','Review due'],'Current'),index=d.index)

def retirement_status(d,today=None):
    """Retirement stance only: Retired, Scheduled (date, stage or approval), Candidate (migration assess/yes) or None.

    A model with a FUTURE retire date is Scheduled, never Retired, even if its lifecycle_status label says 'Retired'
    (review item follow-up, 2026-10-26): 'Retired' must not contradict a retire date that has not arrived yet."""
    today=pd.Timestamp(today or pd.Timestamp.now().normalize())
    future_retire=d['retire_date'].notna()&(pd.to_datetime(d['retire_date'],errors='coerce')>today)
    retired=_has(d['lifecycle_status'],'Retired|imminent')&~future_retire
    scheduled=d['retire_date'].notna()|_has(d['stage'],'retire')|_has(d['lifecycle_status'],'Retirement approved')|future_retire
    candidate=d['migration_required'].astype(str).isin(['Assess','Yes'])
    return pd.Series(np.select([retired,scheduled,candidate],['Retired','Scheduled','Candidate'],'None'),index=d.index)


def _derive_availability(name):
    """Deterministic illustrative Internal/External flag for a model that has no sourced availability field (e.g. a
    workbook model). Stable per name; ~60% Internal. Illustrative synthetic only, never a sourced fact."""
    return 'Internal' if int(hashlib.md5(str(name).encode()).hexdigest(),16)%10<8 else 'External'

def enrich_models(models,clients=None,today=None):
    """Add category, unique clients, status concepts, suggested candidate and readiness factors.

    Suggested candidate is DERIVED (not source data, not an approval): never the same model, never retired,
    scheduled for retirement or unsuitable (High risk or incomplete
    evidence). Same provider and family preferred; best evaluation score wins; None when nothing qualifies.
    decommission_readiness is an ILLUSTRATIVE 0-100 score built from SCORE_WEIGHTS."""
    d=models.copy();today=pd.Timestamp(today or pd.Timestamp.now().normalize())
    d['lifecycle_category']=d['stage'].map(lifecycle_category)
    cl=dict(zip(clients.model,clients.unique_clients)) if clients is not None and len(clients) else {}
    d['unique_clients']=d['name'].map(cl)
    d['review_status']=review_status(d,today);d['retirement_status']=retirement_status(d,today)
    if 'availability' not in d:d['availability']=d['name'].astype(str).map(_derive_availability)   # workbook models carry no availability; derive an illustrative one so readiness/assistant are not blank
    evkey=d['evaluation_evidence_status'].astype(str).str.casefold() if 'evaluation_evidence_status' in d else pd.Series('',index=d.index)
    unsuitable=(d['risk'].astype(str).str.casefold()=='high')|(evkey=='action required')
    excluded=d['retirement_status'].isin(['Retired','Scheduled'])|unsuitable
    repl=[];rrisk=[];why=[];rscore=[]
    for i,r in d.iterrows():
        pool=d[(d.index!=i)&(d['name']!=r['name'])&~excluded]
        # Suggest a replacement by tier (2026-10-26 update; broadened from the earlier same-family-only rule so a
        # retiring model is not left without any suitable option): prefer the same model family, else the same provider,
        # else the best-scoring suitable model anywhere. The pool still excludes retired / scheduled / High-risk /
        # incomplete-evidence models, so a suggestion is never an unsuitable model; when the whole pool is excluded
        # there is no candidate.
        fam=pool[pool['model_family']==r['model_family']]
        prov=pool[pool['provider']==r['provider']]
        if len(fam):pick,basis=fam,'same model family'
        elif str(r['risk']).casefold()=='high':pick,basis=None,None                  # a High-risk model gets ONLY a same-family replacement; no cross-family/provider substitute, so a High-risk singleton-family model genuinely has no replacement (reads red)
        elif len(prov):pick,basis=prov,'same provider'
        elif len(pool):pick,basis=pool,'best available model'
        else:pick,basis=None,None
        if pick is not None and len(pick):
            # Prefer an internally available candidate (then best evaluation score), so a retiring model with an in-house
            # replacement reads green rather than external-only amber.
            ranked=pick.assign(_internal=pick['availability'].astype(str).str.casefold().eq('internal')).sort_values(['_internal','evaluation_score'],ascending=[False,False])
            b=ranked.iloc[0];repl.append(b['name']);rrisk.append(str(b['risk']));rscore.append(b['evaluation_score']);why.append(basis)
        else:repl.append(None);rrisk.append(None);why.append(None);rscore.append(None)
    d['suggested_replacement']=repl;d['replacement_risk']=rrisk;d['replacement_basis']=why;d['replacement_score']=rscore;d['has_backup']=d['suggested_replacement'].notna()
    # Review item 4: the suggested candidate's availability (Internal / External). Workbook models carry no availability
    # field, so it stays missing (treated as external-only by the status rule below).
    avail_map=dict(zip(d['name'],d['availability'])) if 'availability' in d else {}
    d['replacement_availability']=d['suggested_replacement'].map(avail_map) if avail_map else pd.Series(pd.NA,index=d.index)
    days=(d['retire_date']-today).dt.days
    time_pts=((days.clip(lower=90,upper=365)-90)/275*SCORE_WEIGHTS['Time before retirement']).fillna(SCORE_WEIGHTS['Time before retirement'])
    ev_pts=evkey.map(_EVIDENCE_POINTS).fillna(10)
    d['replacement_readiness']=np.where(d['has_backup'],'Candidate identified','No suitable candidate')
    d['migration_readiness']=d['migration_required'].astype(str).map({'No':'Not required','Assess':'Assessment needed','Yes':'Migration needed'}).fillna('Unknown')
    d['evidence_completeness']=evkey.map(_EVIDENCE_LABELS).fillna('Not available')
    urgency=pd.cut(days,[-10**6,0,90,180,10**6],labels=['Past date','Within 90 days','Within 180 days','Later']).astype(object)
    d['retirement_urgency']=urgency.where(days.notna(),'No date set').where(d['retirement_status']!='Retired','Retired')
    d['decommission_readiness']=(d['has_backup']*SCORE_WEIGHTS['Replacement candidate exists']+d['replacement_risk'].astype(str).str.casefold().map(_RISK_POINTS).fillna(0)+time_pts+ev_pts).round(0).clip(0,100)
    # Retire/replace traffic-light, read like a normal traffic-light (green = good, red = risk):
    # green  = active, not scheduled for retirement (no action)
    # amber  = retiring AND a suitable replacement is available (manageable)
    # red    = retiring AND no suitable replacement exists (risk)
    retiring=d['retirement_status'].isin(['Scheduled','Candidate'])
    d['decommission_readiness_status']=np.select(
        [retiring&d['has_backup'],retiring&~d['has_backup']],
        ['Retiring: replacement available','Retiring: no replacement'],
        'Active (not retiring)')
    return d
