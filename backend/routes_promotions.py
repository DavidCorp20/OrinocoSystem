from fastapi import APIRouter, Depends, HTTPException
from database import db
from security import new_id, now_iso, require_business, require_roles

router=APIRouter(tags=["promotions"])
MANAGER=Depends(require_roles("propietario","administrador"))

@router.get("/promotions/recommendations")
async def recommendations(user:dict=MANAGER):
    bid=user["business_id"];products=await db.products.find({"business_id":bid,"status":{"$ne":"inactivo"}},{"_id":0}).to_list(5000);sales=await db.sales.find({"business_id":bid},{"_id":0,"items":1}).sort("created_at",-1).to_list(2000);sold={}
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
async def list_promotions(user:dict=MANAGER):
    return {"promotions":await db.promotions.find({"business_id":user["business_id"]},{"_id":0}).sort("created_at",-1).to_list(500)}

@router.post("/promotions")
async def create_promotion(data:dict,user:dict=MANAGER):
    bid=user["business_id"];product_ids=list(dict.fromkeys(data.get("product_ids") or ([data.get("product_id")] if data.get("product_id") else [])))
    if not product_ids:raise HTTPException(400,"Selecciona al menos un producto")
    products=await db.products.find({"business_id":bid,"id":{"$in":product_ids}},{"_id":0}).to_list(1000)
    if len(products)!=len(product_ids):raise HTTPException(400,"Uno o más productos no existen en tu catálogo")
    discount=float(data.get("discount_percent",0) or 0);promo_price=float(data.get("promotion_price",0) or 0)
    if discount<=0 or discount>=100:raise HTTPException(400,"El descuento debe estar entre 0 y 100")
    lines=[];total_original=0;total_promo=0
    for p in products:
        price=float(p.get("sale_price",0) or 0);line_promo=round(price*(1-discount/100),2);total_original+=price;total_promo+=line_promo;lines.append({"product_id":p["id"],"product_name":p["name"],"original_price":price,"promotion_price":line_promo,"cost":float(p.get("purchase_price",0) or 0)})
    if promo_price>0 and len(products)>1:total_promo=round(promo_price,2)
    promotion={"id":new_id(),"business_id":bid,"product_ids":product_ids,"products":lines,"discount_percent":discount,"original_total":round(total_original,2),"promotion_price":round(total_promo,2),"name":str(data.get("name") or "Promoción").strip()[:120],"description":str(data.get("description") or "").strip()[:300],"active":bool(data.get("active",True)),"starts_at":data.get("starts_at"),"ends_at":data.get("ends_at"),"created_at":now_iso()}
    await db.promotions.insert_one(promotion);promotion.pop("_id",None);return {"promotion":promotion}

@router.patch("/promotions/{promotion_id}")
async def toggle_promotion(promotion_id:str,data:dict,user:dict=MANAGER):
    active=bool(data.get("active",False));result=await db.promotions.update_one({"id":promotion_id,"business_id":user["business_id"]},{"$set":{"active":active,"updated_at":now_iso()}})
    if not result.matched_count:raise HTTPException(404,"Promoción no encontrada")
    return {"ok":True,"active":active}
