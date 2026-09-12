from app.demo_data import build_demo_store
from app.inventory import safe_surplus


def test_safe_surplus_matches_gupta_demo_state():
    store = build_demo_store()
    item = store.get_inventory_item("gupta-store", "AMUL_TAAZA_500")
    assert safe_surplus(item) == 13


def test_reservation_cannot_exceed_safe_surplus():
    store = build_demo_store()
    try:
        store.reserve_inventory(
            supplier_id="gupta-store",
            buyer_id="sharma-kirana",
            sku="AMUL_TAAZA_500",
            quantity=14,
        )
    except ValueError as exc:
        assert "safe surplus" in str(exc).lower()
    else:
        raise AssertionError("expected reservation to fail")


def test_reservation_reduces_available_safe_surplus():
    store = build_demo_store()
    reservation = store.reserve_inventory(
        supplier_id="gupta-store",
        buyer_id="sharma-kirana",
        sku="AMUL_TAAZA_500",
        quantity=5,
    )
    assert reservation.status == "reserved"
    item = store.get_inventory_item("gupta-store", "AMUL_TAAZA_500")
    assert safe_surplus(item) == 8


def test_releasing_reservation_restores_capacity():
    store = build_demo_store()
    reservation = store.reserve_inventory(
        supplier_id="gupta-store",
        buyer_id="sharma-kirana",
        sku="AMUL_TAAZA_500",
        quantity=5,
    )
    store.release_reservation(reservation.reservation_id)
    item = store.get_inventory_item("gupta-store", "AMUL_TAAZA_500")
    assert safe_surplus(item) == 13
