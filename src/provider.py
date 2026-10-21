import pandas as pd
PROVIDERS=['Azure','AWS','GCP']
PROVIDER_COLORS={'Azure':'#1768ff','AWS':'#f2a93b','GCP':'#39b98a'}
def normalize_allocations(df):
    d=df.copy()
    for c in PROVIDERS:
        values=d[c] if c in d else pd.Series(0.,index=d.index)
        d[c]=pd.to_numeric(values,errors='coerce').fillna(0).clip(lower=0).astype(float)
    total=d[PROVIDERS].sum(axis=1);valid=total>0
    d.loc[valid,PROVIDERS]=d.loc[valid,PROVIDERS].div(total[valid],axis=0)
    for c in PROVIDERS:
        match=(~valid)&d.get('provider',pd.Series('',index=d.index)).astype(str).str.contains(c,case=False,na=False,regex=False)
        d.loc[match,c]=1.
    total=d[PROVIDERS].sum(axis=1);valid=total>0
    d.loc[valid,PROVIDERS]=d.loc[valid,PROVIDERS].div(total[valid],axis=0)
    d.loc[~valid,PROVIDERS]=1/3
    return d

def provider_consumption(df):
    d=normalize_allocations(df)
    m=pd.to_numeric(d.get('monthly_requests',pd.Series(0.,index=d.index)),errors='coerce').fillna(0).clip(lower=0)
    out=pd.DataFrame({'provider':PROVIDERS,'monthly_requests':[float((m*d[c]).sum()) for c in PROVIDERS]})
    out=out[out.monthly_requests>0].copy();total=out.monthly_requests.sum()
    out['share_percent']=out.monthly_requests/total*100 if total else 0.
    return out
