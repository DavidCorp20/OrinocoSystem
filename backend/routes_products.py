import csv
import io
from typing import Optional
import requests
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from database import db
from models import ProductIn
from security import new_id, now_iso, require_business, require_roles
router = APIRouter(tags=["products"])
PRODUCT_FIELDS = {"_id": 0}
MANAGER = Depends(require_roles("propietario", "administrador"))

def _csv_response(rows, headers, filename):
    buf=io.StringIO();buf.write("﻿");writer=csv.writer(buf);writer.writerow(headers);writer.writerows(rows);buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]),media_type="text/csv",headers={"Content-Disposition":f"attachment; filename={filename}.csv"})

@router.get("/products")
async def list_products(search:Optional[str]=None,category:Optional[str]=None,user:dict=Depends(require_business)):
    query={"business_id":user["business_id"]}
    if category:query["category"]=category
    if search:query["$or"]=[{"name":{"$regex":search,"$options":"i"}},{"sku":{"$regex":search,"$options":"i"}},{"barcode":{"$regex":search,"$options":"i"}}]
    return {"products":await db.products.find(query,PRODUCT_FIELDS).sort("name",1).to_list(5000)}

@router.get("/products/image-search")
async def search_product_images(q:str,user:dict=Depends(require_business)):
    q=q.strip()
    if len(q)<2:raise HTTPException(400,"Indica un producto para buscar")
    try:
        r=requests.get("https://api.openverse.org/v1/images/",params={"q":q,"page_size":12,"mature":"false"},timeout=8);r.raise_for_status();data=r.json();results=[]
        for x in data.get("results",[]):
            url=x.get("thumbnail") or x.get("url")
            if url:results.append({"url":url,"thumbnail":x.get("thumbnail") or url,"title":x.get("title") or q,"source":x.get("foreign_landing_url") or "","creator":x.get("creator") or ""})
        return {"query":q,"images":results}
    except Exception:return {"query":q,"images":[]}

@router.post("/products")
async def create_product(data:ProductIn,user:dict=MANAGER):
    bid=user["business_id"];count=await db.products.count_documents({"business_id":bid});product={"id":new_id(),"business_id":bid,**data.model_dump(),"sku":data.sku or f"P-{count+1:04d}","category":data.category or "General","status":"activo","created_at":now_iso(),"updated_at":now_iso()}
    await db.products.insert_one(product)
    if product["stock"]>0:await db.inventory_movements.insert_one({"id":new_id(),"business_id":bid,"product_id":product["id"],"product_name":product["name"],"type":"entrada","reason":"carga_inicial","quantity":product["stock"],"stock_after":product["stock"],"user_email":user["email"],"notes":None,"created_at":now_iso()})
    product.pop("_id",None);return {"product":product}

@router.put("/products/{product_id}")
async def update_product(product_id:str,data:ProductIn,user:dict=MANAGER):
    bid=user["business_id"];product=await db.products.find_one({"id":product_id,"business_id":bid})
    if not product:raise HTTPException(404,"Producto no encontrado")
    updates=data.model_dump();updates.pop("stock",None);updates["updated_at"]=now_iso();await db.products.update_one({"id":product_id},{"$set":updates})
    return {"product":await db.products.find_one({"id":product_id},PRODUCT_FIELDS)}

@router.delete("/products/{product_id}")
async def delete_product(product_id:str,user:dict=MANAGER):
    result=await db.products.delete_one({"id":product_id,"business_id":user["business_id"]})
    if result.deleted_count==0:raise HTTPException(404,"Producto no encontrado")
    return {"ok":True}

@router.get("/products/export/csv")
async def export_products(user:dict=MANAGER):
    products=await db.products.find({"business_id":user["business_id"]},PRODUCT_FIELDS).sort("name",1).to_list(10000);rows=[[p["name"],p.get("sku",""),p.get("category",""),p.get("brand") or "",p.get("supplier") or "",p.get("purchase_price",0),p.get("sale_price",0),p.get("stock",0),p.get("min_stock",0),p.get("max_stock") or "",p.get("unit","unidad"),p.get("image_url") or ""] for p in products]
    return _csv_response(rows,["nombre","sku","categoria","marca","proveedor","precio_compra","precio_venta","stock","stock_minimo","stock_maximo","unidad","imagen_url"],"productos")

@router.post("/products/import")
async def import_products(file:UploadFile=File(...),user:dict=MANAGER):
    content=(await file.read()).decode("utf-8-sig");reader=csv.DictReader(io.StringIO(content));bid=user["business_id"];count=await db.products.count_documents({"business_id":bid});created=0
    def num(v,default=0.0):
        try:return float(str(v).replace(",",".").strip())
        except (TypeError,ValueError):return default
    for row in reader:
        name=(row.get("nombre") or row.get("name") or "").strip()
        if not name:continue
        count+=1;created+=1;product={"id":new_id(),"business_id":bid,"name":name,"sku":(row.get("sku") or "").strip() or f"P-{count:04d}","barcode":(row.get("codigo_barras") or row.get("barcode") or "").strip() or None,"category":(row.get("categoria") or row.get("category") or "").strip() or "General","brand":(row.get("marca") or "").strip() or None,"supplier":(row.get("proveedor") or "").strip() or None,"purchase_price":num(row.get("precio_compra")),"sale_price":num(row.get("precio_venta")),"stock":num(row.get("stock")),"min_stock":num(row.get("stock_minimo"),5),"max_stock":num(row.get("stock_maximo")) or None,"unit":(row.get("unidad") or "unidad").strip(),"image_url":(row.get("imagen_url") or row.get("image_url") or "").strip() or None,"status":"activo","created_at":now_iso(),"updated_at":now_iso()}
        await db.products.insert_one(product)
        if product["stock"]>0:await db.inventory_movements.insert_one({"id":new_id(),"business_id":bid,"product_id":product["id"],"product_name":product["name"],"type":"entrada","reason":"carga_inicial","quantity":product["stock"],"stock_after":product["stock"],"user_email":user["email"],"notes":"Importado desde CSV","created_at":now_iso()})
    return {"created":created}
