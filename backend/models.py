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
    purchase_price: float = 0
    sale_price: float = 0
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
    bcv_mode: Optional[str] = None
    bcv_rate: Optional[float] = Field(default=None, gt=0)
    iva_enabled: Optional[bool] = None
    iva_percent: Optional[float] = Field(default=None, ge=0, le=100)
    igtf_enabled: Optional[bool] = None
    igtf_percent: Optional[float] = Field(default=None, ge=0, le=100)
    delivery_enabled: Optional[bool] = None
    delivery_amount: Optional[float] = Field(default=None, ge=0)
class TeamUserIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str
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
class PriceSuggestionIn(BaseModel):
    purchase_price: float = Field(ge=0)
    target_margin_percent: float = Field(default=35, ge=1, le=90)
class RecipeIngredientIn(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
class RecipeIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    output_product_id: Optional[str] = None
    yield_quantity: float = Field(default=1, gt=0)
    ingredients: List[RecipeIngredientIn] = Field(min_length=1)
class MovementIn(BaseModel):
    product_id: str
    type: str
    reason: str
    quantity: float = Field(gt=0)
    notes: Optional[str] = None
class SaleItemIn(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
    unit_price: Optional[float] = Field(default=None, ge=0)
    discount: float = Field(default=0, ge=0)
class PaymentPartIn(BaseModel):
    method: str = Field(min_length=2, max_length=30)
    amount: float = Field(gt=0)
class SaleIn(BaseModel):
    items: List[SaleItemIn] = Field(min_length=1)
    payment_method: str = "efectivo"
    payment_parts: List[PaymentPartIn] = []
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
    payment_parts: List[PaymentPartIn] = []
    status: str = "completada"
class ExpenseIn(BaseModel):
    category: str
    description: str = Field(min_length=1, max_length=200)
    amount: float = Field(gt=0)
    date: Optional[str] = None
class ObligationIn(BaseModel):
    kind: str = Field(pattern="^(por_cobrar|por_pagar)$")
    contact: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=200)
    amount: float = Field(gt=0)
    due_date: str
    notes: Optional[str] = Field(default=None, max_length=300)
class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
class BusinessStatusIn(BaseModel):
    active: bool
class PlatformExpenseIn(BaseModel):
    category: str
    description: str = Field(min_length=1, max_length=200)
    amount: float = Field(gt=0)
    date: Optional[str] = None
class PlatformPlanIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    description: Optional[str] = Field(default=None, max_length=300)
    monthly_price_usd: float = Field(gt=0)
    active: bool = True
    features: List[str] = []
class PlatformSubscriptionIn(BaseModel):
    plan_id: str
    status: str = Field(default="activo", pattern="^(activo|pendiente|vencido|cancelado)$")
    due_date: Optional[str] = None
    monthly_price_usd: Optional[float] = Field(default=None, gt=0)
class UserApprovalIn(BaseModel):
    approved: bool
class AdminPasswordResetIn(BaseModel):
    password: str = Field(min_length=8, max_length=128)
