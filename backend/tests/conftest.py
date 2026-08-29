import os
import uuid
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
DOTENV_PATHS = [BACKEND_DIR / ".env", ROOT_DIR / ".env"]
for env_path in DOTENV_PATHS:
    if env_path.exists():
        for key, value in dotenv_values(env_path).items():
            if key and value is not None and key not in os.environ:
                os.environ[key] = value

frontend_env = {}
frontend_dotenv = ROOT_DIR / "frontend" / ".env"
if frontend_dotenv.exists():
    frontend_env = dotenv_values(frontend_dotenv)

_base = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL") or "http://localhost:8001"
BASE_URL = _base.rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="session")
def test_credentials():
    email = os.environ.get("TEST_ADMIN_EMAIL") or os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("TEST_ADMIN_PASSWORD") or os.environ.get("ADMIN_PASSWORD")
    if not email or not password:
        pytest.skip("No hay credenciales de prueba en variables de entorno TEST_ADMIN_EMAIL / TEST_ADMIN_PASSWORD")
    return {"email": email, "password": password}


@pytest.fixture(scope="class")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="class")
def admin(request):
    """Authenticated session for the seeded demo admin (cookies + Bearer)."""
    creds = request.getfixturevalue("test_credentials")
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json=creds)
    if r.status_code != 200:
        pytest.fail(f"Admin login failed {r.status_code}: {r.text[:400]}")
    token = r.json().get("access_token")
    if not token:
        pytest.fail("login response missing access_token")
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


def new_email(tag="qa"):
    return f"test_pyme_{tag}_{uuid.uuid4().hex[:8]}@mail.com"
