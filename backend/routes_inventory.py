from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from database import db
from models import MovementIn
from routes_products import _csv_response, _xlsx_response
from security import new_id, now_iso, require_business, require_roles
from pymongo import ReturnDocument

router = APIRouter(tags=["inventory"])
ENTRY_REASONS = {"compra", "reposicion", "ajuste_positivo", "devolucion", "carga_inicial"}
EXIT_REASONS = {"venta", "danado", "perdida", "ajuste_negativo", "devolucion_proveedor"}

@router.get("/movements")
async def list_movements(product_id: Optional[str] = None, type: Optional[str] = None, user: dict = Depends(require_business)):
    query = {"business_id": user["business_id"]}
    if product_id: query["product_id"] = product_id
    if type in ("entrada", "salida"): query["type"] = type
    movements = await db.inventory_movements.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"movements": movements}

@router.post("/movements")
async def create_movement(data: MovementIn, user: dict = Depends(require_business)):
    bid = user["business_id"]
    if data.type not in ("entrada", "salida"): raise HTTPException(status_code=400, detail="Tipo de movimiento inválido")
    valid = ENTRY_REASONS if data.type == "entrada" else EXIT_REASONS
    if data.reason not in valid: raise HTTPException(status_code=400, detail="Motivo inválido para este tipo de movimiento")
    product = await db.products.find_one({"id": data.product_id, "business_id": bid})
    if not product: raise HTTPException(status_code=404, detail="Producto no encontrado")
    if data.type == "salida":
        updated = await db.products.find_one_and_update({"id": data.product_id, "business_id": bid, "stock": {"$gte": data.quantity}}, {"$inc": {"stock": -data.quantity}, "$set": {"updated_at": now_iso()}}, return_document=ReturnDocument.AFTER)
        if not updated: raise HTTPException(status_code=400, detail=f"Stock insuficiente: solo hay {product['stock']:g} unidad(es) de {product['name']}")
    else:
        updated = await db.products.find_one_and_update({"id": data.product_id, "business_id": bid}, {"$inc": {"stock": data.quantity}, "$set": {"updated_at": now_iso()}}, return_document=ReturnDocument.AFTER)
    new_stock = updated["stock"]
    movement = {"id": new_id(), "business_id": bid, "product_id": data.product_id, "product_name": product["name"], "type": data.type, "reason": data.reason, "quantity": data.quantity, "stock_after": new_stock, "user_email": user["email"], "notes": data.notes, "created_at": now_iso()}
    await db.inventory_movements.insert_one(movement); movement.pop("_id", None); return {"movement": movement, "stock": new_stock}

@router.get("/movements/export/csv")
async def export_movements(user: dict = Depends(require_roles("propietario", "administrador"))):
    movements = await db.inventory_movements.find({"business_id": user["business_id"]}, {"_id": 0}).sort("created_at", -1).to_list(20000)
    rows = [[m["created_at"][:10], m["product_name"], m["type"], m["reason"], m["quantity"], m.get("stock_after", ""), m.get("user_email", ""), m.get("notes") or ""] for m in movements]
    return _csv_response(rows, ["fecha", "producto", "tipo", "motivo", "cantidad", "stock_resultante", "usuario", "notas"], "movimientos")

@router.get("/movements/export/xlsx")
async def export_movements_xlsx(user: dict = Depends(require_roles("propietario", "administrador"))):
    movements = await db.inventory_movements.find({"business_id": user["business_id"]}, {"_id": 0}).sort("created_at", -1).to_list(20000)
    rows = [[m["created_at"][:10], m["product_name"], m["type"], m["reason"], m["quantity"], m.get("stock_after", ""), m.get("user_email", ""), m.get("notes") or ""] for m in movements]
    return _xlsx_response(rows, ["Fecha", "Producto", "Tipo", "Motivo", "Cantidad", "Stock resultante", "Usuario", "Notas"], "movimientos")
