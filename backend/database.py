import os

from motor.motor_asyncio import AsyncIOMotorClient

from config import settings

client = AsyncIOMotorClient(settings.MONGO_URL)
db = client[settings.DB_NAME]

if not settings.MONGO_URL or not settings.DB_NAME:
    raise RuntimeError("Faltan MONGO_URL o DB_NAME. Revisa backend/.env")
