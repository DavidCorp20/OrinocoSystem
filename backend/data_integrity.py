"""Read-only Phase 1 integrity checks for PLATIA."""
from collections import Counter
from database import db

COLLECTIONS=("products","sales","purchases","inventory_movements","expenses","customers","suppliers","supplier_events","obligations","obligation_payments","cash_closures","cash_movements")

async def _scan_ids(collection, scope):
    ids=[]
    async for doc in db[collection].find(scope,{"id":1}):
        if doc.get("id"): ids.append(doc["id"])
    counts=Counter(ids)
    return set(ids),sum(1 for n in counts.values() if n>1)

async def run_data_integrity_checks(business_id: str | None = None) -> dict:
    scope={"business_id":business_id} if business_id else {}
    result={}
    for collection in COLLECTIONS:
        total=await db[collection].count_documents(scope)
        missing=await db[collection].count_documents({"business_id":{"$exists":False}})
        result[collection]={"total":total,"missing_business_id":missing}

    products,dup_products=await _scan_ids("products",scope)
    customers,dup_customers=await _scan_ids("customers",scope)
    suppliers,dup_suppliers=await _scan_ids("suppliers",scope)
    obligations,dup_obligations=await _scan_ids("obligations",scope)

    bad_inventory=0
    async for movement in db.inventory_movements.find(scope,{"product_id":1}):
        if movement.get("product_id") not in products: bad_inventory+=1
    bad_supplier_events=0
    async for event in db.supplier_events.find(scope,{"supplier_id":1}):
        if event.get("supplier_id") not in suppliers: bad_supplier_events+=1
    bad_payments=0
    payment_totals=Counter()
    async for payment in db.obligation_payments.find(scope,{"obligation_id":1,"amount":1}):
        oid=payment.get("obligation_id")
        if oid not in obligations: bad_payments+=1
        else: payment_totals[oid]+=float(payment.get("amount",0) or 0)

    negative_outstanding=0; status_mismatch=0; bad_party_refs=0
    async for obligation in db.obligations.find(scope,{"id":1,"kind":1,"customer_id":1,"supplier_id":1,"original_amount":1,"amount":1,"paid_amount":1,"remaining_amount":1,"outstanding_amount":1,"status":1}):
        oid=obligation.get("id"); original=float(obligation.get("original_amount",obligation.get("amount",0)) or 0); paid=float(obligation.get("paid_amount",0) or 0); remaining=float(obligation.get("remaining_amount",obligation.get("outstanding_amount",original-paid)) or 0)
        if remaining < -0.009 or float(obligation.get("outstanding_amount",remaining) or 0) < -0.009: negative_outstanding+=1
        expected=max(0,round(original-paid,2)); status=obligation.get("status")
        if status in {"pendiente","parcial","pagada"} and abs(remaining-expected)>0.02: status_mismatch+=1
        if obligation.get("kind")=="por_cobrar" and obligation.get("customer_id") and obligation["customer_id"] not in customers: bad_party_refs+=1
        if obligation.get("kind")=="por_pagar" and obligation.get("supplier_id") and obligation["supplier_id"] not in suppliers: bad_party_refs+=1
        if oid and abs(payment_totals.get(oid,0)-paid)>0.02: status_mismatch+=1

    bad_cash=0
    async for movement in db.cash_movements.find(scope,{"direction":1,"amount":1,"business_id":1,"source_type":1,"source_id":1}):
        if movement.get("direction") not in {"in","out"} or float(movement.get("amount",0) or 0)<=0 or not movement.get("business_id") or not movement.get("source_type") or not movement.get("source_id"): bad_cash+=1

    result["duplicates"]={"products":dup_products,"customers":dup_customers,"suppliers":dup_suppliers,"obligations":dup_obligations}
    result["references"]={"inventory_movements_missing_product":bad_inventory,"supplier_events_missing_supplier":bad_supplier_events,"obligation_payments_missing_obligation":bad_payments,"obligations_missing_party":bad_party_refs}
    result["financial"]={"negative_outstanding":negative_outstanding,"obligation_status_or_payment_mismatch":status_mismatch,"malformed_cash_movements":bad_cash}
    result["ok"]=all(v==0 for section in (result["duplicates"],result["references"],result["financial"]) for v in section.values())
    return result
