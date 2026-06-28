"""
tests/conftest.py — Shared pytest fixtures for Assist Neo
==========================================================
Sets APP_ENV=testing before any import so config/ picks up TestingConfig
(in-memory/temp DBs, no real API calls required).
"""
import os, sys, pytest

# ── Force testing config before any app import ───────────────────────────────
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("FLASK_ENV", "testing")

# Ensure project root is on the path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ── App fixture ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def flask_app():
    """Create a test Flask app (session-scoped — built once for the whole run)."""
    from config.testing import TestingConfig
    import os
    os.makedirs(TestingConfig.UPLOAD_DIR,   exist_ok=True)
    os.makedirs(TestingConfig.DOCS_DIR,     exist_ok=True)
    os.makedirs(TestingConfig.WORKSPACE_DIR, exist_ok=True)

    # Patch DB path before importing db
    import db as _db_mod
    _db_mod.DB_PATH = TestingConfig.DB_PATH
    _db_mod.init_db()

    from app import app
    app.config.from_object(TestingConfig)
    app.config["TESTING"] = True
    yield app


@pytest.fixture(scope="session")
def client(flask_app):
    """Flask test client."""
    with flask_app.test_client() as c:
        yield c


@pytest.fixture(scope="session")
def auth_client(client):
    """Test client pre-logged-in as 'testuser'."""
    import db as _db
    from services.auth_service import hash_password
    # create a test user if not present
    if not _db.get_user("testuser"):
        _db.create_user("testuser", "Test User", hash_password("testpass1"), role="user")
    client.post("/login", json={"username": "testuser", "password": "testpass1"})
    yield client


@pytest.fixture(scope="session")
def admin_client(client):
    """Test client pre-logged-in as 'adminuser' (role=admin)."""
    import db as _db
    from services.auth_service import hash_password
    if not _db.get_user("adminuser"):
        _db.create_user("adminuser", "Admin", hash_password("adminpass1"), role="admin")
    client.post("/login", json={"username": "adminuser", "password": "adminpass1"})
    yield client
