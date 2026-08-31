import logging

from fastapi import APIRouter, FastAPI
from starlette.middleware.cors import CORSMiddleware

from config import settings
from database import client, db
from routes_ai import router as ai_router
from routes_assistant import router as assistant_router
from routes_auth import router as auth_router
from routes_business import router as business_router
from routes_dashboard import router as dashboard_router
from routes_expenses import router as expenses_router
from routes_inventory import router as inventory_router
from routes_platform import router as platform_router
from routes_products import router as products_router
from routes_purchases import router as purchases_router
from routes_rates import router as rates_router
from routes_sales import router as sales_router
from seed import seed_all

app = FastAPI(title="ControlPyme API")

api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"message": "ControlPyme API"}


for r in (auth_router, business_router, products_router, inventory_router, sales_router, purchases_router, expenses_router, dashboard_router, assistant_router, ai_router, rates_router, platform_router):
    api_router.include_router(r)

app.include_router(api_router)

# CORS: normalize configured origins and always include the production frontend.
# FRONTEND_URL must contain the origin only (no path such as /auth).
def normalize_origin(value: str) -> str:
    return value.strip().rstrip("/")

env_origins = [
    normalize_origin(origin)
    for origin in (settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS else [])
    if origin.strip()
]

frontend_origins = {
    normalize_origin(settings.FRONTEND_URL) if settings.FRONTEND_URL else "",
    "https://cuadrapp.up.railway.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    *env_origins,
}
frontend_origins = [origin for origin in frontend_origins if origin]
frontend_origins = list(dict.fromkeys(frontend_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.products.create_index([("business_id", 1), ("name", 1)])
    await db.sales.create_index([("business_id", 1), ("created_at", -1)])
    await db.purchases.create_index([("business_id", 1), ("created_at", -1)])
    await db.expenses.create_index([("business_id", 1), ("created_at", -1)])
    await db.inventory_movements.create_index([("business_id", 1), ("created_at", -1)])
    await db.assistant_messages.create_index([("business_id", 1), ("created_at", 1)])
    await seed_all()
    logger.info("ControlPyme API lista")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
