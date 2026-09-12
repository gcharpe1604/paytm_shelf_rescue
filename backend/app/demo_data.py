from uuid import uuid4

from .inventory import safe_surplus
from .schemas import InventoryItem, Merchant, Reservation, StockoutEvent


class DemoStore:
    def __init__(
        self,
        merchants: dict[str, Merchant],
        inventory: dict[tuple[str, str], InventoryItem],
        stockout_events: dict[tuple[str, str], StockoutEvent],
    ) -> None:
        self.merchants = merchants
        self.inventory = inventory
        self.stockout_events = stockout_events
        self.reservations: dict[str, Reservation] = {}
        self.buyer_incoming_stock: dict[tuple[str, str], int] = {}

    def get_inventory_item(self, merchant_id: str, sku: str) -> InventoryItem:
        return self.inventory[(merchant_id, sku)]

    def get_reservation(self, reservation_id: str) -> Reservation:
        return self.reservations[reservation_id]

    def reserve_inventory(
        self,
        supplier_id: str,
        buyer_id: str,
        sku: str,
        quantity: int,
    ) -> Reservation:
        item = self.get_inventory_item(supplier_id, sku)
        if quantity <= 0:
            raise ValueError("Reservation quantity must be positive")
        if quantity > safe_surplus(item):
            raise ValueError("Reservation quantity exceeds safe surplus")

        item.reserved += quantity
        reservation = Reservation(
            reservation_id=str(uuid4()),
            supplier_id=supplier_id,
            buyer_id=buyer_id,
            sku=sku,
            quantity=quantity,
            unit_price=item.rescue_price,
            total_amount=quantity * item.rescue_price,
            status="reserved",
        )
        self.reservations[reservation.reservation_id] = reservation
        return reservation

    def release_reservation(self, reservation_id: str) -> Reservation:
        reservation = self.get_reservation(reservation_id)
        if reservation.status == "released":
            return reservation
        if reservation.status != "reserved":
            raise ValueError("Only a reserved reservation can be released")

        item = self.get_inventory_item(reservation.supplier_id, reservation.sku)
        item.reserved -= reservation.quantity
        reservation.status = "released"
        return reservation

    def commit_reservation(self, reservation_id: str) -> Reservation:
        reservation = self.get_reservation(reservation_id)
        if reservation.status == "committed":
            return reservation
        if reservation.status != "reserved":
            raise ValueError("Only a reserved reservation can be committed")

        item = self.get_inventory_item(reservation.supplier_id, reservation.sku)
        item.on_hand -= reservation.quantity
        item.reserved -= reservation.quantity
        incoming_key = (reservation.buyer_id, reservation.sku)
        self.buyer_incoming_stock[incoming_key] = (
            self.buyer_incoming_stock.get(incoming_key, 0) + reservation.quantity
        )
        reservation.status = "committed"
        return reservation


def build_demo_store() -> DemoStore:
    merchants = {
        "sharma-kirana": Merchant(
            id="sharma-kirana",
            name="Sharma Kirana",
            type="retailer",
            lat=28.6139,
            lng=77.2090,
        ),
        "gupta-store": Merchant(
            id="gupta-store",
            name="Gupta General Store",
            type="retailer",
            lat=28.6150,
            lng=77.2100,
        ),
        "abc-wholesale": Merchant(
            id="abc-wholesale",
            name="ABC Wholesale",
            type="wholesaler",
            lat=28.6200,
            lng=77.2200,
        ),
    }
    inventory_items = [
        InventoryItem(
            merchant_id="sharma-kirana",
            sku="AMUL_TAAZA_500",
            name="Amul Taaza 500ml",
            on_hand=6,
            forecast_until_restock=19,
            safety_stock=0,
            reserved=0,
            rescue_price=0,
            eta_minutes=0,
        ),
        InventoryItem(
            merchant_id="gupta-store",
            sku="AMUL_TAAZA_500",
            name="Amul Taaza 500ml",
            on_hand=30,
            forecast_until_restock=11,
            safety_stock=4,
            reserved=2,
            rescue_price=19,
            eta_minutes=12,
        ),
        InventoryItem(
            merchant_id="abc-wholesale",
            sku="AMUL_TAAZA_500",
            name="Amul Taaza 500ml",
            on_hand=120,
            forecast_until_restock=20,
            safety_stock=10,
            reserved=0,
            rescue_price=18,
            eta_minutes=42,
        ),
    ]
    inventory = {
        (item.merchant_id, item.sku): item for item in inventory_items
    }
    stockout = StockoutEvent(
        merchant_id="sharma-kirana",
        sku="AMUL_TAAZA_500",
        current_stock=6,
        predicted_demand=19,
        shortage=13,
        stockout_in_minutes=55,
        estimated_sales_at_risk=320,
    )
    return DemoStore(
        merchants=merchants,
        inventory=inventory,
        stockout_events={(stockout.merchant_id, stockout.sku): stockout},
    )
