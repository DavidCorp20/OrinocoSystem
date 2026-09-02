from fastapi import HTTPException
from database import db

FEATURES = {
    "basic_operations": "Operación básica",
    "finance": "Finanzas",
    "obligations": "Cuentas por cobrar/pagar",
    "reports_advanced": "Reportes avanzados",
    "projections": "Proyecciones",
    "promotions": "Promociones",
    "recipes": "Recetas y costos",
    "abc_xyz": "Análisis ABC/XYZ",
    "advanced_analytics": "Analítica avanzada",
    "cash_closure": "Cierre de caja",
    "automations": "Automatizaciones",
    "exports": "Exportaciones",
    "cubi": "Cubi",
}

DEFAULT_ENTITLEMENTS = {
    "Básico": {"max_users": 1, "basic_operations": True, "finance": False, "obligations": False, "reports_advanced": False, "projections": False, "promotions": False, "recipes": False, "abc_xyz": False, "advanced_analytics": False, "cash_closure": True, "automations": "none", "exports": "basic", "cubi": "basic"},
    "Negocio": {"max_users": 3, "basic_operations": True, "finance": True, "obligations": True, "reports_advanced": True, "projections": True, "promotions": True, "recipes": False, "abc_xyz": True, "advanced_analytics": False, "cash_closure": True, "automations": "basic", "exports": "full", "cubi": "standard"},
    "Pro": {"max_users": 10, "basic_operations": True, "finance": True, "obligations": True, "reports_advanced": True, "projections": True, "promotions": True, "recipes": True, "abc_xyz": True, "advanced_analytics": True, "cash_closure": True, "automations": "advanced", "exports": "full", "cubi": "advanced"},
}

async def get_plan_for_business(business_id: str):
    sub = await db.platform_subscriptions.find_one({"business_id": business_id, "status": {"$ne": "cancelado"}}, {"_id": 0}, sort=[("created_at", -1)])
    if not sub:
        return None, DEFAULT_ENTITLEMENTS["Básico"]
    plan = await db.platform_plans.find_one({"id": sub.get("plan_id")}, {"_id": 0})
    if not plan:
        return sub, DEFAULT_ENTITLEMENTS["Básico"]
    entitlements = plan.get("entitlements") or DEFAULT_ENTITLEMENTS.get(plan.get("name"), DEFAULT_ENTITLEMENTS["Básico"])
    return sub, entitlements

async def get_entitlements(business_id: str):
    _, entitlements = await get_plan_for_business(business_id)
    return entitlements

async def require_feature(business_id: str, feature: str):
    entitlements = await get_entitlements(business_id)
    value = entitlements.get(feature, False)
    if value is False or value == "none":
        label = FEATURES.get(feature, feature)
        raise HTTPException(status_code=402, detail=f"La función {label} no está incluida en tu plan. Puedes actualizar tu plan desde Mi plan.")
    return entitlements

async def require_user_capacity(business_id: str):
    entitlements = await get_entitlements(business_id)
    max_users = int(entitlements.get("max_users", 1))
    current = await db.users.count_documents({"business_id": business_id})
    if current >= max_users:
        raise HTTPException(status_code=402, detail=f"Tu plan permite hasta {max_users} usuario{'s' if max_users != 1 else ''}. Actualiza tu plan para agregar más usuarios.")
    return entitlements
