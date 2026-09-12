from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException

from .demo_data import build_demo_store
from .payments import MockPaymentProvider, execute_rescue
from .phinite import (
    PhiniteConfigurationError,
    PhiniteResponseError,
    get_phinite_http_client,
    request_phinite_recommendation,
)
from .rescue import check_supply, detect_stockout, discover_suppliers, evaluate_offers
from .schemas import (
    DashboardResponse,
    EvaluateOffersRequest,
    ExecuteRescueRequest,
    ExecuteRescueResponse,
    RecommendationRequest,
    RecommendationResponse,
    Reservation,
    ReservationRequest,
    ScoredOffer,
    StockoutEvent,
    SupplyCheckRequest,
    SupplyOffer,
)


router = APIRouter(prefix="/api")
# ponytail: one process-global store; add shared persistence only for multi-process use.
store = build_demo_store()


@router.post("/reset")
def reset_demo() -> dict[str, str]:
    global store
    store = build_demo_store()
    return {"status": "reset"}


@router.get("/dashboard/{merchant_id}", response_model=DashboardResponse)
def get_dashboard(merchant_id: str) -> DashboardResponse:
    try:
        merchant = store.merchants[merchant_id]
        event = detect_stockout(store, merchant_id, "AMUL_TAAZA_500")
        item = store.get_inventory_item(merchant_id, event.sku)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=exc.args[0]) from exc

    return DashboardResponse(
        merchant_id=merchant.id,
        merchant_name=merchant.name,
        today_sales=8420,
        transactions=63,
        sku=event.sku,
        sku_name=item.name,
        stock_remaining=item.on_hand,
        shortage=event.shortage,
        stockout_in_minutes=event.stockout_in_minutes,
        estimated_sales_at_risk=event.estimated_sales_at_risk,
    )


@router.get(
    "/stockout/{merchant_id}/{sku}", response_model=StockoutEvent
)
def get_stockout(merchant_id: str, sku: str) -> StockoutEvent:
    try:
        return detect_stockout(store, merchant_id, sku)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=exc.args[0]) from exc


@router.get("/suppliers/{buyer_id}/{sku}", response_model=list[str])
def get_suppliers(buyer_id: str, sku: str) -> list[str]:
    if buyer_id not in store.merchants:
        raise HTTPException(status_code=404, detail=f"Unknown merchant {buyer_id!r}")
    return discover_suppliers(store, buyer_id, sku)


@router.post("/supply/check", response_model=SupplyOffer)
def post_supply_check(payload: SupplyCheckRequest) -> SupplyOffer:
    return check_supply(
        store,
        payload.supplier_id,
        payload.sku,
        payload.requested_quantity,
        payload.deadline_minutes,
    )


@router.post("/offers/evaluate", response_model=list[ScoredOffer])
def post_evaluate_offers(payload: EvaluateOffersRequest) -> list[ScoredOffer]:
    try:
        stockout = detect_stockout(store, payload.buyer_id, payload.sku)
        return evaluate_offers(stockout, payload.requested_quantity, payload.offers)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=exc.args[0]) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reservations", response_model=Reservation)
def post_reservation(payload: ReservationRequest) -> Reservation:
    if payload.buyer_id not in store.merchants:
        raise HTTPException(
            status_code=404, detail=f"Unknown merchant {payload.buyer_id!r}"
        )
    try:
        return store.reserve_inventory(
            supplier_id=payload.supplier_id,
            buyer_id=payload.buyer_id,
            sku=payload.sku,
            quantity=payload.quantity,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown supplier or SKU: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/rescues/execute", response_model=ExecuteRescueResponse)
def post_execute_rescue(payload: ExecuteRescueRequest) -> ExecuteRescueResponse:
    try:
        reservation, payment = execute_rescue(
            store,
            MockPaymentProvider(force_status=payload.force_payment_status),
            payload.reservation_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown reservation: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ExecuteRescueResponse(reservation=reservation, payment=payment)


@router.post("/recommendations", response_model=RecommendationResponse)
async def post_recommendation(
    payload: RecommendationRequest,
    client: Annotated[httpx.AsyncClient, Depends(get_phinite_http_client)],
) -> RecommendationResponse:
    try:
        return await request_phinite_recommendation(payload, client)
    except PhiniteConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PhiniteResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
