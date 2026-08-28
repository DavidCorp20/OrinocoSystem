import os
import uuid
from datetime import datetime, timezone, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, Response

from database import db

JWT_ALGORITHM = "HS256"
ACCESS_MINUTES = 15
REFRESH_DAYS = 7

ALL_TENANT_ROLES = ("propietario", "administrador", "vendedor")


def new_id() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now().isoformat()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "exp": now() + timedelta(minutes=ACCESS_MINUTES),
    }
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": now() + timedelta(days=REFRESH_DAYS),
    }
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)


def set_auth_cookies(response: Response, user: dict) -> dict:
    access = create_access_token(user["id"], user["email"])
    refresh = create_refresh_token(user["id"])
    response.set_cookie("access_token", access, httponly=True, secure=True, samesite="lax", max_age=ACCESS_MINUTES * 60, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=True, samesite="lax", max_age=REFRESH_DAYS * 86400, path="/")
    return {"access_token": access, "refresh_token": refresh}


def public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user.get("name", ""),
        "role": user.get("role", "propietario"),
        "platform_role": user.get("platform_role"),
        "business_id": user.get("business_id"),
        "created_at": user.get("created_at"),
    }


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Token inválido")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sesión expirada")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return user


async def _check_tenant(user: dict, roles: tuple) -> dict:
    if not user.get("business_id"):
        raise HTTPException(status_code=400, detail="Primero completa el registro de tu negocio")
    business = await db.businesses.find_one({"id": user["business_id"]}, {"_id": 0, "active": 1})
    if business and business.get("active") is False:
        raise HTTPException(status_code=403, detail="Tu cuenta está deshabilitada. Contacta al soporte de ControlPyme.")
    if user.get("role", "propietario") not in roles:
        raise HTTPException(status_code=403, detail="No tienes permiso para realizar esta acción")
    return user


async def require_business(user: dict = Depends(get_current_user)) -> dict:
    return await _check_tenant(user, ALL_TENANT_ROLES)


def require_roles(*roles: str):
    async def dep(user: dict = Depends(get_current_user)) -> dict:
        return await _check_tenant(user, roles)
    return dep


async def require_superadmin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("platform_role") != "superadmin":
        raise HTTPException(status_code=403, detail="Solo el administrador de la plataforma")
    return user
