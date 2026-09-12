from .demo_data import DemoStore
from .inventory import safe_surplus
from .schemas import ScoredOffer, StockoutEvent, SupplyOffer


def detect_stockout(
    store: DemoStore, merchant_id: str, sku: str
) -> StockoutEvent:
    try:
        return store.stockout_events[(merchant_id, sku)]
    except KeyError:
        raise KeyError(f"No stockout event for merchant {merchant_id!r} and SKU {sku!r}") from None


def discover_suppliers(store: DemoStore, buyer_id: str, sku: str) -> list[str]:
    return [
        merchant_id
        for merchant_id, item_sku in store.inventory
        if merchant_id != buyer_id and item_sku == sku
    ]


def check_supply(
    store: DemoStore,
    supplier_id: str,
    sku: str,
    requested_quantity: int,
    deadline_minutes: int,
) -> SupplyOffer:
    merchant = store.merchants.get(supplier_id)
    item = store.inventory.get((supplier_id, sku))
    if merchant is None or item is None or requested_quantity <= 0:
        return SupplyOffer(
            supplier_id=supplier_id,
            supplier_name=merchant.name if merchant else supplier_id,
            can_fulfil=False,
            quantity=0,
            unit_price=0,
            eta_minutes=0,
            fulfilment=merchant.fulfilment_mode if merchant else "pickup",
        )

    quantity = min(requested_quantity, safe_surplus(item))
    return SupplyOffer(
        supplier_id=supplier_id,
        supplier_name=merchant.name,
        can_fulfil=quantity > 0,
        quantity=quantity,
        unit_price=item.rescue_price,
        eta_minutes=item.eta_minutes,
        fulfilment=merchant.fulfilment_mode,
    )


def evaluate_offers(
    stockout: StockoutEvent,
    requested_quantity: int,
    offers: list[SupplyOffer],
) -> list[ScoredOffer]:
    if requested_quantity <= 0:
        raise ValueError("Requested quantity must be positive")

    scored: list[ScoredOffer] = []
    for offer in offers:
        coverage_ratio = min(offer.quantity / requested_quantity, 1.0)
        time_buffer = max(0, stockout.stockout_in_minutes - offer.eta_minutes)
        coverage_value = 30 * coverage_ratio
        price_penalty = max(0, offer.unit_price - 18) * 5
        late_penalty = max(
            0, offer.eta_minutes - stockout.stockout_in_minutes
        ) * 2
        eligible = offer.can_fulfil and offer.quantity > 0
        scored_offer = ScoredOffer(
            **offer.model_dump(),
            total_cost=offer.quantity * offer.unit_price,
            expected_sales_protected=(
                round(stockout.estimated_sales_at_risk * coverage_ratio)
                if offer.eta_minutes <= stockout.stockout_in_minutes
                else 0
            ),
            score=time_buffer + coverage_value - price_penalty - late_penalty,
            eligible=eligible,
        )
        if eligible:
            scored.append(scored_offer)

    return sorted(
        scored,
        key=lambda offer: (-offer.score, offer.eta_minutes, offer.total_cost),
    )
