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
from seed import seed_all
from demo_seed import seed_demo_account
from demo_catalog_upgrade import upgrade_demo_catalog
from demo_product_images import seed_demo_product_images
app=FastAPI(title="CuadraApp API");api_router=APIRouter(prefix="/api")
@api_router.get("/")
async def root():return {"message":"CuadraApp API"}
@api_router.get("/healthz")
async def healthz():await db.command("ping");return {"status":"ok"}
for r in (auth_router,business_router,products_router,inventory_router,sales_router,purchases_router,expenses_router,dashboard_router,assistant_router,ai_router,rates_router,platform_router,subscription_router,reports_router,obligations_router,recipes_router,promotions_router,cash_closure_router,cubi_router):api_router.include_router(r)
app.include_router(api_router)
def normalize_origin(v:str)->str:return v.strip().rstrip("/")
env_origins=[normalize_origin(o) for o in (settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS else []) if o.strip()];frontend_origins={normalize_origin(settings.FRONTEND_URL) if settings.FRONTEND_URL else "","https://cuadrapp.up.railway.app","http://localhost:3000","http://127.0.0.1:3000","http://localhost:3001","http://127.0.0.1:3001",*env_origins};frontend_origins=list(dict.fromkeys(o for o in frontend_origins if o))
if settings.APP_ENV=="production":
    if not settings.COOKIE_SECURE:raise RuntimeError("COOKIE_SECURE debe estar habilitado en production")
    if settings.COOKIE_SAMESITE not in {"lax","strict","none"}:raise RuntimeError("COOKIE_SAMESITE inválido; usa lax, strict o none")
    if not settings.FRONTEND_URL or settings.FRONTEND_URL.startswith("http://localhost"):raise RuntimeError("FRONTEND_URL debe apuntar al frontend real en production")
    if "*" in frontend_origins:raise RuntimeError("CORS no puede usar '*' en production")
app.add_middleware(CORSMiddleware,allow_origins=frontend_origins,allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self,request:Request,call_next):
        response=await call_next(request);response.headers.setdefault("X-Content-Type-Options","nosniff");response.headers.setdefault("X-Frame-Options","DENY");response.headers.setdefault("Referrer-Policy","strict-origin-when-cross-origin");response.headers.setdefault("Permissions-Policy","camera=(), microphone=(), geolocation=()")
        if settings.APP_ENV=="production":response.headers.setdefault("Strict-Transport-Security","max-age=31536000; includeSubDomains")
        return response
app.add_middleware(SecurityHeadersMiddleware);logging.basicConfig(level=logging.INFO,format="%(asctime)s - %(name)s - %(levelname)s - %(message)s");logger=logging.getLogger(__name__)
@app.on_event("startup")
async def startup():
    await db.users.create_index("email",unique=True);await db.login_attempts.create_index("identifier");await db.products.create_index([("business_id",1),("name",1)]);await db.products.create_index([("business_id",1),("barcode",1)]);await db.sales.create_index([("business_id",1),("created_at",-1)]);await db.purchases.create_index([("business_id",1),("created_at",-1)]);await db.expenses.create_index([("business_id",1),("created_at",-1)]);await db.expenses.create_index([("business_id",1),("date",1)]);await db.inventory_movements.create_index([("business_id",1),("created_at",-1)]);await db.assistant_messages.create_index([("business_id",1),("created_at",1)]);await db.obligations.create_index([("business_id",1),("status",1),("due_date",1)]);await db.obligation_payments.create_index([("business_id",1),("obligation_id",1),("paid_at",-1)]);await db.platform_subscriptions.create_index([("business_id",1),("status",1)]);await db.platform_subscriptions.create_index([("status",1),("due_date",1)]);await db.platform_billing.create_index([("business_id",1),("paid_at",-1)]);await db.platform_billing.create_index([("subscription_id",1),("paid_at",-1)]);await db.platform_billing.create_index([("status",1),("paid_at",-1)]);await db.platform_expenses.create_index([("date",1)]);await db.promotions.create_index([("business_id",1),("created_at",-1)]);await db.cash_closures.create_index([("business_id",1),("date",-1),("closed_at",-1)]);await ensure_managed_accounts_approved()
    defaults=[{"name":"Básico","description":"Para negocios que comienzan a digitalizar su operación.","monthly_price_usd":4.98,"active":True,"features":["Inventario","Ventas","Compras","Dashboard"]},{"name":"Negocio","description":"Para negocios que necesitan más control y análisis de su operación.","monthly_price_usd":8.98,"active":True,"features":["Todo Básico","Finanzas","Reportes","Equipo"]},{"name":"Pro","description":"Para negocios que quieren aprovechar todas las capacidades de CuadraApp.","monthly_price_usd":14.98,"active":True,"features":["Todo Negocio","IA","Reportes avanzados","Proyección","Funciones premium"]}]
    for p in defaults:await db.platform_plans.update_one({"name":p["name"]},{"$set":{**p,"updated_at":datetime.now(timezone.utc).isoformat()},"$setOnInsert":{"id":__import__("uuid").uuid4().hex,"created_at":datetime.now(timezone.utc).isoformat()}},upsert=True)
    await db.platform_plans.update_many({"name":"Premium"},{"$set":{"active":False,"updated_at":datetime.now(timezone.utc).isoformat()}})
    if settings.APP_ENV!="production":await seed_all()
    await seed_demo_account();await upgrade_demo_catalog();await seed_demo_product_images();logger.info("CuadraApp API lista")
@app.on_event("shutdown")
async def shutdown_db_client():client.close()
