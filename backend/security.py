import uuid
from datetime import datetime, timezone, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, Response

from database import db
from config import settings

JWT_ALGORITHM = "HS256"
ACCESS_MINUTES = 15
REFRESH_DAYS = 7
ALL_TENANT_ROLES = ("propietario", "administrador", "vendedor")


def new_id(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc)
def now_iso(): return now().isoformat()
def hash_password(password): return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
def verify_password(plain, hashed): return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id, email):
    return jwt.encode({"sub": str(user_id), "email": email, "type": "access", "exp": now() + timedelta(minutes=ACCESS_MINUTES)}, settings.JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id):
    return jwt.encode({"sub": str(user_id), "type": "refresh", "exp": now() + timedelta(days=REFRESH_DAYS)}, settings.JWT_SECRET, algorithm=JWT_ALGORITHM)


def set_auth_cookies(response: Response, user: dict):
    access, refresh = create_access_token(user["id"], user["email"]), create_refresh_token(user["id"])
    kwargs = {"httponly": True, "secure": settings.COOKIE_SECURE, "samesite": settings.COOKIE_SAMESITE, "path": "/"}
    if settings.COOKIE_DOMAIN: kwargs["domain"] = settings.COOKIE_DOMAIN
    response.set_cookie("access_token", access, **{**kwargs, "max_age": ACCESS_MINUTES * 60})
    response.set_cookie("refresh_token", refresh, **{**kwargs, "max_age": REFRESH_DAYS * 86400})
    return {"access_token": access, "refresh_token": refresh}


def public_user(user):
    return {"id": user["id"], "email": user["email"], "name": user.get("name", ""), "role": user.get("role", "propietario"), "platform_role": user.get("platform_role"), "business_id": user.get("business_id"), "approved": user.get("approved") is True, "approved_at": user.get("approved_at"), "created_at": user.get("created_at")}


async def get_current_user(request: Request):
    token = request.cookies.get("access_token") or (request.headers.get("Authorization", "")[7:] if request.headers.get("Authorization", "").startswith("Bearer ") else None)
    if not token: raise HTTPException(status_code=401, detail="No autenticado")
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access": raise HTTPException(status_code=401, detail="Token inválido")
    except jwt.ExpiredSignatureError: raise HTTPException(status_code=401, detail="Sesión expirada")
    except jwt.InvalidTokenError: raise HTTPException(status_code=401, detail="Token inválido")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user: raise HTTPException(status_code=401, detail="Usuario no encontrado")

    # Self-heal the most important onboarding/session invariant:
    # an owner who already has a business must keep that business linked to
    # the user even if an older account was created before business_id existed.
    if not user.get("business_id") and user.get("role", "propietario") == "propietario":
        existing_business = await db.businesses.find_one({"owner_id": user["id"]}, {"_id": 0, "id": 1})
        if existing_business and existing_business.get("id"):
            user["business_id"] = existing_business["id"]
            await db.users.update_one({"id": user["id"]}, {"$set": {"business_id": existing_business["id"]}})

    if user.get("platform_role") != "superadmin" and user.get("approved") is not True: raise HTTPException(status_code=403, detail="Cuenta pendiente de aprobación")
    return user

async def _check_tenant(user, roles):
    if not user.get("business_id"): raise HTTPException(status_code=400, detail="Primero completa el registro de tu negocio")
    business = await db.businesses.find_one({"id": user["business_id"]}, {"_id": 0, "active": 1})
    if not business: raise HTTPException(status_code=403, detail="Negocio no encontrado")
    if business.get("active") is False: raise HTTPException(status_code=403, detail="Tu cuenta está deshabilitada. Contacta al soporte de ControlPyme.")
    if user.get("role", "propietario") not in roles: raise HTTPException(status_code=403, detail="No tienes permiso para realizar esta acción")
    return user

async def require_business(user: dict = Depends(get_current_user)): return await _check_tenant(user, ALL_TENANT_ROLES)

def require_roles(*roles):
    async def dep(user=Depends(get_current_user)): return await _check_tenant(user, roles)
    return dep

async def require_superadmin(user: dict = Depends(get_current_user)):
    if user.get("platform_role") != "superadmin": raise HTTPException(status_code=403, detail="Solo el administrador de la plataforma")
    return user