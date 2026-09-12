import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.phinite import get_phinite_http_client


client = TestClient(app)

RECOMMENDATION = {
    "workflow_id": "workflow-123",
    "merchant_id": "sharma-kirana",
    "sku": "AMUL_TAAZA_500",
    "supplier_ids": ["gupta-store", "abc-wholesale"],
    "requested_quantity": 13,
    "deadline_minutes": 55,
    "evaluated_offers": [
        {
            "supplier_id": "gupta-store",
            "supplier_name": "Gupta General Store",
            "can_fulfil": True,
            "quantity": 13,
            "unit_price": 19,
            "eta_minutes": 12,
            "fulfilment": "pickup",
            "total_cost": 247,
            "expected_sales_protected": 320,
            "score": 68,
            "eligible": True,
        },
        {
            "supplier_id": "abc-wholesale",
            "supplier_name": "ABC Wholesale",
            "can_fulfil": True,
            "quantity": 13,
            "unit_price": 18,
            "eta_minutes": 42,
            "fulfilment": "pickup",
            "total_cost": 234,
            "expected_sales_protected": 320,
            "score": 43,
            "eligible": True,
        },
    ],
    "top_supplier_id": "gupta-store",
    "top_quantity": 13,
    "top_total_cost": 247,
    "top_eta_minutes": 12,
    "top_expected_sales_protected": 320,
    "top_score": 68,
    "recommendation_explanation": "Gupta protects the same sales with a 30-minute faster pickup.",
}


@pytest.fixture(autouse=True)
def phinite_environment(monkeypatch):
    monkeypatch.setenv("PHINITE_TRIGGER_URL", "https://phinite.test/trigger")
    monkeypatch.setenv("PHINITE_API_KEY", "test-secret")
    yield
    app.dependency_overrides.pop(get_phinite_http_client, None)


def use_phinite_response(payload: dict, status_code: int = 200) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-secret"
        assert json.loads(request.content) == {
            "message": "Find the best shelf rescue recommendation",
            "user_variables": {
                "merchant_id": "sharma-kirana",
                "sku": "AMUL_TAAZA_500",
            },
        }
        return httpx.Response(status_code, json=payload)

    async def override_client():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            yield http_client

    app.dependency_overrides[get_phinite_http_client] = override_client


def test_recommendations_endpoint_normalizes_completed_phinite_response():
    use_phinite_response(
        {
            "workflow_id": "outer-workflow-123",
            "response": RECOMMENDATION,
            "status": "completed",
            "requires_input": False,
            "error": None,
        }
    )

    response = client.post(
        "/api/recommendations",
        json={"merchant_id": "sharma-kirana", "sku": "AMUL_TAAZA_500"},
    )

    assert response.status_code == 200
    expected = RECOMMENDATION.copy()
    expected.pop("supplier_ids")
    assert response.json() == expected


def test_recommendations_endpoint_rejects_non_2xx_phinite_response():
    use_phinite_response({"detail": "provider failure"}, status_code=500)

    response = client.post(
        "/api/recommendations",
        json={"merchant_id": "sharma-kirana", "sku": "AMUL_TAAZA_500"},
    )

    assert response.status_code == 502
    assert "phinite" in response.json()["detail"].lower()


@pytest.mark.parametrize(
    "phinite_payload",
    [
        {"status": "running", "error": None, "response": RECOMMENDATION},
        {"status": "completed", "error": "agent failed", "response": RECOMMENDATION},
        {"status": "completed", "error": None},
        {
            "status": "completed",
            "error": None,
            "response": {"workflow_id": "incomplete"},
        },
    ],
)
def test_recommendations_endpoint_rejects_invalid_workflow_results(
    phinite_payload: dict,
):
    use_phinite_response(phinite_payload)

    response = client.post(
        "/api/recommendations",
        json={"merchant_id": "sharma-kirana", "sku": "AMUL_TAAZA_500"},
    )

    assert response.status_code == 502


def test_recommendations_endpoint_requires_server_configuration(monkeypatch):
    monkeypatch.delenv("PHINITE_TRIGGER_URL")
    monkeypatch.delenv("PHINITE_API_KEY")
    use_phinite_response({})

    response = client.post(
        "/api/recommendations",
        json={"merchant_id": "sharma-kirana", "sku": "AMUL_TAAZA_500"},
    )

    assert response.status_code == 503
