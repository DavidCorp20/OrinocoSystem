from fastapi import APIRouter, Depends, HTTPException
from database import db
from security import new_id, now_iso, require_business, require_roles
router=APIRouter(tags=["promotions"])
MANAGER=Depends(require_roles("propietario","administrador"))
@router.get("/promotions/recommendations")
async def recommendations(user:dict=MANAGER):
    bid=user["business_id"];products=await db.products.find({"business_id":bid,"status":{"$ne":"inactivo"}},{"_id":0}).to_list(5000);sales=await db.sales.find({"business_id":bid},{"_id":0,"items":1}).sort("created_at",-1).to_list(2000); sold={}
    for sale in sales:
        for item in sale.get("items",[]):sold[item.get("product_id")]=sold.get(item.get("product_id"),0)+float(item.get("base_quantity",item.get("quantity",0)) or 0)
    out=[]
    for p in products:
        stock=float(p.get("stock",0) or 0);sold_qty=sold.get(p["id"],0);price=float(p.get("sale_price",0) or 0);cost=float(p.get("purchase_price",0) or 0);margin=(price-cost)/price*100 if price else 0
        if stock<=0:continue
        score=(stock/(sold_qty or 1))*100
        if stock>=float(p.get("min_stock",0) or 0)*2 and (sold_qty==0 or score>=150):
            discount=min(20,max(5,round((stock/(sold_qty or 1))*3,1)));promo_price=round(price*(1-discount/100),2);promo_margin=round((promo_price-cost)/promo_price*100,1) if promo_price else 0
            out.append({"product_id":p["id"],"product_name":p["name"],"stock":stock,"sold_quantity":sold_qty,"sale_price":price,"cost":cost,"current_margin":round(margin,1),"suggested_discount_percent":discount,"suggested_price":promo_price,"estimated_margin_after":promo_margin,"reason":"stock alto frente a su rotación reciente" if sold_qty else "sin ventas registradas en el período analizado","confidence":"media" if sold_qty else "baja"})
    return {"recommendations":sorted(out,key=lambda x:x["stock"]/(x["sold_quantity"] or 1),reverse=True)[:50],"basis":"rotación, stock, costo y margen observados; recomendación orientativa, no orden de precio"}
@router.get("/promotions")
async def list_promotions(user:dict=MANAGER):return {"promotions":await db.promotions.find({"business_id":user["business_id"]},{"_id":0}).sort("created_at",-1).to_list(500)}
@router.post("/promotions")
async def create_promotion(data:dict,user:dict=MANAGER):
    product=await db.products.find_one({"id":data.get("product_id"),"business_id":user["business_id"]},{"_id":0})
    if not product:raise HTTPException(400,"Producto no encontrado")
    discount=float(data.get("discount_percent",0) or 0)
    if discount<=0 or discount>=100:raise HTTPException(400,"El descuento debe estar entre 0 y 100")
    price=float(product.get("sale_price",0) or 0);promo_price=round(price*(1-discount/100),2);cost=float(product.get("purchase_price",0) or 0)
    promotion={"id":new_id(),"business_id":user["business_id"],"product_id":product["id"],"product_name":product["name"],"discount_percent":discount,"original_price":price,"promotion_price":promo_price,"margin_after":round((promo_price-cost)/promo_price*100,1) if promo_price else 0,"name":data.get("name") or f"Promoción {product['name']}","active":True,"created_at":now_iso()}
    await db.promotions.insert_one(promotion);promotion.pop("_id",None);return {"promotion":promotion}
