import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import MenuItem, Order, Review, RewardAccount, RestaurantSettings

app = FastAPI(title="QR Restaurant Ordering API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------- Helpers -------------

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)


def oid_str(doc):
    if not doc:
        return doc
    doc["id"] = str(doc.pop("_id"))
    return doc


def require_admin(authorization: Optional[str] = Header(default=None)):
    token = authorization.replace("Bearer ", "") if authorization else None
    admin_token = os.getenv("ADMIN_TOKEN", "admin-demo-token")
    if token != admin_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


# ------------- Basic routes -------------

@app.get("/")
def root():
    return {"message": "QR Ordering API running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set",
        "database_name": "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected & Working"
            response["connection_status"] = "Connected"
            response["collections"] = db.list_collection_names()
    except Exception as e:
        response["database"] = f"⚠️ {str(e)[:80]}"
    return response

# ------------- Settings -------------

@app.get("/api/settings")
def get_settings():
    doc = db["restaurantsettings"].find_one({})
    if not doc:
        # return default settings
        defaults = RestaurantSettings().model_dump()
        defaults["_seed"] = True
        return defaults
    return oid_str(doc)

class SettingsUpdate(RestaurantSettings):
    pass

@app.put("/api/settings")
def update_settings(payload: SettingsUpdate, _: bool = Depends(require_admin)):
    data = payload.model_dump()
    existing = db["restaurantsettings"].find_one({})
    if existing:
        db["restaurantsettings"].update_one({"_id": existing["_id"]}, {"$set": data})
        doc = db["restaurantsettings"].find_one({"_id": existing["_id"]})
    else:
        _id = db["restaurantsettings"].insert_one(data).inserted_id
        doc = db["restaurantsettings"].find_one({"_id": _id})
    return oid_str(doc)

# ------------- Auth (simple) -------------

class AdminLogin(BaseModel):
    password: str

@app.post("/api/admin/login")
def admin_login(body: AdminLogin):
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
    if body.password != admin_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = os.getenv("ADMIN_TOKEN", "admin-demo-token")
    return {"token": token}

# ------------- Menu -------------

@app.get("/api/menu", response_model=List[dict])
def list_menu(category: Optional[str] = None):
    q = {"category": category} if category else {}
    items = list(db["menuitem"].find(q).sort("title", 1))
    return [oid_str(i) for i in items]

@app.post("/api/menu")
def create_menu_item(item: MenuItem, _: bool = Depends(require_admin)):
    _id = db["menuitem"].insert_one(item.model_dump()).inserted_id
    doc = db["menuitem"].find_one({"_id": _id})
    return oid_str(doc)

@app.put("/api/menu/{item_id}")
def update_menu_item(item_id: str, item: MenuItem, _: bool = Depends(require_admin)):
    oid = PyObjectId.validate(item_id)
    db["menuitem"].update_one({"_id": oid}, {"$set": item.model_dump()})
    doc = db["menuitem"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(404, "Item not found")
    return oid_str(doc)

@app.delete("/api/menu/{item_id}")
def delete_menu_item(item_id: str, _: bool = Depends(require_admin)):
    oid = PyObjectId.validate(item_id)
    res = db["menuitem"].delete_one({"_id": oid})
    if res.deleted_count == 0:
        raise HTTPException(404, "Item not found")
    return {"ok": True}

# ------------- Orders -------------

class OrderCreate(Order):
    pass

@app.post("/api/orders")
def create_order(order: OrderCreate):
    data = order.model_dump()
    _id = db["order"].insert_one(data).inserted_id
    doc = db["order"].find_one({"_id": _id})
    return oid_str(doc)

@app.get("/api/orders")
def list_orders(status: Optional[str] = None, _: bool = Depends(require_admin)):
    q = {"status": status} if status else {}
    orders = list(db["order"].find(q).sort("_id", -1))
    return [oid_str(o) for o in orders]

class OrderStatusUpdate(BaseModel):
    status: str

@app.patch("/api/orders/{order_id}")
def update_order_status(order_id: str, body: OrderStatusUpdate, _: bool = Depends(require_admin)):
    oid = PyObjectId.validate(order_id)
    db["order"].update_one({"_id": oid}, {"$set": {"status": body.status}})
    doc = db["order"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(404, "Order not found")
    return oid_str(doc)

@app.get("/api/orders/track/{order_id}")
def track_order(order_id: str):
    oid = PyObjectId.validate(order_id)
    doc = db["order"].find_one({"_id": oid}, {"status": 1})
    if not doc:
        raise HTTPException(404, "Order not found")
    return {"id": str(doc["_id"]), "status": doc["status"]}

# ------------- Reviews -------------

@app.post("/api/reviews")
def create_review(review: Review):
    _id = db["review"].insert_one(review.model_dump()).inserted_id
    doc = db["review"].find_one({"_id": _id})
    return oid_str(doc)

@app.get("/api/reviews")
def list_reviews(limit: int = 20):
    reviews = list(db["review"].find({}).sort("_id", -1).limit(limit))
    return [oid_str(r) for r in reviews]

# ------------- Rewards -------------

@app.get("/api/rewards/{phone}")
def get_rewards(phone: str):
    acc = db["rewardaccount"].find_one({"customer_phone": phone})
    if not acc:
        acc = {"customer_phone": phone, "points": 0, "tier": "Bronze"}
        _id = db["rewardaccount"].insert_one(acc).inserted_id
        acc["_id"] = _id
    return oid_str(acc)

class RewardAdd(BaseModel):
    points: int

@app.post("/api/rewards/{phone}/add")
def add_points(phone: str, body: RewardAdd, _: bool = Depends(require_admin)):
    acc = db["rewardaccount"].find_one({"customer_phone": phone})
    if not acc:
        acc = {"customer_phone": phone, "points": 0, "tier": "Bronze"}
        acc["_id"] = db["rewardaccount"].insert_one(acc).inserted_id
    new_points = max(0, acc.get("points", 0) + body.points)
    tier = "Gold" if new_points >= 500 else ("Silver" if new_points >= 200 else "Bronze")
    db["rewardaccount"].update_one({"_id": acc["_id"]}, {"$set": {"points": new_points, "tier": tier}})
    acc = db["rewardaccount"].find_one({"_id": acc["_id"]})
    return oid_str(acc)
