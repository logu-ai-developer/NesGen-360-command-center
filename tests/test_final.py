import json
import pandas as pd
import pytest
from src.data import synthetic_apps,get_apps,get_models,get_health,synthetic_charges
from src.provider import normalize_allocations,provider_consumption
from src.agent import get_adoption_summary,get_model_lifecycle_summary,get_platform_health_summary,get_executive_summary,POLICY
from src.usage import init,summary

def test_source_or_fallback_contracts():
 a=get_apps();m=get_models();h=get_health();c=synthetic_charges()
 assert len(a)>=114 and {'Azure','AWS','GCP','monthly_requests','region','status'}.issubset(a.columns)
 assert len(m)>=32 and {'name','provider','risk','stage','evaluation_score'}.issubset(m.columns)
 assert len(h)>=1 and pd.to_numeric(h.success_rate,errors='coerce').between(0,100).all()
 assert len(c)==3 and float(c.loc[c.provider=='AWS','variance'].iloc[0])==7.4

def test_provider_allocations_and_reconciliation():
 a=normalize_allocations(get_apps());totals=a[['Azure','AWS','GCP']].sum(axis=1)
 assert totals.between(.999,1.001).all()
 p=provider_consumption(a)
 assert p.monthly_requests.sum()==pytest.approx(pd.to_numeric(a.monthly_requests,errors='coerce').fillna(0).sum())

def test_fallback_provider_distribution():
 p=provider_consumption(synthetic_apps()).set_index('provider').share_percent
 assert p['Azure']==pytest.approx(43.7,abs=.2);assert p['AWS']==pytest.approx(34.5,abs=.2);assert p['GCP']==pytest.approx(21.8,abs=.2)

def test_exact_windows_and_grounding():
 assert get_adoption_summary(10)['days']==10 and get_adoption_summary(90)['days']==90
 assert get_model_lifecycle_summary()['count']==len(get_models())
 assert get_platform_health_summary(10)['days']==10
 assert 'ONLY from function results' in POLICY and 'Never use external knowledge' in POLICY

def test_executive_provider_payload():
 x=get_executive_summary();assert len(x['provider_consumption'])==3 and x['source']=='Dashboard: Executive overview'

def test_usage_migration():
 init();u=summary();assert {'today','tokens60'}==set(u)

def test_navigation_and_gemini_chat_contract():
 app=open('app.py',encoding='utf-8').read();agent=open('src/agent.py',encoding='utf-8').read()
 for n in ['Executive overview','Model lifecycle','Platform health','User adoption','Chargeback','AI assistant','Administration','Solution design','Requirements','Demo & tests']:assert n in app
 assert 'client.chats.create' in agent and 'chat.send_message' in agent
 assert 'models.generate_content' not in agent
 assert 'config=' in app
