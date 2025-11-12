"""
Database Schemas for QR Restaurant Ordering App

Each Pydantic model maps to a MongoDB collection using the lowercase
class name as the collection name.

Examples:
- MenuItem -> "menuitem"
- Order -> "order"
- Review -> "review"
- RewardAccount -> "rewardaccount"
- RestaurantSettings -> "restaurantsettings"
"""

from pydantic import BaseModel, Field, HttpUrl, EmailStr
from typing import List, Optional, Literal
from datetime import datetime

# ---------- Customer-facing domain ----------

class MenuItem(BaseModel):
    title: str = Field(..., description="Item name")
    description: Optional[str] = Field(None, description="Item description")
    price: float = Field(..., ge=0, description="Price in currency units")
    category: Literal["Drinks", "Desserts", "Meals"] = Field(
        ..., description="Menu category"
    )
    image_url: Optional[HttpUrl] = Field(None, description="Item image URL")
    is_available: bool = Field(True)

class OrderItem(BaseModel):
    item_id: str = Field(..., description="MenuItem _id")
    title: str
    quantity: int = Field(..., ge=1)
    unit_price: float = Field(..., ge=0)
    notes: Optional[str] = None

class Order(BaseModel):
    customer_name: Optional[str] = None
    table_number: Optional[str] = None
    items: List[OrderItem]
    total_amount: float = Field(..., ge=0)
    status: Literal["Pending", "Ready", "Completed", "Canceled"] = Field("Pending")
    payment_status: Literal["Unpaid", "Paid", "Refunded"] = Field("Unpaid")
    created_at: Optional[datetime] = None

class Review(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    photo_url: Optional[HttpUrl] = None
    customer_name: Optional[str] = None
    order_id: Optional[str] = None
    created_at: Optional[datetime] = None

class RewardAccount(BaseModel):
    customer_phone: str = Field(..., description="Phone number used as identifier")
    points: int = Field(0, ge=0)
    tier: Literal["Bronze", "Silver", "Gold"] = Field("Bronze")

# ---------- Admin and settings ----------

class RestaurantSettings(BaseModel):
    restaurant_name: str = Field("Your Restaurant")
    logo_url: Optional[HttpUrl] = None
    primary_color: str = Field("#4f46e5")  # Indigo
    languages: List[str] = Field(["en", "ar"])  # supported locales
    default_language: str = Field("en")
    theme: Literal["light", "dark", "system"] = Field("light")
    currency: str = Field("USD")
    address: Optional[str] = None
    contact_email: Optional[EmailStr] = None
