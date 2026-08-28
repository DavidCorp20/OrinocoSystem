from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class InitialProduct(BaseModel):
    name: str
    sale_price: float = 0
    purchase_price: float = 0
    stock: float = 0
    category: Optional[str] = None


class BusinessIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    type: str
    currency: str = "USD"
    initial_products: List[InitialProduct] = []


class SettingsIn(BaseModel):
    rif: Optional[str] = Field(default=None, max_length=20)
    address: Optional[str] = Field(default=None, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=30)
    bcv_mode: Optional[str] = None  # auto | manual
    bcv_rate: Optional[float] = Field(default=None, gt=0)


class TeamUserIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str  # administrador | vendedor


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    sku: Optional[str] = None
    barcode: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    supplier: Optional[str] = None
    purchase_price: float = Field(default=0, ge=0)
    sale_price: float = Field(default=0, ge=0)
    stock: float = Field(default=0, ge=0)
    min_stock: float = Field(default=5, ge=0)
    max_stock: Optional[float] = None
    unit: str = "unidad"


class MovementIn(BaseModel):
    product_id: str
    type: str  # entrada | salida
    reason: str
    quantity: float = Field(gt=0)
    notes: Optional[str] = None


class SaleItemIn(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
    unit_price: Optional[float] = Field(default=None, ge=0)
    discount: float = Field(default=0, ge=0)


class SaleIn(BaseModel):
    items: List[SaleItemIn] = Field(min_length=1)
    payment_method: str = "efectivo"
    customer_name: Optional[str] = None
    customer_rif: Optional[str] = None


class PurchaseItemIn(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
    unit_cost: float = Field(ge=0)


class PurchaseIn(BaseModel):
    supplier: Optional[str] = None
    supplier_rif: Optional[str] = None
    items: List[PurchaseItemIn] = Field(min_length=1)
    payment_method: str = "efectivo"
    status: str = "completada"


class ExpenseIn(BaseModel):
    category: str
    description: str = Field(min_length=1, max_length=200)
    amount: float = Field(gt=0)
    date: Optional[str] = None


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class BusinessStatusIn(BaseModel):
    active: bool


class PlatformExpenseIn(BaseModel):
    category: str
    description: str = Field(min_length=1, max_length=200)
    amount: float = Field(gt=0)
    date: Optional[str] = None
