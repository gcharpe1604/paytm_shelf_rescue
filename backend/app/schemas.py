from typing import Literal

from pydantic import BaseModel


class Merchant(BaseModel):
    id: str
    name: str
    type: Literal["retailer", "wholesaler", "distributor"]
    lat: float
    lng: float
    fulfilment_mode: str = "pickup"


class InventoryItem(BaseModel):
    merchant_id: str
    sku: str
    name: str
    on_hand: int
    forecast_until_restock: int
    safety_stock: int
    reserved: int
    rescue_price: int
    eta_minutes: int


class StockoutEvent(BaseModel):
    merchant_id: str
    sku: str
    current_stock: int
    predicted_demand: int
    shortage: int
    stockout_in_minutes: int
    estimated_sales_at_risk: int


class SupplyOffer(BaseModel):
    supplier_id: str
    supplier_name: str
    can_fulfil: bool
    quantity: int
    unit_price: int
    eta_minutes: int
    fulfilment: str


class ScoredOffer(SupplyOffer):
    total_cost: int
    expected_sales_protected: int
    score: float
    eligible: bool


class Reservation(BaseModel):
    reservation_id: str
    supplier_id: str
    buyer_id: str
    sku: str
    quantity: int
    unit_price: int
    total_amount: int
    status: Literal["reserved", "committed", "released"]


class PaymentRecord(BaseModel):
    payment_id: str
    buyer_id: str
    seller_id: str
    amount: int
    reference: str
    status: Literal["pending", "success", "failed"]
    payment_url: str | None = None


class SupplyCheckRequest(BaseModel):
    supplier_id: str
    sku: str
    requested_quantity: int
    deadline_minutes: int


class EvaluateOffersRequest(BaseModel):
    buyer_id: str
    sku: str
    requested_quantity: int
    offers: list[SupplyOffer]


class ReservationRequest(BaseModel):
    supplier_id: str
    buyer_id: str
    sku: str
    quantity: int


class ExecuteRescueRequest(BaseModel):
    reservation_id: str
    force_payment_status: Literal["success", "failed"] = "success"


class DashboardResponse(BaseModel):
    merchant_id: str
    merchant_name: str
    today_sales: int
    transactions: int
    sku: str
    sku_name: str
    stock_remaining: int
    shortage: int
    stockout_in_minutes: int
    estimated_sales_at_risk: int


class ExecuteRescueResponse(BaseModel):
    reservation: Reservation
    payment: PaymentRecord
