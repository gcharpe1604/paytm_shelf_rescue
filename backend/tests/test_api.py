from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def setup_function():
    client.post("/api/reset")


def test_stockout_endpoint():
    response = client.get("/api/stockout/sharma-kirana/AMUL_TAAZA_500")
    assert response.status_code == 200
    assert response.json()["shortage"] == 13


def test_supplier_offer_endpoint():
    response = client.post(
        "/api/supply/check",
        json={
            "supplier_id": "gupta-store",
            "sku": "AMUL_TAAZA_500",
            "requested_quantity": 13,
            "deadline_minutes": 40,
        },
    )
    assert response.status_code == 200
    assert response.json()["quantity"] == 13


def test_full_reservation_and_successful_execution():
    reserve = client.post(
        "/api/reservations",
        json={
            "supplier_id": "gupta-store",
            "buyer_id": "sharma-kirana",
            "sku": "AMUL_TAAZA_500",
            "quantity": 13,
        },
    )
    assert reserve.status_code == 200
    reservation_id = reserve.json()["reservation_id"]
    execute = client.post(
        "/api/rescues/execute",
        json={
            "reservation_id": reservation_id,
            "force_payment_status": "success",
        },
    )
    assert execute.status_code == 200
    assert execute.json()["reservation"]["status"] == "committed"
