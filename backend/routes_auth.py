from datetime import timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from config import settings
from database import db
from models import LoginIn, RegisterIn
from security import create_access_token, get_current_user, hash_password, new_id, now, now_iso, public_user, set_auth_cookies, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
MAX_ATTEMPTS = 5
LOCK_MINUTES = 15


async def _business_of(user: dict):
    business_id = user.get("business_id")
    if not business_id and user.get("role", "propietario") == "propietario":
        business = await db.businesses.find_one({"owner_id": user["id"]}, {"_id": 0, "id": 1})
        if business and business.get("id"):
            business_id = business["id"]
            await db.users.update_one({"id": user["id"]}, {"$set": {"business_id": business_id}})
            user["business_id"] = business_id
    if not business_id:
        return None
    return await db.businesses.find_one({"id": business_id}, {"_id": 0})


@router.post("/register")
async def register(data: RegisterIn, response: Response):
    email = data.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Ya existe una cuenta con este correo")
    user = {"id": new_id(), "email": email, "name": data.name.strip(), "password_hash": hash_password(data.password), "role": "propietario", "platform_role": None, "business_id": None, "approved": False, "approved_at": None, "approved_by": None, "created_at": now_iso()}
    await db.users.insert_one(user)
    return {"user": public_user(user), "business": None, "pending_approval": True}


@router.post("/login")
async def login(data: LoginIn, request: Request, response: Response):
    email = data.email.strip().lower()
    attempts = await db.login_attempts.find_one({"identifier": email})
    if attempts and attempts.get("count", 0) >= MAX_ATTEMPTS:
        if attempts.get("locked_until", "") > now_iso():
            raise HTTPException(status_code=429, detail="Demasiados intentos fallidos. Intenta de nuevo en 15 minutos.")
        await db.login_attempts.update_one({"identifier": email}, {"$set": {"count": 0, "locked_until": ""}})
        attempts = None
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(data.password, user["password_hash"]):
        count = (attempts.get("count", 0) if attempts else 0) + 1
        locked_until = (now() + timedelta(minutes=LOCK_MINUTES)).isoformat() if count >= MAX_ATTEMPTS else ""
        await db.login_attempts.update_one({"identifier": email}, {"$set": {"identifier": email, "count": count, "locked_until": locked_until}}, upsert=True)
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")

    await db.login_attempts.delete_one({"identifier": email})

    configured_admin = (settings.ADMIN_EMAIL or "").strip().lower()
    if configured_admin and email == configured_admin:
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {"platform_role": "superadmin", "approved": True, "approved_at": now_iso(), "approved_by": "system_admin_login"}},
        )
        user["platform_role"] = "superadmin"
        user["approved"] = True
        user["approved_at"] = now_iso()
        user["approved_by"] = "system_admin_login"

    if user.get("platform_role") != "superadmin" and user.get("approved") is not True:
        raise HTTPException(status_code=403, detail="Tu cuenta está pendiente de aprobación. Te avisaremos cuando puedas ingresar.")
    if user.get("business_id"):
        biz = await db.businesses.find_one({"id": user["business_id"]}, {"active": 1})
        if biz and biz.get("active") is False:
            raise HTTPException(status_code=403, detail="Tu cuenta está deshabilitada. Contacta al soporte de ControlPyme.")
    tokens = set_auth_cookies(response, user)
    return {"user": public_user(user), "business": await _business_of(user), **tokens}


@router.post("/logout")
async def logout(response: Response):
    cookie_kwargs = {"path": "/"}
    if settings.COOKIE_DOMAIN:
        cookie_kwargs["domain"] = settings.COOKIE_DOMAIN
    response.delete_cookie("access_token", **cookie_kwargs)
    response.delete_cookie("refresh_token", **cookie_kwargs)
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {"user": public_user(user), "business": await _business_of(user)}


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Sin sesión")
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Token inválido")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")
    user = await db.users.find_one({"id": payload["sub"]})
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    if user.get("platform_role") != "superadmin" and user.get("approved") is not True:
        raise HTTPException(status_code=403, detail="Tu cuenta está pendiente de aprobación.")
    access = create_access_token(user["id"], user["email"])
    cookie_kwargs = {"httponly": True, "secure": settings.COOKIE_SECURE, "samesite": settings.COOKIE_SAMESITE, "max_age": 15 * 60, "path": "/"}
    if settings.COOKIE_DOMAIN:
        cookie_kwargs["domain"] = settings.COOKIE_DOMAIN
    response.set_cookie("access_token", access, **cookie_kwargs)
    return {"ok": True, "access_token": access}
