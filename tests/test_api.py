"""
tests/test_api.py — Integration tests for Flask routes
Uses the test client from conftest.py (session-scoped, in-memory DB).
"""
import pytest


# ── Auth routes ───────────────────────────────────────────────────────────────

class TestAuthRoutes:
    def test_login_page_loads(self, client):
        r = client.get("/login")
        assert r.status_code == 200

    def test_register_page_loads(self, client):
        r = client.get("/register")
        assert r.status_code == 200

    def test_register_new_user(self, client):
        r = client.post("/register", json={
            "username": "newuser_api_test",
            "password": "securepass1",
            "nickname": "New User",
        })
        assert r.status_code in (200, 302)
        if r.is_json:
            assert r.get_json().get("ok")

    def test_register_duplicate_user(self, client):
        client.post("/register", json={
            "username": "dupuser",
            "password": "securepass1",
            "nickname": "Dup",
        })
        r = client.post("/register", json={
            "username": "dupuser",
            "password": "securepass1",
            "nickname": "Dup",
        })
        assert r.status_code in (400, 200)
        if r.is_json:
            assert "error" in r.get_json()

    def test_login_wrong_password(self, client):
        r = client.post("/login", json={
            "username": "testuser",
            "password": "wrongpassword!",
        })
        assert r.status_code == 401

    def test_login_success(self, client):
        import db as _db
        from services.auth_service import hash_password
        if not _db.get_user("testuser"):
            _db.create_user("testuser", "Test User", hash_password("testpass1"))
        r = client.post("/login", json={
            "username": "testuser",
            "password": "testpass1",
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data.get("ok") is True

    def test_logout(self, client):
        r = client.get("/logout")
        assert r.status_code in (200, 302)


# ── Auth-gated routes return 401 when not logged in ──────────────────────────

class TestAuthGating:
    GATED_ROUTES = [
        ("GET",  "/"),
        ("POST", "/ask"),
        ("GET",  "/chats"),
        ("GET",  "/memory"),
        ("GET",  "/tools"),
        ("POST", "/tools/run"),
        ("GET",  "/files/list"),
    ]

    @pytest.mark.parametrize("method,path", GATED_ROUTES)
    def test_requires_login(self, client, method, path):
        # Fresh client with no session
        from flask import Flask
        import app as _app
        with _app.app.test_client() as fresh:
            if method == "GET":
                r = fresh.get(path)
            else:
                r = fresh.post(path, json={})
            assert r.status_code in (401, 302), (
                f"{method} {path} returned {r.status_code}, expected 401 or 302"
            )


# ── Tools API ─────────────────────────────────────────────────────────────────

class TestToolsAPI:
    def test_tools_list(self, auth_client):
        r = auth_client.get("/tools")
        assert r.status_code == 200
        data = r.get_json()
        assert "tools" in data
        assert isinstance(data["tools"], list)

    def test_tools_run_calculator(self, auth_client):
        r = auth_client.post("/tools/run", json={
            "tool": "calculator",
            "args": {"expression": "10 * 5"},
        })
        assert r.status_code == 200
        data = r.get_json()
        assert "error" not in data or data.get("error") is None

    def test_tools_run_missing_name(self, auth_client):
        r = auth_client.post("/tools/run", json={"args": {}})
        assert r.status_code == 400

    def test_tools_run_unknown(self, auth_client):
        r = auth_client.post("/tools/run", json={
            "tool": "__nonexistent__",
            "args": {},
        })
        assert r.status_code == 200
        data = r.get_json()
        assert "error" in data


# ── Chat API ──────────────────────────────────────────────────────────────────

class TestChatAPI:
    def test_list_chats(self, auth_client):
        r = auth_client.get("/chats")
        assert r.status_code == 200
        data = r.get_json()
        assert "chats" in data

    def test_memory_endpoint(self, auth_client):
        r = auth_client.get("/memory")
        assert r.status_code == 200

    def test_greet(self, auth_client):
        r = auth_client.get("/greet")
        assert r.status_code == 200


# ── Settings ──────────────────────────────────────────────────────────────────

class TestSettings:
    def test_get_settings(self, auth_client):
        r = auth_client.get("/settings/personality")
        assert r.status_code == 200

    def test_save_settings(self, auth_client):
        r = auth_client.post("/settings/personality", json={
            "persona_name": "TestBot",
            "custom_instructions": "Be concise.",
            "model_routing": True,
            "self_reflect": False,
        })
        assert r.status_code == 200
        assert r.get_json().get("ok")


# ── Admin API ─────────────────────────────────────────────────────────────────

class TestAdminAPI:
    def test_admin_requires_admin_role(self, auth_client):
        """Regular user should get 403 from admin routes."""
        r = auth_client.get("/admin/users")
        assert r.status_code == 403

    def test_admin_list_users(self, admin_client):
        r = admin_client.get("/admin/users")
        assert r.status_code == 200
        data = r.get_json()
        assert "users" in data
        assert isinstance(data["users"], list)

    def test_admin_metrics(self, admin_client):
        r = admin_client.get("/admin/metrics")
        assert r.status_code == 200
        assert "metrics" in r.get_json()

    def test_admin_set_invalid_role(self, admin_client):
        r = admin_client.post("/admin/users/testuser/role",
                              json={"role": "superuser"})
        assert r.status_code == 400


# ── Error handler ─────────────────────────────────────────────────────────────

class TestErrorHandlers:
    def test_404_returns_json(self, client):
        r = client.get("/route_that_does_not_exist_xyz")
        # might redirect to login (302) or return 404
        assert r.status_code in (302, 401, 404)
        if r.status_code == 404 and r.is_json:
            data = r.get_json()
            assert "error" in data

    def test_method_not_allowed(self, auth_client):
        r = auth_client.delete("/tools")   # DELETE not allowed on /tools
        assert r.status_code == 405
        if r.is_json:
            assert "error" in r.get_json()
