import logging
from datetime import datetime, timezone
from fastapi import APIRouter, FastAPI, Request
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
from plan_access import DEFAULT_ENTITLEMENTS
app=FastAPI(title="CuadraApp API");api_router=APIRouter(prefix="/api")
@api_router.get("/")
async def root():return {"message":"CuadraApp API"}
@api_router.get("/healthz")
async def healthz():await db.command("ping");return {"status":"ok"}
for r in (auth_router,business_router,products_router,inventory_router,sales_router,purchases_router,expenses_router,finance_export_router,dashboard_router,assistant_router,ai_router,rates_router,platform_router,subscription_router,reports_router,obligations_router,recipes_router,promotions_router,cash_closure_router,cubi_router,import_export_router):api_router.include_router(r)
app.include_router(api_router)
def normalize_origin(v:str)->str:return v.strip().rstrip("/")
env_origins=[normalize_origin(o) for o in (settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS else []) if o.strip()];frontend_origins={normalize_origin(settings.FRONTEND_URL) if settings.FRONTEND_URL else "","https://cuadrapp.up.railway.app","http://localhost:3000","http://127.0.0.1:3000","http://localhost:3001","http://127.0.0.1:3001",*env_origins};frontend_origins=list(dict.fromkeys(o for o in frontend_origins if o))
if settings.APP_ENV=="production":
    if not settings.COOKIE_SECURE:raise RuntimeError("COOKIE_SECURE debe estar habilitado en production")
    if settings.COOKIE_SAMESITE not in {"lax","strict","none"}:raise RuntimeError("COOKIE_SAMESITE inválido; usa lax, strict o none")
    if not settings.FRONTEND_URL or settings.FRONTEND_URL.startswith("http://localhost"):raise RuntimeError("FRONTEND_URL debe apuntar al frontend real en production")
    if "*" in frontend_origins:raise RuntimeError("CORS no puede usar '*' en production")
app.add_middleware(CORSMiddleware,allow_origins=frontend_origins,allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
PLAN_PATHS={"/finance":"finance","/finances":"finance","/finanzas":"finance","/obligations":"obligations","/reports":"reports_advanced","/projections":"projections","/projection":"projections","/promotions":"promotions","/recipes":"recipes","/cash-closure":"cash_closure","/cash-closures":"cash_closure","/exports":"exports","/templates":"exports","/ai/margin-analysis":"advanced_analytics"}
class PlanAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self,request:Request,call_next):
        if request.method=="OPTIONS":return await call_next(request)
        path=request.url.path
        if path.startswith("/api/assistant/chat"):
            from security import get_current_user
            from plan_access import require_cubi_chat
            try:
                user=await get_current_user(request)
                if user.get("platform_role")!="superadmin" and user.get("business_id"): await require_cubi_chat(user["business_id"])
            except Exception as exc:
                from fastapi import HTTPException
                if isinstance(exc,HTTPException):
                    from fastapi.responses import JSONResponse
                    return JSONResponse(status_code=exc.status_code,content={"detail":exc.detail})
                raise
        feature=next((f for suffix,f in PLAN_PATHS.items() if path.startswith("/api"+suffix)),None)
        if feature:
            from security import get_current_user
            from plan_access import require_feature
            try:
                user=await get_current_user(request)
                if user.get("platform_role")!="superadmin" and user.get("business_id"):await require_feature(user["business_id"],feature)
            except Exception as exc:
                from fastapi import HTTPException
                if isinstance(exc,HTTPException):
                    from fastapi.responses import JSONResponse
                    return JSONResponse(status_code=exc.status_code,content={"detail":exc.detail})
                raise
        return await call_next(request)
app.add_middleware(PlanAccessMiddleware)