"""Isolated synthetic UI tests; no real sources, auth state or database required."""
import ast,importlib.util,sys,types
from pathlib import Path
import pandas as pd
import pytest

@pytest.fixture
def ui(monkeypatch,tmp_path):
    components=types.ModuleType('src.components');components.header=lambda *a:None
    data=types.ModuleType('src.data');data.DATA=tmp_path;data.ENVS=['Production','Sandbox']
    data.get_apps=lambda:pd.DataFrame({'status':['Active','Inactive','Operational']})
    data.get_models=lambda:pd.DataFrame({'name':['Model A','Model B'],'risk':['High','Low']})
    data.get_health=lambda:pd.DataFrame({'date':pd.date_range('2026-10-01',periods=7),
        'requests':[240000]*7,'success_rate':[95.1]*7,'environment':['Production']*7})
    data.synthetic_alerts=lambda:pd.DataFrame({'title':['Demo action'],'status':['Open']})
    provider=types.ModuleType('src.provider');provider.PROVIDER_COLORS={'Azure':'#1768ff','AWS':'#f2a93b','GCP':'#39b98a'}
    for name,value in [('src.components',components),('src.data',data),('src.provider',provider)]:monkeypatch.setitem(sys.modules,name,value)
    path=Path(__file__).resolve().parents[1]/'src/executive_ui.py'
    spec=importlib.util.spec_from_file_location('compact_ui_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setitem(sys.modules,'compact_ui_test',module)
    return module

def test_count_helpers_unchanged(ui):
    d=ui._trend_data(ui.get_health(),pd.Timestamp('2026-10-01'),pd.Timestamp('2026-10-07'),['Production'])
    assert (d.successful_requests+d.failed_requests==d.total_requests).all()
    assert d.iloc[0].successful_requests==228240
    assert d.iloc[0].failed_requests==11760

def test_three_lines_and_compact_legend(ui):
    d=ui._trend_data(ui.get_health(),pd.Timestamp('2026-10-01'),pd.Timestamp('2026-10-07'),['Production'])
    fig=ui._trend_chart(d)
    assert len(fig.data)==3 and all(t.type=='scatter' and t.mode=='lines+markers' for t in fig.data)
    assert fig.layout.height==280 and fig.layout.legend.orientation=='h' and fig.layout.legend.y<0

def test_donut_height(ui):
    fig=ui._provider_chart(ui._synthetic_provider())
    assert fig.layout.height==280 and fig.data[0].hole==.62

def test_incomplete_date_range(ui):
    date=pd.Timestamp('2026-10-01').date()
    assert ui._range((date,))==(pd.Timestamp(date),pd.Timestamp(date))
    assert ui._range(()) is None

def test_no_global_zoom_or_overflow_hiding(ui):
    import inspect
    text=inspect.getsource(ui._compact_css)
    assert '.st-key-exec_compact_root' in text
    assert 'zoom:' not in text and 'overflow:hidden' not in text and 'transform:scale' not in text

def test_render_and_queue_toggle(ui):
    from streamlit.testing.v1 import AppTest
    at=AppTest.from_string('from compact_ui_test import render_executive\nrender_executive()',default_timeout=30).run()
    assert not at.exception
    assert len(at.dataframe)==0
    assert len(at.get('plotly_chart'))==2
    assert not at.expander[0].proto.expanded
    at.button(key='priority_actions_toggle').click().run()
    assert not at.exception and len(at.dataframe)==1
    at.button(key='priority_actions_toggle').click().run()
    assert not at.exception and len(at.dataframe)==0

def test_filter_keys_preserved(ui):
    from streamlit.testing.v1 import AppTest
    at=AppTest.from_string('from compact_ui_test import render_executive\nrender_executive()',default_timeout=30).run()
    assert not at.exception
    assert at.multiselect(key='exec_trend_models').value==['Model A','Model B']
    assert at.multiselect(key='exec_trend_env').value==['Production']
    assert len(at.date_input)==2
