import os
import re
import uuid
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
_base = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not _base:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = _base.rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="session")
def test_credentials():
    p = Path("/app/memory/test_credentials.md")
    if not p.exists():
        pytest.skip("Missing /app/memory/test_credentials.md")
    content = p.read_text(encoding="utf-8")
    email = re.search(r'(?im)^\s*(?:[-*]\s*)?(?:\*\*)?email(?:\*\*)?\s*:\s*`?([^`\s]+)', content)
    pwd = re.search(r'(?im)^\s*(?:[-*]\s*)?(?:\*\*)?password(?:\*\*)?\s*:\s*`?([^`\s]+)', content)
    if not email or not pwd:
        pytest.skip("No credentials found in test_credentials.md")
    return {"email": email.group(1), "password": pwd.group(1)}


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
