"""Offline tests. All source fixtures below are explicitly synthetic."""
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
import sys
import duckdb
import pandas as pd
import pytest
from src import query_tools as qt
from src import agent


def run(**kwargs):
    return json.loads(qt.query_dashboard(json.dumps(kwargs)))

@pytest.fixture
def app_frame(monkeypatch):
    d=pd.DataFrame({
        'id':['A','B','C','D'], 'name':['private name']*4,
        'region':['Europe','Europe','Asia','Europe'],
        'environment':['Production','Production','Sandbox','Production'],
        'status':['Active','Dormant','Active','Active'],
        'platform':['NesGen']*4, 'recertification_status':['Pending']*4,
        'created_date':pd.to_datetime(['2026-10-01 23:00','2026-10-02','2026-10-10 18:00','2026-10-10 23:59'],format='mixed'),
        'expected_daily_users':[10,20,30,40], 'business_value':[100,200,300,400],
        'monthly_requests':[100,200,300,400], 'provider':['Azure']*4,
        'Azure':[.5]*4,'AWS':[.3]*4,'GCP':[.2]*4,
        'owner':['person@example.invalid']*4,
    })
    monkeypatch.setattr(qt.dashboard,'get_apps',lambda:d.copy())
    return d


def test_grouped_query_and_no_private_fields(app_frame):
    x=run(dataset='applications',dimensions=['region'],metrics=['unique_applications'])
    assert x['status']=='ok'
    assert {r['region']:r['unique_applications'] for r in x['rows']}=={'Europe':3,'Asia':1}
    assert 'private name' not in json.dumps(x) and 'person@' not in json.dumps(x)


def test_filters_and_numeric_aggregation(app_frame):
    x=run(dataset='applications',dimensions=['region'],metrics=['expected_daily_users'],
          filters=[{'column':'status','op':'eq','value':'Active'},{'column':'expected_daily_users','op':'gte','value':20}])
    assert sum(r['expected_daily_users'] for r in x['rows'])==70


def test_ten_inclusive_calendar_days(app_frame):
    x=run(dataset='applications',metrics=['application_rows'],date_range={'days':10,'as_of':'latest'})
    assert x['date_range']['start']=='2026-10-01'
    assert x['date_range']['end']=='2026-10-10'
    assert x['rows'][0]['application_rows']==4


def test_explicit_end_includes_entire_day(app_frame):
    x=run(dataset='applications',metrics=['application_rows'],date_range={'start':'2026-10-10','end':'2026-10-10'})
    assert x['rows'][0]['application_rows']==2


def test_today_does_not_silently_anchor_to_old_data(app_frame):
    x=run(dataset='applications',metrics=['application_rows'],date_range={'days':1,'as_of':'today'})
    assert x['date_range']['anchor']=='today'
    assert x['date_range']['end']==str(pd.Timestamp.now(tz='UTC').date())


def test_provider_weighting_reconciles(app_frame):
    x=run(dataset='provider_usage',dimensions=['provider'],metrics=['allocated_monthly_requests'])
    assert x['status']=='ok'
    values={r['provider']:r['allocated_monthly_requests'] for r in x['rows']}
    assert values=={'Azure':500.,'AWS':300.,'GCP':200.}
    assert 'estimate' in x['metric_definitions']['allocated_monthly_requests']


def test_5000_row_adapter_snapshot(monkeypatch,app_frame):
    d=pd.concat([app_frame]*1250,ignore_index=True)
    monkeypatch.setattr(qt.dashboard,'get_apps',lambda:d)
    x=run(dataset='applications',metrics=['application_rows'])
    assert x['rows'][0]['application_rows']==5000


def test_one_snapshot_per_question(monkeypatch,app_frame):
    mock=MagicMock(return_value=app_frame)
    monkeypatch.setattr(qt.dashboard,'get_apps',mock)
    with qt.query_session():
        qt.get_apps();qt.get_apps()
        run(dataset='applications',metrics=['application_rows'])
    assert mock.call_count==1

@pytest.mark.parametrize('bad',[
 {'dataset':'applications','sql':'DROP TABLE x','metrics':['application_rows']},
 {'dataset':"read_parquet('https://bad.invalid')",'metrics':['events']},
 {'dataset':'applications','dimensions':['owner'],'metrics':['application_rows']},
 {'dataset':'applications','dimensions':['region; DROP TABLE x'],'metrics':['application_rows']},
 {'dataset':'applications','metrics':['SUM(secret)']},
 {'dataset':'applications','metrics':['application_rows'],'limit':101},
 {'dataset':'applications','metrics':['application_rows'],'filters':[{'column':'owner','op':'eq','value':'x'}]},
 {'dataset':'applications','metrics':['application_rows'],'filters':[{'column':'region','op':'like','value':'%'}]},
 {'dataset':'applications','metrics':['application_rows'],'date_range':{'days':0}},
 {'dataset':'applications','metrics':['application_rows'],'date_range':{'days':10,'start':'2026-01-01'}},
 {'dataset':'applications','metrics':['application_rows'],'filters':[{'column':'region','op':'in','value':[]}]},
])
def test_rejects_unapproved_queries(app_frame,bad):
    assert run(**bad)['status']=='error'


