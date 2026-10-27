from pathlib import Path
import sqlite3,time
import pytest
from src import auth,storage
PASS='Test-only long passphrase 123!'

@pytest.fixture
def accounts():
    auth.bootstrap_admin('admin_123',PASS)
    auth.register_end_user('end_user_123',PASS,'Demo user',auth.GROUPS[1])

def test_no_admin_by_default():assert not auth.has_admin()

def _app():
    from streamlit.testing.v1 import AppTest
    return AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30)

def test_secrets_bootstrap_creates_admin_and_opens_login(monkeypatch):
    # Hosted deploy with no committed DB: ADMIN_* secrets create the admin on first run.
    monkeypatch.setenv('ADMIN_USERNAME','deploy_admin');monkeypatch.setenv('ADMIN_PASSWORD',PASS)
    at=_app().run()
    assert not at.exception and auth.has_admin()
    assert auth.login('deploy_admin',PASS)                                   # the secret-created admin can sign in
    assert not any('First-time setup' in w.value for w in at.warning)        # setup screen skipped
    assert any(t.label=='Username' for t in at.text_input)                   # sign-in form is shown instead

def test_without_secret_setup_screen_stays_and_no_admin(monkeypatch):
    monkeypatch.delenv('ADMIN_USERNAME',raising=False);monkeypatch.delenv('ADMIN_PASSWORD',raising=False)
    at=_app().run()
    assert not at.exception and not auth.has_admin()
    assert any('First-time setup' in w.value for w in at.warning)

def test_short_secret_password_is_refused_without_crashing(monkeypatch):
    from src import auth_ui
    monkeypatch.setenv('ADMIN_PASSWORD','short')                             # under the 15-char policy
    auth_ui._bootstrap_admin_from_secrets()
    assert not auth.has_admin()                                             # refused, no admin, no exception

def test_secrets_bootstrap_is_idempotent_and_keeps_first_admin(monkeypatch):
    from src import auth_ui
    auth.bootstrap_admin('admin_123',PASS)                                   # an admin already exists
    monkeypatch.setenv('ADMIN_USERNAME','deploy_admin');monkeypatch.setenv('ADMIN_PASSWORD','A different passphrase 999!')
    auth_ui._bootstrap_admin_from_secrets()                                  # must not create a second admin
    assert auth.login('admin_123',PASS) and auth.login('deploy_admin','A different passphrase 999!') is None

def test_registration_requires_local_setup():
    with pytest.raises(ValueError,match='setup'):auth.register_end_user('someone',PASS,'Demo',auth.GROUPS[0])

def test_hash_is_salted_and_not_plaintext():
    a=auth.hash_password(PASS);b=auth.hash_password(PASS)
    assert a!=b and PASS not in a and auth.verify_password(PASS,a)
    assert not auth.verify_password('wrong',a)

@pytest.mark.parametrize('password',['short','x'*129])
def test_password_policy(password):
    with pytest.raises(ValueError):auth.hash_password(password)

def test_registration_always_end_user(accounts):
    token=auth.login('END_USER_123',PASS)
    assert auth.principal(token)['role']=='end_user'
    with pytest.raises(TypeError):auth.register_end_user('badrole',PASS,'Demo',auth.GROUPS[0],role='admin')

def test_second_admin_refused(accounts):
    with pytest.raises(ValueError):auth.bootstrap_admin('another_admin',PASS)

def test_duplicate_registration_cannot_reset_password(accounts):
    with pytest.raises(ValueError):auth.register_end_user('admin_123','Another long password 456!','Demo',auth.GROUPS[0])
    assert auth.login('admin_123',PASS)

def test_no_email_required(accounts):
    assert auth.login('end_user_123',PASS)

def test_unknown_and_wrong_credentials_fail(accounts):
    assert auth.login('unknown',PASS) is None
    assert auth.login('admin_123','wrong') is None

def test_five_attempts_throttle(accounts):
    for _ in range(5):assert auth.login('end_user_123','wrong') is None
    assert auth.login('end_user_123',PASS) is None

def test_token_hash_only_and_logout(accounts):
    token=auth.login('admin_123',PASS)
    with storage.connect() as c:assert c.execute('SELECT token_hash FROM auth_sessions').fetchone()[0]!=token
    auth.logout(token);assert auth.principal(token) is None

def test_idle_expiry(accounts):
    token=auth.login('admin_123',PASS)
    with storage.connect() as c:c.execute('UPDATE auth_sessions SET last_seen=?',(time.time()-1801,))
    assert auth.principal(token) is None

def test_absolute_expiry(accounts):
    token=auth.login('admin_123',PASS)
    with storage.connect() as c:c.execute('UPDATE auth_sessions SET created=?',(time.time()-28801,))
    assert auth.principal(token) is None

def test_unauthenticated_backend_actions_denied(accounts):
    with pytest.raises(PermissionError):storage.set_setting('agent_disabled',True)
    with pytest.raises(PermissionError):storage.register_model('Model','Azure','Demo','Exploration',80,'Low')

def test_end_user_backend_actions_denied(accounts):
    auth.bind(auth.login('end_user_123',PASS))
    with pytest.raises(PermissionError):storage.set_setting('chargeback_threshold',10)
    with pytest.raises(PermissionError):auth.list_users()

def test_admin_actions_and_revocation(accounts):
    user_token=auth.login('end_user_123',PASS)
    auth.bind(auth.login('admin_123',PASS))
    storage.set_setting('chargeback_threshold',10)
    assert storage.get_setting('chargeback_threshold')==10
    user=next(u for u in auth.list_users() if u['role']=='end_user')
    auth.set_user_active(user['id'],False)
    assert auth.principal(user_token) is None and auth.login('end_user_123',PASS) is None

def test_profiles_not_in_agent_query_catalog():
    from src.query_tools import CATALOG
    assert not any('auth' in name or 'user'==name for name in CATALOG)

def test_login_gate_blocks_dashboard(accounts):
    from streamlit.testing.v1 import AppTest
    at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
    assert not at.exception and len(at.radio)==0
    assert any(t.label=='Username' for t in at.text_input)

def test_end_user_navigation_and_logout(accounts):
    from streamlit.testing.v1 import AppTest
    at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30)
    token=auth.login('end_user_123',PASS);at.session_state['auth_token']=token
    at.run();assert not at.exception
    assert 'Administration' not in at.sidebar.radio[0].options
    at.session_state['agent_messages']=[{'role':'user','content':'private previous chat'}]
    at.button(key='auth_logout').click().run()
    assert not at.exception and len(at.radio)==0
    assert auth.principal(token) is None

def test_admin_navigation(accounts):
    from streamlit.testing.v1 import AppTest
    at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30)
    at.session_state['auth_token']=auth.login('admin_123',PASS)
    at.run();assert not at.exception
    # Administration is now hidden from the visible navigation for everyone, including admins (2026-10-26 usability review);
    # it stays a reachable route/function and still enforces require_admin(). The admin can still use the dashboard.
    assert 'Administration' not in at.sidebar.radio[0].options
    at.sidebar.radio[0].set_value('Executive overview').run()
    assert not at.exception and not at.error
