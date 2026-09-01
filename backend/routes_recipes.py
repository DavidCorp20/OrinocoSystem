from fastapi import APIRouter, Depends, HTTPException
from database import db
from models import PriceSuggestionIn, RecipeIn
from security import new_id, now_iso, require_roles

router = APIRouter(tags=["recipes"])
MANAGER = Depends(require_roles("propietario", "administrador"))

@router.get("/recipes")
async def list_recipes(user: dict = MANAGER):
    recipes = await db.recipes.find({"business_id": user["business_id"]}, {"_id": 0}).sort("name", 1).to_list(1000)
    return {"recipes": recipes}

@router.post("/recipes")
async def create_recipe(data: RecipeIn, user: dict = MANAGER):
    bid = user["business_id"]
    ids = [i.product_id for i in data.ingredients] + ([data.output_product_id] if data.output_product_id else [])
    products = await db.products.find({"business_id": bid, "id": {"$in": ids}}, {"_id": 0, "id": 1, "name": 1, "purchase_price": 1, "unit": 1}).to_list(1000)
    catalog = {p["id"]: p for p in products}
    if any(i.product_id not in catalog for i in data.ingredients) or (data.output_product_id and data.output_product_id not in catalog):
        raise HTTPException(status_code=400, detail="Todos los productos de la receta deben pertenecer a tu negocio")
    if data.output_product_id and data.output_product_id in {i.product_id for i in data.ingredients}:
        raise HTTPException(status_code=400, detail="El producto terminado no puede ser ingrediente de sí mismo")
    ingredients = [{"product_id": i.product_id, "name": catalog[i.product_id]["name"], "quantity": i.quantity, "unit": catalog[i.product_id].get("unit", "unidad")} for i in data.ingredients]
    cost = round(sum(float(i["quantity"]) * float(catalog[i["product_id"]].get("purchase_price", 0) or 0) for i in ingredients), 4)
    recipe = {"id": new_id(), "business_id": bid, "name": data.name.strip(), "output_product_id": data.output_product_id, "yield_quantity": data.yield_quantity, "ingredients": ingredients, "estimated_cost": cost, "cost_per_output": round(cost / data.yield_quantity, 4), "created_at": now_iso(), "updated_at": now_iso()}
    await db.recipes.insert_one(recipe); recipe.pop("_id", None)
    return {"recipe": recipe}

@router.put("/recipes/{recipe_id}")
async def update_recipe(recipe_id: str, data: RecipeIn, user: dict = MANAGER):
    existing = await db.recipes.find_one({"id": recipe_id, "business_id": user["business_id"]})
    if not existing: raise HTTPException(status_code=404, detail="Receta no encontrada")
    # Reuse creation validation by calculating from the current catalog.
    ids = [i.product_id for i in data.ingredients] + ([data.output_product_id] if data.output_product_id else [])
    products = await db.products.find({"business_id": user["business_id"], "id": {"$in": ids}}, {"_id": 0, "id": 1, "name": 1, "purchase_price": 1, "unit": 1}).to_list(1000)
    catalog = {p["id"]: p for p in products}
    if any(i.product_id not in catalog for i in data.ingredients) or (data.output_product_id and data.output_product_id not in catalog): raise HTTPException(status_code=400, detail="Producto inválido en la receta")
    ingredients = [{"product_id": i.product_id, "name": catalog[i.product_id]["name"], "quantity": i.quantity, "unit": catalog[i.product_id].get("unit", "unidad")} for i in data.ingredients]
    cost = round(sum(float(i["quantity"]) * float(catalog[i["product_id"]].get("purchase_price", 0) or 0) for i in ingredients), 4)
    patch = {"name": data.name.strip(), "output_product_id": data.output_product_id, "yield_quantity": data.yield_quantity, "ingredients": ingredients, "estimated_cost": cost, "cost_per_output": round(cost / data.yield_quantity, 4), "updated_at": now_iso()}
    await db.recipes.update_one({"id": recipe_id, "business_id": user["business_id"]}, {"$set": patch})
    return {"recipe": {**existing, **patch, "id": recipe_id, "business_id": user["business_id"]}}

@router.delete("/recipes/{recipe_id}")
async def delete_recipe(recipe_id: str, user: dict = MANAGER):
    result = await db.recipes.delete_one({"id": recipe_id, "business_id": user["business_id"]})
    if not result.deleted_count: raise HTTPException(status_code=404, detail="Receta no encontrada")
    return {"ok": True}

@router.post("/products/price-suggestion")
async def price_suggestion(data: PriceSuggestionIn, user: dict = MANAGER):
    bid = user["business_id"]
    expenses = await db.expenses.find({"business_id": bid}, {"_id": 0, "amount": 1}).to_list(5000)
    sales = await db.sales.find({"business_id": bid}, {"_id": 0, "total": 1}).to_list(5000)
    monthly_expense = sum(float(e.get("amount", 0) or 0) for e in expenses[-100:])
    revenue = sum(float(s.get("total", 0) or 0) for s in sales[-100:])
    expense_ratio = min(monthly_expense / revenue, 0.5) if revenue else 0
    # Suggested gross margin rises modestly when the business has a meaningful expense load.
    effective_margin = min(max(data.target_margin_percent / 100 + expense_ratio * 0.25, 0.05), 0.85)
    suggested = round(data.purchase_price / (1 - effective_margin), 2) if data.purchase_price else 0
    return {"purchase_price": data.purchase_price, "suggested_sale_price": suggested, "target_margin_percent": round(effective_margin * 100, 1), "basis": "estimación por costo, margen objetivo y proporción observada de gastos; no representa precio de mercado", "observed_expense_ratio": round(expense_ratio * 100, 1)}
