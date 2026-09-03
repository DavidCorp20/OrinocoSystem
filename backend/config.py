import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent

for env_path in (
    BACKEND_DIR / ".env",
    PROJECT_ROOT / ".env",
):
    if env_path.exists():
        load_dotenv(env_path, override=False)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
    MONGO_URL = os.getenv("MONGO_URL", "mongodb://127.0.0.1:27017")
    DB_NAME = os.getenv("DB_NAME", "controlpyme")
    JWT_SECRET = os.getenv("JWT_SECRET")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3001")
    REACT_APP_BACKEND_URL = os.getenv("REACT_APP_BACKEND_URL", "http://localhost:8001")
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "")
    COOKIE_SECURE = _env_bool("COOKIE_SECURE", APP_ENV == "production")
    COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax").strip().lower()
    COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN", "").strip()
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
    TEST_ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL")
    TEST_ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD")
    ALLOW_DEV_RESET = _env_bool("ALLOW_DEV_RESET", False)

    @classmethod
    def ensure_required(cls):
        missing = []
        for name, value in {
            "JWT_SECRET": cls.JWT_SECRET,
            "MONGO_URL": cls.MONGO_URL,
            "DB_NAME": cls.DB_NAME,
        }.items():
            if not value:
                missing.append(name)
        if missing:
            raise RuntimeError(
                "Faltan variables de entorno críticas: " + ", ".join(missing)
                + ". Revisa backend/.env o la configuración local."
            )

        if cls.APP_ENV == "production":
            if len(cls.JWT_SECRET or "") < 32:
                raise RuntimeError("JWT_SECRET debe tener al menos 32 caracteres en production")
            if cls.MONGO_URL.startswith("mongodb://127.0.0.1") or cls.MONGO_URL.startswith("mongodb://localhost"):
                raise RuntimeError("MONGO_URL no puede apuntar a localhost en production")
            if cls.ALLOW_DEV_RESET:
                raise RuntimeError("ALLOW_DEV_RESET debe estar deshabilitado en production")


settings = Settings()
settings.ensure_required()

for key, value in {
    "APP_ENV": settings.APP_ENV,
    "MONGO_URL": settings.MONGO_URL,
    "DB_NAME": settings.DB_NAME,
    "JWT_SECRET": settings.JWT_SECRET,
    "FRONTEND_URL": settings.FRONTEND_URL,
    "REACT_APP_BACKEND_URL": settings.REACT_APP_BACKEND_URL,
    "CORS_ORIGINS": settings.CORS_ORIGINS,
    "COOKIE_SECURE": str(settings.COOKIE_SECURE).lower(),
    "COOKIE_SAMESITE": settings.COOKIE_SAMESITE,
    "COOKIE_DOMAIN": settings.COOKIE_DOMAIN,
    "OPENAI_API_KEY": settings.OPENAI_API_KEY,
    "OPENAI_MODEL": settings.OPENAI_MODEL,
    "ADMIN_EMAIL": settings.ADMIN_EMAIL,
    "ADMIN_PASSWORD": settings.ADMIN_PASSWORD,
    "TEST_ADMIN_EMAIL": settings.TEST_ADMIN_EMAIL,
    "TEST_ADMIN_PASSWORD": settings.TEST_ADMIN_PASSWORD,
    "ALLOW_DEV_RESET": str(settings.ALLOW_DEV_RESET).lower(),
}.items():
    if value is not None:
        os.environ.setdefault(key, value)
