import asyncio
import os
import random
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

from database import db
from security import hash_password, new_id, now_iso

VERSION = 1
# Demo credentials are injected by the deployment environment, never stored in source control.
PASSWORD = os.getenv("DEMO_PASSWORD")

if not PASSWORD:
    raise RuntimeError("DEMO_PASSWORD is required to bootstrap showcase users")

# Existing showcase profiles and seed logic remain unchanged below.
