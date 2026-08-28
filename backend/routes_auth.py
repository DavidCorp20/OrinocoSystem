import os
from datetime import timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from database import db
from models import LoginIn, RegisterIn
from security import (
    create_access_token, get_current_user, hash_password, new_id, now, now_iso,
    public_user, set_auth_cookies, verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

MAX_ATTEMPTS = 5
LOCK_MINUTES = 15


async def _business_of(user: dict):
    if not user.get("business_id"):
        return None
    return await db.businesses.find_one({"id": user["business_id"]}, {"_id": 0})


@router.post("/register")
async def register(data: RegisterIn, response: Response):
    email = data.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Ya existe una cuenta con este correo")
    user = {
        "id": new_id(),
        "email": email,
        "name": data.name.strip(),
        "password_hash": hash_password(data.password),
        "role": "propietario",
        "platform_role": None,
        "business_id": None,
        "created_at": now_iso(),
    }
    await db.users.insert_one(user)
    tokens = set_auth_cookies(response, user)
    return {"user": public_user(user), "business": None, **tokens}


@router.post("/login")
async def login(data: LoginIn, request: Request, response: Response):
    email = data.email.lower()
    identifier = email

    attempts = await db.login_attempts.find_one({"identifier": identifier})
    if attempts and attempts.get("count", 0) >= MAX_ATTEMPTS:
        if attempts.get("locked_until", "") > now_iso():
            raise HTTPException(status_code=429, detail="Demasiados intentos fallidos. Intenta de nuevo en 15 minutos.")
        await db.login_attempts.update_one({"identifier": identifier}, {"$set": {"count": 0, "locked_until": ""}})
        attempts = None

    user = await db.users.find_one({"email": email})
    if not user or not verify_password(data.password, user["password_hash"]):
        count = (attempts.get("count", 0) if attempts else 0) + 1
        locked_until = (now() + timedelta(minutes=LOCK_MINUTES)).isoformat() if count >= MAX_ATTEMPTS else ""
        await db.login_attempts.update_one(
            {"identifier": identifier},
            {"$set": {"identifier": identifier, "count": count, "locked_until": locked_until}},
            upsert=True,
        )
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")

    await db.login_attempts.delete_one({"identifier": identifier})
    if user.get("business_id"):
        biz = await db.businesses.find_one({"id": user["business_id"]}, {"active": 1})
        if biz and biz.get("active") is False:
            raise HTTPException(status_code=403, detail="Tu cuenta está deshabilitada. Contacta al soporte de ControlPyme.")
    tokens = set_auth_cookies(response, user)
    return {"user": public_user(user), "business": await _business_of(user), **tokens}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
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
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Token inválido")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")
    user = await db.users.find_one({"id": payload["sub"]})
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    access = create_access_token(user["id"], user["email"])
    response.set_cookie("access_token", access, httponly=True, secure=True, samesite="lax", max_age=15 * 60, path="/")
    return {"ok": True, "access_token": access}
