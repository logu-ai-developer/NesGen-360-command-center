from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
@pytest.fixture(autouse=True)
def isolate_operational_db(tmp_path,monkeypatch):
    from src import data,storage,usage
    db=tmp_path/'test.db'
    monkeypatch.setattr(data,'DB',db);monkeypatch.setattr(storage,'DB',db);monkeypatch.setattr(usage,'DB',db)
    # Never read or mutate the user's real workbook/Parquet data during startup tests.
    monkeypatch.setattr(data,'DATA',tmp_path/'sources')
    monkeypatch.setattr(data,'HUB_XLSX',tmp_path/'missing_hub.xlsx')
    monkeypatch.setattr(data,'MODEL_XLSX',tmp_path/'missing_models.xlsx')

@pytest.fixture(autouse=True)
def authenticated_legacy_tests(request,isolate_operational_db):
    """Legacy dashboard tests use an explicit test admin, not a production bypass."""
    from src import auth
    auth.bind(None)
    if request.node.path.name=='test_login_patch.py':
        yield
    else:
        from src import auth_ui
        auth.bootstrap_admin('test_admin','Test-only long passphrase 123!')
        token=auth.login('test_admin','Test-only long passphrase 123!')
        auth.bind(token)
        # Existing page tests exercise authenticated routes; login tests exercise real gate.
        def test_gate():
            auth.bind(token)
            return auth.principal(token)
        request.getfixturevalue('monkeypatch').setattr(auth_ui,'gate',test_gate)
        yield
    auth.bind(None)
