from app.demo_data import build_demo_store
from app.rescue import check_supply, detect_stockout, discover_suppliers, evaluate_offers


def test_detect_stockout_returns_controlled_sharma_event():
    event = detect_stockout(build_demo_store(), "sharma-kirana", "AMUL_TAAZA_500")
    assert event.shortage == 13
    assert event.stockout_in_minutes == 55
    assert event.estimated_sales_at_risk == 320


def test_gupta_offer_never_exposes_more_than_safe_surplus():
    store = build_demo_store()
    offer = check_supply(store, "gupta-store", "AMUL_TAAZA_500", 20, 40)
    assert offer.can_fulfil is True
    assert offer.quantity == 13
    assert offer.unit_price == 19


def test_supplier_without_stock_returns_decline():
    store = build_demo_store()
    offer = check_supply(store, "gupta-store", "UNKNOWN_SKU", 10, 40)
    assert offer.can_fulfil is False
    assert offer.quantity == 0


def test_gupta_beats_cheaper_but_late_abc_offer():
    store = build_demo_store()
    event = detect_stockout(store, "sharma-kirana", "AMUL_TAAZA_500")
    supplier_ids = discover_suppliers(store, "sharma-kirana", "AMUL_TAAZA_500")
    offers = [
        check_supply(store, supplier_id, "AMUL_TAAZA_500", 13, 40)
        for supplier_id in supplier_ids
    ]
    ranked = evaluate_offers(event, 13, offers)
    assert ranked[0].supplier_id == "gupta-store"
    assert ranked[0].total_cost == 247
    assert ranked[1].supplier_id == "abc-wholesale"
