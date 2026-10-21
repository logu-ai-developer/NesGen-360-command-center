"""Idempotent operational schema. Safe when the entire data directory is replaced."""
import json,sqlite3,uuid
from src.data import DB

def connect():
    DB.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB,timeout=15)
    c.execute('PRAGMA busy_timeout=15000')
    return c

def init():
    with connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS local_models(id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS app_settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS source_status(domain TEXT PRIMARY KEY,mode TEXT,detail TEXT,rows INTEGER,updated_at TEXT DEFAULT CURRENT_TIMESTAMP)')
        c.execute('CREATE TABLE IF NOT EXISTS build_metadata(key TEXT PRIMARY KEY,value TEXT)')
        c.execute("INSERT OR IGNORE INTO build_metadata VALUES('version','V0.1-rebuild')")

def set_setting(key,value):
    from src.auth import require_admin
    require_admin()
    init()
    with connect() as c:c.execute('INSERT OR REPLACE INTO app_settings VALUES(?,?)',(key,json.dumps(value)))

def get_setting(key,default=None):
    init()
    with connect() as c:r=c.execute('SELECT value FROM app_settings WHERE key=?',(key,)).fetchone()
    return json.loads(r[0]) if r else default

def register_model(name,provider,owner,stage,score,risk):
    from src.auth import require_admin
    require_admin()
    if not name.strip() or not owner.strip():raise ValueError('Model name and accountable owner are required.')
    if provider not in ['Azure','AWS','GCP'] or risk not in ['Low','Medium','High'] or not 0<=int(score)<=100:raise ValueError('Invalid model fields.')
    init();ident='LOCAL-'+uuid.uuid4().hex[:10]
    payload={'id':ident,'name':name.strip(),'provider':provider,'owner':owner.strip(),'stage':stage,'evaluation_score':int(score),'risk':risk,'model_family':'Locally registered','lifecycle_status':'Current','migration_required':'No','next_review_date':None,'retire_date':None,'environment':'Sandbox'}
    with connect() as c:c.execute('INSERT INTO local_models VALUES(?,?)',(ident,json.dumps(payload)))
    return ident

def local_models():
    init()
    with connect() as c:return [json.loads(r[0]) for r in c.execute('SELECT payload FROM local_models')]

def source(domain,mode,detail,rows):
    init()
    with connect() as c:c.execute('INSERT OR REPLACE INTO source_status(domain,mode,detail,rows) VALUES(?,?,?,?)',(domain,mode,detail,int(rows)))

def sources():
    init()
    with connect() as c:
        c.row_factory=sqlite3.Row
        return [dict(r) for r in c.execute('SELECT * FROM source_status')]
