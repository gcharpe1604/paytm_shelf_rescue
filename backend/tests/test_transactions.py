from app.demo_data import build_demo_store
from app.payments import MockPaymentProvider, execute_rescue


def test_failed_payment_releases_reservation():
    store = build_demo_store()
    reservation = store.reserve_inventory(
        supplier_id="gupta-store",
        buyer_id="sharma-kirana",
        sku="AMUL_TAAZA_500",
        quantity=13,
    )
    provider = MockPaymentProvider(force_status="failed")
    final_reservation, payment = execute_rescue(
        store, provider, reservation.reservation_id
    )
    assert payment.status == "failed"
    assert final_reservation.status == "released"


def test_successful_payment_commits_exactly_once():
    store = build_demo_store()
    before = store.get_inventory_item("gupta-store", "AMUL_TAAZA_500").on_hand
    reservation = store.reserve_inventory(
        supplier_id="gupta-store",
        buyer_id="sharma-kirana",
        sku="AMUL_TAAZA_500",
        quantity=13,
    )
    provider = MockPaymentProvider(force_status="success")
    final_reservation, payment = execute_rescue(
        store, provider, reservation.reservation_id
    )
    assert payment.status == "success"
    assert final_reservation.status == "committed"
    after_first = store.get_inventory_item(
        "gupta-store", "AMUL_TAAZA_500"
    ).on_hand
    store.commit_reservation(reservation.reservation_id)
    after_second = store.get_inventory_item(
        "gupta-store", "AMUL_TAAZA_500"
    ).on_hand
    assert after_first == before - 13
    assert after_second == after_first
