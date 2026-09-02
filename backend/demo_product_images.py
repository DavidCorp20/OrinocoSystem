"""Assigns stable, real automotive product photographs to the demo catalog."""
import os
from urllib.parse import quote

from database import db

DEMO_EMAIL = os.getenv("DEMO_EMAIL", "demo@cuadrapp.com").strip().lower()

IMAGE_FILES = {
    "Aceite 20W-50 (galón)": "Motor oil.JPG",
    "Bujía NGK": "Sparkplug.jpg",
    "Bombillo H4 12V": "H4 halogen car lamp.jpg",
    "Filtro de aceite": "Engine oil filter.JPG",
    "Filtro de aire": "Filtry powietrza2.jpg",
    "Líquido de frenos DOT3": "Brake fluid (5049376195).jpg",
    "Pastillas de freno delanteras": "Automobile brake pad.jpg",
    "Refrigerante verde (galón)": "Coolant.jpg",
    "Limpiaparabrisas 22 pulgadas": "Windshield Wiper 1.jpg",
    "Batería 12V 600A": "Photo-CarBattery.jpg",
    "Correa de distribución": "Timing belt.jpg",
    "Termostato 82°C": "Replacement Thermostat.jpg",
    "Bomba de agua": "Water Pump.JPG",
    "Amortiguador delantero": "Shock absorber.png",
    "Rodamiento de rueda": "Vehicle-Wheel Bearing. - DPLA - 455bc705f2beced235d55c5d6aa4c75f (page 2).jpg",
    "Disco de freno delantero": "Disc brakes.jpg",
    "Sensor de oxígeno": "Oxygen sensor IMG 0488.JPG",
    "Relé automotriz 12V": "AutomotiveRelay.jpg",
    "Terminal de batería": "A battery terminal.jpg",
    "Silicón para juntas": "Motor oil bottles variousbrands.jpg",
}


def commons_url(filename: str) -> str:
    return "https://commons.wikimedia.org/wiki/Special:Redirect/file/" + quote(filename, safe="")


async def seed_demo_product_images():
    if os.getenv("DEMO_SEED_ENABLED", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        return
    user = await db.users.find_one({"email": DEMO_EMAIL})
    if not user or not user.get("business_id"):
        return
    bid = user["business_id"]
    for name, filename in IMAGE_FILES.items():
        await db.products.update_one(
            {"business_id": bid, "name": name},
            {"$set": {"image_url": commons_url(filename)}},
        )
