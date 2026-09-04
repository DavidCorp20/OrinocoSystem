import asyncio
from database import db

async def main():
    for email, name in (("cafe.demo@platia.app","Café Aroma Caracas"),("barber.demo@platia.app","Barbería Central Caracas"),("moda.demo@platia.app","Moda Urbana Caracas")):
        user=await db.users.find_one({"email":email})
        if not user or not user.get("business_id"): continue
        bid=user["business_id"]
        if name=="Café Aroma Caracas":
            async for e in db.expenses.find({"business_id":bid}):
                await db.expenses.update_one({"id":e["id"]},{"$set":{"amount":round(float(e.get("amount",0))*0.55,2)}})
        await db.businesses.update_one({"id":bid},{"$set":{"demo_showcase_version":2,"is_demo":True,"active":True}})

if __name__=="__main__": asyncio.run(main())
