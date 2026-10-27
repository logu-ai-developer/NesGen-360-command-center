"""Cross-domain context for the bounded assistants (review item: AI value, option C, 2026-10-26).

Joins grounded facts across reliability, cost and governance so the Model Evaluation and Error Analysis assistants can
synthesise a priority that a single page cannot show. Provider is the reliable join key (telemetry 'Azure OpenAI' ->
'Azure'); model-name alignment across telemetry and the governance workbook is best-effort and is disclosed as "not
matched" when absent. Every value here is a real number from a real adapter -- nothing forms a conclusion; the
assistant does the weighing. These helpers add FACTS to the evidence, never a verdict."""
from __future__ import annotations
import pandas as pd
from src.metrics import fmt_pct

_PROVIDER_ALIASES = {'azure': 'Azure', 'aws': 'AWS', 'bedrock': 'AWS', 'gcp': 'GCP', 'google': 'GCP', 'vertex': 'GCP'}


def normalize_provider(name):
    """Map a telemetry/governance provider label to canonical Azure / AWS / GCP (else pass through)."""
    s = str(name).casefold()
    for key, canon in _PROVIDER_ALIASES.items():
        if key in s:
            return canon
    return str(name)


def provider_context(provider, models=None, charges=None):
    """Grounded cost + governance facts for a provider (canonical Azure/AWS/GCP)."""
    from src.data import get_models, synthetic_charges
    canon = normalize_provider(provider)
    m = models if models is not None else get_models()
    mp = m[m['provider'].astype(str).map(normalize_provider) == canon] if len(m) else m
    high = int((mp['risk'].astype(str).str.casefold() == 'high').sum()) if len(mp) else 0
    review = int(mp['lifecycle_status'].astype(str).str.contains('Review', case=False, na=False).sum()) if len(mp) else 0
    c = charges if charges is not None else synthetic_charges()
    cp = c[c['provider'].astype(str).map(normalize_provider) == canon] if len(c) else c
    if len(cp):
        var = float(cp['variance'].iloc[0])
        variance = f"{var:.2f}% ({'above' if var > 5 else 'within'} the 5% threshold)"
    else:
        variance = 'N/A'
    return {'provider': canon, 'models': int(len(mp)), 'high_risk': high, 'review_due': review, 'variance': variance}


def model_governance_match(model_name, models=None):
    """Governance standing of a telemetry model name, or None when it is not in the governance inventory."""
    from src.data import get_models
    m = models if models is not None else get_models()
    if not len(m):
        return None
    hit = m[m['name'].astype(str).str.casefold() == str(model_name).casefold()]
    if not len(hit):
        return None
    r = hit.iloc[0]
    return {'risk': str(r.get('risk')), 'lifecycle_status': str(r.get('lifecycle_status'))}


def model_telemetry_footprint(model_name, tel=None):
    """Reliability footprint of a governance model name in telemetry, or None when there is no telemetry match."""
    from src.data import get_telemetry
    t = tel if tel is not None else get_telemetry()
    bm = t.get('by_model')
    if bm is None or not len(bm):
        return None
    hit = bm[bm['model'].astype(str).str.casefold() == str(model_name).casefold()]
    if not len(hit):
        return None
    calls, failures = int(hit['calls'].sum()), int(hit['failures'].sum())
    return {'calls': f"{calls:,}", 'failures': f"{failures:,}", 'rate': fmt_pct(100.0 * failures / calls) if calls else 'N/A'}


def _provider_line(pc):
    return f"{pc['provider']}: chargeback variance {pc['variance']}; {pc['high_risk']} high-risk and {pc['review_due']} review-due governance models"


def error_context(tel, provider, model):
    """Cross-domain context for the leading failing provider/model (grounded facts only, for the Error assistant)."""
    out = {'Leading provider context (cost & governance)': _provider_line(provider_context(provider))}
    gov = model_governance_match(model)
    out['Leading model governance match'] = (f"{model}: risk {gov['risk']}, {gov['lifecycle_status']}" if gov
                                             else f"{model}: not matched to the governance inventory")
    clients = tel.get('clients') if isinstance(tel, dict) else None
    if clients is not None and len(clients):
        ch = clients[clients['model'].astype(str) == str(model)]
        if len(ch):
            out['Leading model adoption'] = f"{int(ch['unique_clients'].iloc[0]):,} unique API clients"
    return out


def model_context(row):
    """Cross-domain context for a governance model under review (grounded facts only, for the Model assistant)."""
    foot = model_telemetry_footprint(str(row['name']))
    footprint = (f"{foot['failures']} failed of {foot['calls']} classified calls (failure rate {foot['rate']})"
                 if foot else 'No telemetry match for this model name')
    return {'Operational Footprint (telemetry)': footprint,
            'Provider Context (cost & governance)': _provider_line(provider_context(row.get('provider')))}
