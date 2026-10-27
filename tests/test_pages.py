from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
# Administration, Solution design, Requirements and Demo & tests are internal scaffolding hidden from navigation
# (Administration hidden 2026-10-26 usability review); they keep their ROUTES entries but cannot be selected from the
# sidebar radio, so they are not exercised here.
PAGES=['Executive overview','Platform health','Model lifecycle','User adoption','Chargeback','AI assistant']
@pytest.mark.parametrize('page',PAGES)
def test_page_fallback(page):
    at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception
    assert not at.error,[(page,x.value) for x in at.error]

@pytest.mark.parametrize('page',PAGES)
def test_page_source_backed(page,tmp_path,monkeypatch):
    import pandas as pd
    from src import data
    hub=tmp_path/'hub.xlsx';hub.touch();models=tmp_path/'models.xlsx';models.touch()
    monkeypatch.setattr(data,'HUB_XLSX',hub);monkeypatch.setattr(data,'MODEL_XLSX',models)
    applications=pd.DataFrame({'Application ID':[f'APP-{i}' for i in range(5000)],
        'APM Name':['Demo application']*5000,'Region':['Europe']*5000,
        'Environment':['Production']*5000,'LATEST STATUS OF USE CASE':['Active']*5000,
        'Models':['Gemini']*5000,'Azure':[50]*5000,'AWS':[30]*5000,'GCP':[20]*5000,
        'Expected Daily Users':[10]*5000,'Business Value':[100]*5000,'Approval date':['2026-10-01']*5000})
    model_frame=pd.DataFrame({'Model Name':['Demo model'],'Cloud Provider':['Azure'],
        'governance_stage':['Industrialized'],'risk':['Low'],'lifecycle_status':['Current'],
        'Retire Date':['Not announced'],'next_review_date':['2027-01-01']})
    monkeypatch.setattr(pd,'read_excel',lambda p,**kw:applications.copy() if Path(p)==hub else model_frame.copy())
    at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception
    assert not at.error,[(page,x.value) for x in at.error]
