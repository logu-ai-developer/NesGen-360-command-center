# Login patch validation
115 tests passed across three complete non-overlapping batches:
- 21 auth tests: no default admin, setup requirement, salted password hashes, password length, end-user-only registration, duplicate protection, case-normalized login, throttling, hashed sessions, logout, idle/absolute expiry, unauthenticated/end-user action denial, admin writes, account revocation, auth tables absent from query catalog, real login gate, end-user navigation/logout and admin navigation.
- 40 existing page/persistence/core tests with explicit authenticated test sessions.
- 54 existing AI/query/audience tests with explicit authenticated test sessions.

Compilation passed. Existing page function ASTs match the audience-patch baseline except Administration, which adds permission enforcement and user management. The app-level login gate and role-aware navigation are new. Agent, query tools, model config and quota files are not replaced.

Tests use temporary SQLite databases and synthetic fixtures. Login tests do not use the legacy gate mock. Legacy AppTest tests use a test-only authenticated Admin fixture; no production authentication bypass exists. Password hashing uses its real 600,000-iteration work factor during tests.

No live API call or penetration test was made. Streamlit AppTest used 1.53.1, not pinned 1.66.0. Windows getpass/launcher, actual data, HTTPS/reverse proxy and enterprise identity remain untested. This is local POC validation, not a security certification.
