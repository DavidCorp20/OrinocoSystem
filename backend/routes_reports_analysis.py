from datetime import datetime,timedelta,timezone
from fastapi import APIRouter,Depends
from database import db
from security import require_roles
router=APIRouter(tags=["reports"])
@router.get("/reports/business-analysis")
async def business_analysis(user:dict=Depends(require_roles("propietario","administrador"))):
 bid=user["business_id"];now=datetime.now(timezone.utc);since=(now-timedelta(days=30)).isoformat()
 sales=await db.sales.find({"business_id":bid,"created_at":{"$gte":since}},{"_id":0}).to_list(50000);expenses=await db.expenses.find({"business_id":bid,"created_at":{"$gte":since}},{"_id":0}).to_list(50000);products=await db.products.find({"business_id":bid},{"_id":0}).to_list(10000)
 revenue=round(sum(float(s.get("total",0) or 0) for s in sales),2);cost=round(sum(float(s.get("cost_total",0) or 0) for s in sales),2);gross=round(revenue-cost,2);opex=round(sum(float(e.get("amount",0) or 0) for e in expenses),2);net=round(gross-opex,2);margin=round(net/revenue*100,1) if revenue else 0
 stock_value=round(sum(float(p.get("stock",0) or 0)*float(p.get("purchase_price",0) or 0) for p in products),2)
 if not sales: verdict="Sin datos suficientes"; recommendation="Registra ventas durante el período para obtener un diagnóstico real."
 elif net>0: verdict="El negocio está generando resultado positivo";recommendation="Mantén el seguimiento del margen y revisa los productos con menor rentabilidad."
 else: verdict="El negocio presenta resultado negativo";recommendation="Revisa precios, costos y gastos antes de aumentar el volumen de ventas."
 return {"period_days":30,"verdict":verdict,"recommendation":recommendation,"metrics":{"sales_count":len(sales),"revenue":revenue,"cost":cost,"gross_profit":gross,"operating_expenses":opex,"net_profit":net,"net_margin_percent":margin,"inventory_cost_value":stock_value},"generated_at":now.isoformat()}
