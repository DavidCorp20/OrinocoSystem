import logging
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from config import settings
from database import client, db
from production_migrations import ensure_managed_accounts_approved
from routes_ai import router as ai_router
from routes_assistant import router as assistant_router
from routes_auth import router as auth_router
from routes_business import router as business_router
from routes_dashboard import router as dashboard_router
from routes_expenses import router as expenses_router
from routes_finance_export import router as finance_export_router
from routes_financial_engine import router as financial_engine_router
from routes_financial_insights import router as financial_insights_router
from routes_intelligence import router as intelligence_router
from routes_inventory import router as inventory_router
from routes_platform import router as platform_router
from routes_subscription import router as subscription_router
from routes_products import router as products_router
from routes_purchases import router as purchases_router
from routes_rates import router as rates_router
from routes_sales import router as sales_router
from routes_reports_analysis import router as reports_router
from routes_obligations import router as obligations_router
from routes_recipes import router as recipes_router
from routes_promotions import router as promotions_router
from routes_cash_closure import router as cash_closure_router
from routes_cubi import router as cubi_router
from routes_import_export import router as import_export_router
from seed import seed_all
from demo_seed import seed_demo_account
from demo_catalog_upgrade import upgrade_demo_catalog
from demo_product_images import seed_demo_product_images
from demo_showcase_seed import seed_showcase
from demo_showcase_patch import main as patch_demo_showcase
from plan_access import DEFAULT_ENTITLEMENTS

app = FastAPI(title="PLATIA API")
api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"message": "PLATIA API"}


@api_router.get("/healthz")
async def healthz():
    await db.command("ping")
    return {"status": "ok"}


for r in (
    auth_router, business_router, products_router, inventory_router, sales_router,
    purchases_router, expenses_router, finance_export_router, dashboard_router,
    financial_engine_router, financial_insights_router, intelligence_router,
    assistant_router, ai_router, rates_router, platform_router, subscription_router,
    reports_router, obligations_router, recipes_router, promotions_router,
    cash_closure_router, cubi_router, import_export_router,
):
    api_router.include_router(r)
app.include_router(api_router)


def normalize_origin(v: str) -> str:
    return v.strip().rstrip("/")


env_origins = [
    normalize_origin(o)
    for o in (settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS else [])
    if o.strip()
]
frontend_origins = {
    normalize_origin(settings.FRONTEND_URL) if settings.FRONTEND_URL else "",
    "https://platia.up.railway.app",
    "https://cuadrapp.up.railway.app",
}
allow_origins = [o for o in dict.fromkeys(env_origins + list(frontend_origins)) if o]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.on_event("startup")
async def startup_event():
    await ensure_managed_accounts_approved()
    await seed_all()
    await seed_demo_account()
    await upgrade_demo_catalog()
    await seed_demo_product_images()

    # Public PLATIA showcase bootstrap. It uses the exact same MongoDB
    # connection as the running API, so it cannot silently seed another DB.
    demo_enabled = os.getenv("DEMO_SEED_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    logging.info("[PLATIA] MongoDB startup: DB_NAME=%s DEMO_SEED_ENABLED=%s", settings.DB_NAME, demo_enabled)
    if demo_enabled:
        logging.info("[PLATIA] Demo showcase bootstrap starting in DB=%s", settings.DB_NAME)
        await db.command("ping")
        await seed_showcase()
        await patch_demo_showcase()

        demo_emails = [
            "cafe.demo@platia.app",
            "barber.demo@platia.app",
            "moda.demo@platia.app",
        ]
        found = await db.users.count_documents({"email": {"$in": demo_emails}})
        logging.info("[PLATIA] Demo users verified: %s/%s", found, len(demo_emails))
        if found != len(demo_emails):
            raise RuntimeError(
                f"PLATIA demo bootstrap incomplete: found {found}/{len(demo_emails)} demo users in DB '{settings.DB_NAME}'"
            )
        logging.info("[PLATIA] Demo showcase bootstrap completed successfully")


@app.on_event("shutdown")
async def shutdown_event():
    client.close()
