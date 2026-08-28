"""Auth module: login, register, cookies, brute-force lockout, protected routes."""
import requests

from conftest import API, new_email


class TestAuth:
    def test_root(self, api_client):
        r = api_client.get(f"{API}/")
        assert r.status_code == 200
        assert "ControlPyme" in r.json().get("message", "")

    def test_login_success_sets_httponly_cookies(self, api_client, test_credentials):
        r = api_client.post(f"{API}/auth/login", json=test_credentials)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data["user"]["email"] == test_credentials["email"].lower()
        assert isinstance(data["access_token"], str) and len(data["access_token"]) > 20
        assert data["refresh_token"]
        assert data["business"] and data["business"]["name"]
        # httpOnly cookies
        raw = r.headers.get("set-cookie", "") + ";".join(
            v for k, v in r.raw.headers.items() if k.lower() == "set-cookie"
        )
        assert "access_token" in raw and "HttpOnly" in raw, raw[:300]
        assert "refresh_token" in raw

    def test_me_with_cookies(self, api_client, test_credentials):
        api_client.post(f"{API}/auth/login", json=test_credentials)
        r = api_client.get(f"{API}/auth/me")
        assert r.status_code == 200
        assert r.json()["user"]["email"] == test_credentials["email"].lower()
        assert r.json()["business"]["currency"] == "USD"

    def test_me_with_bearer(self, test_credentials):
        s = requests.Session()
        tok = s.post(f"{API}/auth/login", json=test_credentials).json()["access_token"]
        r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200

    def test_login_wrong_password_spanish_error(self, test_credentials):
        r = requests.post(f"{API}/auth/login", json={"email": test_credentials["email"], "password": "WrongPass123!"})
        assert r.status_code == 401
        assert "incorrect" in r.json()["detail"].lower() or "contraseña" in r.json()["detail"].lower()

    def test_protected_without_auth_401(self):
        for path in ("/dashboard", "/products", "/sales", "/finances/summary"):
            r = requests.get(f"{API}{path}")
            assert r.status_code == 401, f"{path} -> {r.status_code}"

    def test_register_duplicate_email(self, test_credentials):
        r = requests.post(f"{API}/auth/register", json={
            "name": "Dup", "email": test_credentials["email"], "password": "TestPyme2026!"})
        assert r.status_code == 400
        assert "Ya existe" in r.json()["detail"]

    def test_register_weak_password_422(self):
        r = requests.post(f"{API}/auth/register", json={"name": "Ab", "email": new_email("weak"), "password": "123"})
        assert r.status_code == 422

    def test_logout_clears_cookies(self, test_credentials):
        s = requests.Session()
        s.post(f"{API}/auth/login", json=test_credentials)
        assert s.get(f"{API}/auth/me").status_code == 200
        r = s.post(f"{API}/auth/logout")
        assert r.status_code == 200 and r.json()["ok"] is True
        assert s.get(f"{API}/auth/me").status_code == 401

    def test_refresh_token_flow(self, test_credentials):
        s = requests.Session()
        s.post(f"{API}/auth/login", json=test_credentials)
        r = s.post(f"{API}/auth/refresh")
        assert r.status_code == 200
        assert r.json().get("access_token")

    def test_refresh_without_cookie_401(self):
        assert requests.post(f"{API}/auth/refresh").status_code == 401


class TestBruteForce:
    """5 failed logins for a throwaway email -> 6th returns 429."""

    def test_lockout_after_five_failures(self):
        email = new_email("bf")
        requests.post(f"{API}/auth/register", json={"name": "BF User", "email": email, "password": "TestPyme2026!"})
        codes = []
        for _ in range(5):
            codes.append(requests.post(f"{API}/auth/login", json={"email": email, "password": "badpass"}).status_code)
        assert codes == [401] * 5, codes
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": "badpass"})
        assert r.status_code == 429, f"expected 429, got {r.status_code}: {r.text[:200]}"
        # correct password is also blocked while locked
        r2 = requests.post(f"{API}/auth/login", json={"email": email, "password": "TestPyme2026!"})
        assert r2.status_code == 429