def test_sql_injection_in_value_is_literal(app_frame):
    x=run(dataset='applications',metrics=['application_rows'],filters=[{'column':'region','op':'eq','value':"Europe' OR 1=1 --"}])
    assert x['status']=='ok' and x['rows'][0]['application_rows']==0


def test_query_budget(app_frame):
    with qt.query_session():
        for _ in range(8):assert run(dataset='applications',metrics=['application_rows'])['status']=='ok'
        assert run(dataset='applications',metrics=['application_rows'])['status']=='error'


def test_catalog_and_definitions(app_frame):
    assert 'new_relic' in qt.list_datasets()
    d=json.loads(qt.describe_dataset('applications'))
    assert 'owner' not in d['dimensions']
    assert 'expected_daily_users' in d['metrics']
    assert 'not observed active users' in qt.get_metric_definition('applications','expected_daily_users')


def test_sqlite_read_only_and_allowlisted_columns(tmp_path,monkeypatch):
    p=tmp_path/'demo.db'
    with sqlite3.connect(p) as c:
        c.execute('CREATE TABLE provider_charges(provider TEXT,provider_bill REAL,platform_usage REAL,variance REAL,status TEXT,api_key TEXT)')
        c.execute("INSERT INTO provider_charges VALUES('AWS',100,90,10,'Review','NEVER_SEND')")
        c.execute('CREATE TABLE secrets(secret TEXT)')
    monkeypatch.setattr(qt.dashboard,'DB',p)
    x=run(dataset='sqlite_charges',dimensions=['provider'],metrics=['provider_invoice','unexplained_amount'])
    assert x['status']=='ok' and x['rows'][0]['unexplained_amount']==10
    assert 'NEVER_SEND' not in json.dumps(x)
    assert run(dataset='secrets',metrics=['application_rows'])['status']=='error'
    with sqlite3.connect(p) as c:assert c.execute('SELECT COUNT(*) FROM provider_charges').fetchone()[0]==1


def make_parquet(tmp_path,folder,frame):
    d=tmp_path/folder;d.mkdir()
    with duckdb.connect() as c:
        c.register('fixture',frame)
        c.execute('COPY fixture TO ? (FORMAT PARQUET)',[str(d/'part.parquet')])


def test_new_relic_parquet_aggregation(tmp_path,monkeypatch):
    frame=pd.DataFrame({
        'Timestamp_1':['2026-10-01T00:00:00Z','2026-10-10T23:59:00Z'],
        'Attributes.BusinessKeys.provider':['Azure','AWS'],
        'Attributes.BusinessKeys.environment':['PROD','DEV'],
        'Attributes.BusinessKeys.model':['m1','m2'],
        'Attributes.BusinessKeys.service':['s1','s2'],
        'Attributes.BusinessKeys.responseTime':[100,300],
        'Attributes.BusinessKeys.total_tokens':[10,20],
        'Attributes.BusinessKeys.total_cost':[.1,.2],
        'SeverityText':['INFO','ERROR'],'Body.Message':['SECRET','SECRET']})
    make_parquet(tmp_path,'NewRelic',frame)
    monkeypatch.setattr(qt.dashboard,'DATA',tmp_path)
    x=run(dataset='new_relic',metrics=['events','total_tokens','p95_latency_ms','non_error_event_percent'],date_range={'days':10,'as_of':'latest'})
    assert x['status']=='ok',x
    r=x['rows'][0]
    assert r['events']==2 and r['total_tokens']==30
    assert r['p95_latency_ms']==pytest.approx(290) and r['non_error_event_percent']==50
    assert 'SECRET' not in json.dumps(x)


def test_log_analytics_parquet(tmp_path,monkeypatch):
    frame=pd.DataFrame({'TimeGenerated':['2026-10-10'],'environment_s':['DEV'],'model_s':['m1'],
                        'service_s':['svc'],'responseTime_d':[123],'usage_total_tokens_d':[99]})
    make_parquet(tmp_path,'LogAnalytics',frame)
    monkeypatch.setattr(qt.dashboard,'DATA',tmp_path)
    x=run(dataset='log_analytics',dimensions=['environment'],metrics=['events','total_tokens'])
    assert x['status']=='ok' and x['rows'][0]['total_tokens']==99


def test_missing_parquet_does_not_invent_fallback(tmp_path,monkeypatch):
    monkeypatch.setattr(qt.dashboard,'DATA',tmp_path)
    assert run(dataset='new_relic',metrics=['events'])['status']=='error'


def test_bounded_result(app_frame,monkeypatch):
    d=pd.concat([app_frame]*100,ignore_index=True);d['region']=['R'+str(i) for i in range(len(d))]
    monkeypatch.setattr(qt.dashboard,'get_apps',lambda:d)
    raw=qt.query_dashboard(json.dumps({'dataset':'applications','dimensions':['region'],'metrics':['application_rows'],'limit':100}))
    x=json.loads(raw)
    assert len(x['rows'])<=100 and len(raw.encode())<=12000 and x['truncated']



def test_no_key_is_safe(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    with pytest.raises(RuntimeError,match='missing'):agent.ask('hello','configured-model')
