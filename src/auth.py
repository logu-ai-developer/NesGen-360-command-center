"""Local-demo authentication. No shipped credentials or public admin creation."""
import contextvars,hashlib,hmac,re,secrets,sqlite3,time
from src import storage
GROUPS=['NesGen Platform Team','Regional Product Owners & Managers','Business Stakeholders']
ITERATIONS=600000
IDLE_SECONDS=1800
ABSOLUTE_SECONDS=28800
_TOKEN=contextvars.ContextVar('nesgen_auth_token',default=None)

def init():
    storage.init()
    with storage.connect() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS auth_users(
          id TEXT PRIMARY KEY,user_name TEXT UNIQUE NOT NULL,display_name TEXT NOT NULL,email TEXT,
          stakeholder_group TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('admin','end_user')),
          password_hash TEXT NOT NULL,is_active INTEGER NOT NULL DEFAULT 1,created REAL NOT NULL)''')
        c.execute('CREATE TABLE IF NOT EXISTS auth_sessions(token_hash TEXT PRIMARY KEY,user_id TEXT,created REAL,last_seen REAL)')
        c.execute('CREATE TABLE IF NOT EXISTS auth_attempts(bucket TEXT PRIMARY KEY,count INTEGER,window_start REAL,blocked_until REAL)')

def _username(value):
    value=str(value).strip().lower()
    if not re.fullmatch(r'[a-z0-9_][a-z0-9_.-]{2,39}',value):raise ValueError('Username must be 3-40 letters, digits, dots, underscores or hyphens.')
    return value

def hash_password(password):
    if not isinstance(password,str) or not 15<=len(password)<=128:raise ValueError('Use a password of 15-128 characters.')
    salt=secrets.token_bytes(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,ITERATIONS)
    return f'pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}'

def verify_password(password,encoded):
    try:
        algorithm,iterations,salt,digest=encoded.split('$')
        if algorithm!='pbkdf2_sha256' or not 600000<=int(iterations)<=2000000:return False
        value=hashlib.pbkdf2_hmac('sha256',str(password).encode(),bytes.fromhex(salt),int(iterations))
        return hmac.compare_digest(value.hex(),digest)
    except (ValueError,TypeError):return False

# Equal-cost check for nonexistent usernames, not a usable account password.
_DUMMY=hash_password(secrets.token_urlsafe(32))

def _bucket(name):return hashlib.sha256(name.encode()).hexdigest()

def _allow(c,bucket,limit,window,block):
    now=time.time();row=c.execute('SELECT count,window_start,blocked_until FROM auth_attempts WHERE bucket=?',(bucket,)).fetchone()
    if row and row[2]>now:return False
    count=0 if not row or now-row[1]>=window else row[0]
    start=now if not row or now-row[1]>=window else row[1]
    if count>=limit:
        c.execute('INSERT OR REPLACE INTO auth_attempts VALUES(?,?,?,?)',(bucket,count,start,now+block));return False
    c.execute('INSERT OR REPLACE INTO auth_attempts VALUES(?,?,?,?)',(bucket,count+1,start,0));return True

def register_end_user(user_name,password,display_name,stakeholder_group,email=''):
    init();name=_username(user_name)
    if not display_name.strip() or len(display_name)>100:raise ValueError('Display name is required (maximum 100 characters).')
    if stakeholder_group not in GROUPS:raise ValueError('Select an approved stakeholder group.')
    email=email.strip()
    if email and (len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email)):raise ValueError('Enter a valid email or leave it blank.')
    encoded=hash_password(password)
    with storage.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        if not c.execute("SELECT 1 FROM auth_users WHERE role='admin' AND is_active=1").fetchone():raise ValueError('Local administrator setup is required before registration.')
        if not _allow(c,'registration-global',20,3600,3600):
            c.commit();raise ValueError('Registration temporarily unavailable. Try later.')
        try:c.execute('INSERT INTO auth_users VALUES(?,?,?,?,?,?,?,?,?)',(secrets.token_hex(16),name,display_name.strip(),email,stakeholder_group,'end_user',encoded,1,time.time()))
        except sqlite3.IntegrityError:raise ValueError('Account could not be created. Choose another username or sign in.')
    return name

def bootstrap_admin(user_name,password,display_name='Demo administrator'):
    """Local terminal only; never exposed as a UI action. Refuses a second admin."""
    init();name=_username(user_name);encoded=hash_password(password)
    with storage.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute("SELECT 1 FROM auth_users WHERE role='admin'").fetchone():raise ValueError('An administrator already exists. No changes made.')
        try:c.execute('INSERT INTO auth_users VALUES(?,?,?,?,?,?,?,?,?)',(secrets.token_hex(16),name,display_name,'',GROUPS[0],'admin',encoded,1,time.time()))
        except sqlite3.IntegrityError:raise ValueError('Username already exists. No changes made.')

def has_admin():
    init()
    with storage.connect() as c:return bool(c.execute("SELECT 1 FROM auth_users WHERE role='admin' AND is_active=1").fetchone())

def login(user_name,password):
    init()
    # Invalid usernames get the same failed response and dummy hash work.
    name=str(user_name).strip().lower()[:128]
    with storage.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        allowed=_allow(c,'login-global',100,300,300)
        allowed=_allow(c,'login-'+_bucket(name),5,300,300) and allowed
        c.commit()
        if not allowed:return None
        c.row_factory=sqlite3.Row
        row=c.execute('SELECT * FROM auth_users WHERE user_name=?',(name,)).fetchone()
        encoded=row['password_hash'] if row else _DUMMY
        valid=verify_password(password,encoded)
        if not valid or not row or not row['is_active']:return None
        c.execute('DELETE FROM auth_attempts WHERE bucket=?',('login-'+_bucket(name),))
        token=secrets.token_urlsafe(32);now=time.time()
        c.execute('DELETE FROM auth_sessions WHERE last_seen<? OR created<?',(now-IDLE_SECONDS,now-ABSOLUTE_SECONDS))
        c.execute('INSERT INTO auth_sessions VALUES(?,?,?,?)',(_bucket(token),row['id'],now,now))
        return token

def principal(token=None,touch=True):
    token=token or _TOKEN.get()
    if not token:return None
    init();now=time.time()
    with storage.connect() as c:
        c.row_factory=sqlite3.Row
        row=c.execute('''SELECT u.id,u.user_name,u.display_name,u.role,u.is_active,s.created,s.last_seen
             FROM auth_sessions s JOIN auth_users u ON u.id=s.user_id WHERE s.token_hash=?''',(_bucket(token),)).fetchone()
        if not row:return None
        if not row['is_active'] or now-row['last_seen']>=IDLE_SECONDS or now-row['created']>=ABSOLUTE_SECONDS:
            c.execute('DELETE FROM auth_sessions WHERE token_hash=?',(_bucket(token),));return None
        if touch:c.execute('UPDATE auth_sessions SET last_seen=? WHERE token_hash=?',(now,_bucket(token)))
        return {k:row[k] for k in ['id','user_name','display_name','role']}

def bind(token):_TOKEN.set(token)

def require_admin():
    user=principal()
    if not user or user['role']!='admin':raise PermissionError('Administrator permission required.')
    return user

def logout(token):
    init()
    with storage.connect() as c:c.execute('DELETE FROM auth_sessions WHERE token_hash=?',(_bucket(token),))
    bind(None)

def list_users():
    require_admin()
    with storage.connect() as c:
        c.row_factory=sqlite3.Row
        return [dict(r) for r in c.execute('SELECT id,user_name,display_name,stakeholder_group,role,is_active FROM auth_users ORDER BY user_name')]

def set_user_active(user_id,active):
    actor=require_admin()
    if user_id==actor['id']:raise ValueError('You cannot deactivate your own account.')
    with storage.connect() as c:
        row=c.execute('SELECT role FROM auth_users WHERE id=?',(user_id,)).fetchone()
        if not row or row[0]!='end_user':raise ValueError('Only end-user activation can be changed here.')
        c.execute('UPDATE auth_users SET is_active=? WHERE id=?',(int(bool(active)),user_id))
        c.execute('DELETE FROM auth_sessions WHERE user_id=?',(user_id,))
