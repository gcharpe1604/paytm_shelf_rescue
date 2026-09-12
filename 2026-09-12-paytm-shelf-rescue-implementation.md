# Paytm Shelf Rescue MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a repeatable 4-hour hackathon MVP where a Paytm merchant sees an imminent stockout, Phinite agents obtain supplier offers, a deterministic backend scores them, the merchant approves one rescue, inventory is reserved, payment is created, and the transfer commits safely.

**Architecture:** Phinite is the orchestration/agent layer; FastAPI owns facts, deterministic business rules, reservations, and payment-provider abstraction; React/Vite is a single merchant-facing dashboard. Controlled JSON/in-memory data is used for Paytm POS-like inventory and sales, with a replaceable `MockPaymentProvider`/`PaytmPaymentProvider` boundary.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, pytest, httpx/TestClient, React 18+, Vite, JavaScript, Phinite Agent Graph Studio. No database, Redis, Docker, ML framework, maps, or optimization library in the MVP.

**Spec:** `docs/superpowers/specs/2026-09-12-paytm-shelf-rescue-design.md`

## Global Constraints

- Solo build; effective implementation time is approximately 4 hours.
- The happy-path vertical slice is higher priority than all stretch features.
- Phinite decides/orchestrates; FastAPI owns facts and irreversible business operations.
- LLMs must not invent inventory, prices, payment state, or business-critical numeric facts.
- Use exactly three logical Phinite roles for MVP: Buyer Agent, reusable Supplier Agent, Rescue Agent.
- Controlled merchant/POS data must be clearly represented as demo data unless a real Paytm API is provided.
- Seller stock must be reserved before payment creation.
- Payment failure releases inventory reservation.
- Successful commit must be idempotent and must not double-decrement seller inventory.
- Default payment provider is `MockPaymentProvider`; Paytm staging is optional and must not block the build.
- React consists of one dashboard page with dashboard, searching, recommendation, success, and two required failure states.
- Do not add PostgreSQL, Redis, Docker orchestration, Kafka, authentication, real-time maps, StatsForecast, OR-Tools, ONDC/Beckn integration, or multi-SKU optimization before the core demo is stable.

---

## File Structure

Create the following focused structure:

```text
paytm-shelf-rescue/
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app composition only
│   │   ├── schemas.py              # Pydantic request/response/domain DTOs
│   │   ├── demo_data.py            # Controlled merchants, inventory, stockout facts
│   │   ├── inventory.py            # safe surplus + reservation/commit/release state
│   │   ├── rescue.py               # supplier discovery/check + deterministic scoring
│   │   ├── payments.py             # provider protocol + mock provider
│   │   └── routes.py               # HTTP/tool endpoints only
│   └── tests/
│       ├── test_inventory.py
│       ├── test_rescue.py
│       ├── test_transactions.py
│       └── test_api.py
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx                 # one-page state machine
│       ├── api.js                  # backend client only
│       └── styles.css              # all MVP styling
├── phinite/
│   ├── prompts/
│   │   ├── buyer-agent.md
│   │   ├── supplier-agent.md
│   │   └── rescue-agent.md
│   ├── tool-contracts/
│   │   └── tools.md
│   └── README.md
├── .env.example
├── README.md
└── docs/superpowers/...
```

The backend intentionally uses small modules by responsibility rather than repository/service/controller layering.

---

### Task 1: Backend domain model, demo fixtures, and safe-surplus rules

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/schemas.py`
- Create: `backend/app/demo_data.py`
- Create: `backend/app/inventory.py`
- Create: `backend/tests/test_inventory.py`

**Interfaces:**
- Produces: `Merchant`, `InventoryItem`, `StockoutEvent`, `SupplyOffer`, `Reservation`, `PaymentRecord` Pydantic models.
- Produces: `DemoStore` mutable in-memory state container loaded from controlled fixture data.
- Produces: `DemoStore.get_inventory_item(merchant_id: str, sku: str) -> InventoryItem`.
- Produces: `DemoStore.get_reservation(reservation_id: str) -> Reservation`.
- Produces: `safe_surplus(item: InventoryItem) -> int`.
- Produces: `DemoStore.reserve_inventory(...) -> Reservation`.
- Produces: `DemoStore.release_reservation(reservation_id: str) -> Reservation`.
- Produces: `DemoStore.commit_reservation(reservation_id: str) -> Reservation`.
- Later tasks consume these exact model and method names.

- [ ] **Step 1: Add the backend package configuration**

Create `backend/pyproject.toml`:

```toml
[project]
name = "paytm-shelf-rescue-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115,<1",
  "pydantic>=2.9,<3",
  "uvicorn[standard]>=0.30,<1",
]

[project.optional-dependencies]
dev = [
  "pytest>=8,<9",
  "httpx>=0.27,<1",
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 2: Install backend dependencies**

Run:

```bash
cd backend
python -m pip install -e ".[dev]"
```

Expected: FastAPI, Pydantic, uvicorn, pytest, and httpx install successfully.

- [ ] **Step 3: Write the failing inventory tests**

Create `backend/tests/test_inventory.py` with tests for these exact cases:

```python
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
```

- [ ] **Step 4: Run the tests and verify they fail**

Run:

```bash
cd backend
python -m pytest tests/test_inventory.py -v
```

Expected: collection/import failure because `app.demo_data` and `app.inventory` do not yet exist.

- [ ] **Step 5: Implement the minimal Pydantic models and controlled demo data**

Create `backend/app/schemas.py` with these exact fields:

```python
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
```

Create `backend/app/demo_data.py` with controlled merchants and inventory that exactly reproduce the approved scenario:

- Sharma Kirana: buyer, stockout event: stock 6, predicted demand 19, shortage 13, stockout 55 minutes, sales at risk ₹320.
- Gupta General Store: `on_hand=30`, `forecast_until_restock=11`, `safety_stock=4`, `reserved=2`, `rescue_price=19`, `eta_minutes=12`.
- ABC Wholesale: enough state to yield safe surplus >=80, `rescue_price=18`, `eta_minutes=42`.

Implement a `DemoStore` with dictionaries for merchants, inventory, reservations, and buyer incoming stock. Use `uuid.uuid4()` for reservation IDs. Implement `get_inventory_item()` and `get_reservation()` as strict lookup helpers that raise `KeyError` for unknown IDs.

- [ ] **Step 6: Implement safe surplus and reservation state transitions**

Create `backend/app/inventory.py`:

```python
from .schemas import InventoryItem


def safe_surplus(item: InventoryItem) -> int:
    return max(
        0,
        item.on_hand
        - item.forecast_until_restock
        - item.safety_stock
        - item.reserved,
    )
```

Implement `DemoStore.reserve_inventory()` so it:

1. fetches the supplier inventory item;
2. rejects `quantity <= 0`;
3. rejects quantity greater than current `safe_surplus`;
4. increments the inventory item's `reserved` count;
5. creates a `Reservation(status="reserved")` using the item's current rescue price;
6. stores and returns it.

Implement `release_reservation()` so only a currently `reserved` reservation changes to `released`, subtracting its quantity from `InventoryItem.reserved`. Repeated release returns the existing released reservation without changing state again.

Implement `commit_reservation()` so only a currently `reserved` reservation changes to `committed`, decrements `on_hand`, decrements `reserved`, and increments buyer incoming stock. Repeated commit returns the existing committed reservation without changing inventory again.

- [ ] **Step 7: Run the focused tests**

Run:

```bash
cd backend
python -m pytest tests/test_inventory.py -v
```

Expected: all inventory tests PASS.

- [ ] **Step 8: Commit Task 1**

```bash
git add backend
 git commit -m "feat: add demo inventory domain and reservation rules"
```

---

### Task 2: Rescue discovery, supplier offers, deterministic evaluation, and payment transaction safety

**Files:**
- Create: `backend/app/rescue.py`
- Create: `backend/app/payments.py`
- Create: `backend/tests/test_rescue.py`
- Create: `backend/tests/test_transactions.py`
- Modify: `backend/app/demo_data.py`

**Interfaces:**
- Consumes: `DemoStore`, `safe_surplus`, `StockoutEvent`, `SupplyOffer`, `ScoredOffer`, `PaymentRecord`.
- Produces: `detect_stockout(store, merchant_id, sku) -> StockoutEvent`.
- Produces: `discover_suppliers(store, buyer_id, sku) -> list[str]`.
- Produces: `check_supply(store, supplier_id, sku, requested_quantity, deadline_minutes) -> SupplyOffer`.
- Produces: `evaluate_offers(stockout, requested_quantity, offers) -> list[ScoredOffer]` sorted best-first.
- Produces: `PaymentProvider` protocol and `MockPaymentProvider`.
- Produces: `execute_rescue(store, payment_provider, reservation_id) -> tuple[Reservation, PaymentRecord]`.

- [ ] **Step 1: Write failing rescue tests**

Create `backend/tests/test_rescue.py`:

```python
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
    offers = [check_supply(store, sid, "AMUL_TAAZA_500", 13, 40) for sid in supplier_ids]
    ranked = evaluate_offers(event, 13, offers)
    assert ranked[0].supplier_id == "gupta-store"
    assert ranked[0].total_cost == 247
    assert ranked[1].supplier_id == "abc-wholesale"
```

- [ ] **Step 2: Write failing transaction tests**

Create `backend/tests/test_transactions.py`:

```python
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
    final_reservation, payment = execute_rescue(store, provider, reservation.reservation_id)
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
    final_reservation, payment = execute_rescue(store, provider, reservation.reservation_id)
    assert payment.status == "success"
    assert final_reservation.status == "committed"
    after_first = store.get_inventory_item("gupta-store", "AMUL_TAAZA_500").on_hand
    store.commit_reservation(reservation.reservation_id)
    after_second = store.get_inventory_item("gupta-store", "AMUL_TAAZA_500").on_hand
    assert after_first == before - 13
    assert after_second == after_first
```

- [ ] **Step 3: Run the tests and verify they fail**

```bash
cd backend
python -m pytest tests/test_rescue.py tests/test_transactions.py -v
```

Expected: import failures for `app.rescue` / `app.payments`.

- [ ] **Step 4: Implement stockout, discovery, and supply checking**

Create `backend/app/rescue.py`.

`detect_stockout()` must return only the controlled `StockoutEvent` stored for the buyer+SKU pair and raise a clear `KeyError` for unknown pairs.

`discover_suppliers()` must return supplier IDs in the controlled merchant dataset excluding the buyer and only where the SKU exists.

`check_supply()` must:

1. safely decline unknown SKU/supplier;
2. calculate current safe surplus;
3. offer `min(requested_quantity, safe_surplus)`;
4. decline if resulting quantity is zero;
5. return only offer-level fields; never return underlying inventory state;
6. keep the supplier's configured price, ETA, and fulfilment mode.

- [ ] **Step 5: Implement deterministic offer scoring**

Use this transparent MVP scoring model:

```python
time_buffer = max(0, stockout.stockout_in_minutes - offer.eta_minutes)
coverage_ratio = min(offer.quantity / requested_quantity, 1.0)
coverage_value = 30 * coverage_ratio
price_penalty = max(0, offer.unit_price - 18) * 5
late_penalty = max(0, offer.eta_minutes - stockout.stockout_in_minutes) * 2
score = time_buffer + coverage_value - price_penalty - late_penalty
```

Compute:

```python
total_cost = offer.quantity * offer.unit_price
expected_sales_protected = round(stockout.estimated_sales_at_risk * coverage_ratio) if offer.eta_minutes <= stockout.stockout_in_minutes else 0
eligible = offer.can_fulfil and offer.quantity > 0
```

Return only eligible offers sorted descending by score, then ascending by ETA, then ascending by total cost. The controlled scenario must rank Gupta ahead of ABC despite ABC's lower price: Gupta has a 43-minute stockout buffer versus ABC's 13-minute buffer, for only ₹13 additional cost.

- [ ] **Step 6: Implement the mock payment boundary and safe execution**

Create `backend/app/payments.py` with a `PaymentProvider` protocol exposing:

```python
class PaymentProvider(Protocol):
    def create_payment(
        self,
        buyer_id: str,
        seller_id: str,
        amount: int,
        reference: str,
    ) -> PaymentRecord: ...
```

Implement `MockPaymentProvider(force_status: Literal["success", "failed"] = "success")`. Return a unique `payment_id`, the provided values, configured status, and a fake local payment URL only for successful/pending-like demo display.

Implement `execute_rescue()` so it:

1. requires an existing `reserved` reservation;
2. creates payment using `reservation.total_amount`;
3. on success calls `store.commit_reservation()`;
4. on failure calls `store.release_reservation()`;
5. returns `(final_reservation, payment)`.

- [ ] **Step 7: Run rescue and transaction tests**

```bash
cd backend
python -m pytest tests/test_rescue.py tests/test_transactions.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit Task 2**

```bash
git add backend
 git commit -m "feat: add rescue scoring and safe payment execution"
```

---

### Task 3: FastAPI tool endpoints for Phinite and frontend integration

**Files:**
- Create: `backend/app/routes.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/test_api.py`
- Modify: `backend/app/schemas.py`
- Create: `.env.example`

**Interfaces:**
- Consumes all Task 1-2 domain functions.
- Produces HTTP endpoints with stable JSON contracts for Phinite and React.
- The MVP uses one process-global `DemoStore` plus `POST /api/reset` for repeatable demos.

- [ ] **Step 1: Add request schemas**

Add to `backend/app/schemas.py`:

```python
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
```

- [ ] **Step 2: Write failing API tests**

Create `backend/tests/test_api.py` using `fastapi.testclient.TestClient`:

```python
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
    response = client.post("/api/supply/check", json={
        "supplier_id": "gupta-store",
        "sku": "AMUL_TAAZA_500",
        "requested_quantity": 13,
        "deadline_minutes": 40,
    })
    assert response.status_code == 200
    assert response.json()["quantity"] == 13


def test_full_reservation_and_successful_execution():
    reserve = client.post("/api/reservations", json={
        "supplier_id": "gupta-store",
        "buyer_id": "sharma-kirana",
        "sku": "AMUL_TAAZA_500",
        "quantity": 13,
    })
    assert reserve.status_code == 200
    reservation_id = reserve.json()["reservation_id"]
    execute = client.post("/api/rescues/execute", json={
        "reservation_id": reservation_id,
        "force_payment_status": "success",
    })
    assert execute.status_code == 200
    assert execute.json()["reservation"]["status"] == "committed"
```

- [ ] **Step 3: Run and verify failure**

```bash
cd backend
python -m pytest tests/test_api.py -v
```

Expected: import failure for `app.main`.

- [ ] **Step 4: Implement API routes**

Create `backend/app/routes.py` with an `APIRouter(prefix="/api")` and these exact routes:

```text
POST /api/reset
GET  /api/dashboard/{merchant_id}
GET  /api/stockout/{merchant_id}/{sku}
GET  /api/suppliers/{buyer_id}/{sku}
POST /api/supply/check
POST /api/offers/evaluate
POST /api/reservations
POST /api/rescues/execute
```

`GET /api/dashboard/sharma-kirana` must return enough controlled fields for the frontend initial state: merchant name, today's sales `8420`, transactions `63`, SKU name, stock remaining `6`, shortage `13`, stockout horizon, and estimated sales at risk `320`.

`POST /api/reset` must replace the global store with a new `build_demo_store()` instance so the demo can be repeated without manual state repair.

Translate expected domain errors to HTTP 400 or 404 with concise detail. Do not swallow programming errors into HTTP 200 responses.

- [ ] **Step 5: Compose the FastAPI app and CORS**

Create `backend/app/main.py`:

- instantiate `FastAPI(title="Paytm Shelf Rescue API")`;
- add CORS for `http://localhost:5173`;
- include the router;
- add `GET /health` returning `{"status": "ok"}`.

Create `.env.example`:

```text
PAYMENT_PROVIDER=mock
VITE_API_BASE_URL=http://localhost:8000
```

- [ ] **Step 6: Run all backend tests**

```bash
cd backend
python -m pytest -q
```

Expected: all tests PASS.

- [ ] **Step 7: Smoke-run the API**

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

Verify manually:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/stockout/sharma-kirana/AMUL_TAAZA_500
```

Expected: health `ok` and shortage `13`.

- [ ] **Step 8: Commit Task 3**

```bash
git add backend .env.example
 git commit -m "feat: expose Shelf Rescue tool API"
```

---

### Task 4: Phinite prompt/tool contract assets

**Files:**
- Create: `phinite/prompts/buyer-agent.md`
- Create: `phinite/prompts/supplier-agent.md`
- Create: `phinite/prompts/rescue-agent.md`
- Create: `phinite/tool-contracts/tools.md`
- Create: `phinite/README.md`

**Interfaces:**
- Consumes Task 3 HTTP contracts.
- Produces exact prompts and tool mappings to configure manually in Phinite Agent Graph Studio.
- No custom agent framework code is added to the repository.

- [ ] **Step 1: Write the Buyer Agent prompt**

Create `phinite/prompts/buyer-agent.md` with these requirements:

```text
You represent the requesting Paytm merchant in an emergency shelf-rescue workflow.
Use only factual values supplied in the stockout event or tool results.
Never invent inventory, supplier, price, ETA, sales, or payment facts.
Convert a valid stockout event into one structured rescue requirement with:
buyer_id, sku, quantity, needed_within_minutes, max_unit_price.
For the MVP, quantity equals the backend-provided shortage. Keep the deadline no later than the projected stockout horizon.
Do not select a supplier and do not execute a payment.
Return JSON only when the graph expects structured output.
```

- [ ] **Step 2: Write the Supplier Agent prompt**

Create `phinite/prompts/supplier-agent.md`:

```text
You represent exactly one candidate supplier in the Paytm Shelf Rescue network.
Call the supply-check tool for the supplier_id provided by the graph.
Never reveal or infer total inventory, margins, purchase cost, safety stock, demand forecast, or any private supplier state.
Return only the offer-level fields returned by the tool: supplier_id, supplier_name, can_fulfil, quantity, unit_price, eta_minutes, fulfilment.
Never increase quantity or alter price/ETA returned by the tool.
If the tool declines or fails, return a safe decline; do not fabricate an offer.
```

- [ ] **Step 3: Write the Rescue Agent prompt**

Create `phinite/prompts/rescue-agent.md`:

```text
You explain and recommend among backend-scored Shelf Rescue offers.
The backend score and eligibility are authoritative. Never recalculate or override factual metrics.
Recommend the first/highest-ranked eligible offer supplied by the scoring tool.
Explain the trade-off using only supplied total_cost, eta_minutes, expected_sales_protected, quantity, and supplier name.
Keep the explanation to 2-3 sentences suitable for a small merchant.
Do not reserve inventory or create payment until explicit merchant approval is received.
If no eligible offer exists, return a clear no-rescue result.
```

- [ ] **Step 4: Document exact tool mappings**

Create `phinite/tool-contracts/tools.md` mapping:

```text
detect_stockout       -> GET  /api/stockout/{merchant_id}/{sku}
discover_suppliers    -> GET  /api/suppliers/{buyer_id}/{sku}
check_supply          -> POST /api/supply/check
evaluate_offers       -> POST /api/offers/evaluate
reserve_inventory     -> POST /api/reservations
execute_rescue        -> POST /api/rescues/execute
```

Include example request/response JSON copied from the API schemas, including the Gupta and ABC controlled offers.

- [ ] **Step 5: Document graph wiring**

Create `phinite/README.md` with this graph order:

```text
Trigger / dashboard rescue request
→ detect_stockout tool
→ Buyer Agent
→ discover_suppliers tool
→ Supplier Agent for Gupta
→ Supplier Agent for ABC
→ evaluate_offers tool
→ Rescue Agent
→ Human approval
→ reserve_inventory tool
→ execute_rescue tool
→ final success/failure output
```

State that sequential supplier calls are acceptable if parallel fan-out is awkward in the UI.

- [ ] **Step 6: Commit Task 4**

```bash
git add phinite
 git commit -m "docs: add Phinite agent and tool contracts"
```

---

### Task 5: React merchant dashboard and rescue state machine

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.jsx`
- Create: `frontend/src/api.js`
- Create: `frontend/src/App.jsx`
- Create: `frontend/src/styles.css`

**Interfaces:**
- Consumes Task 3 REST API.
- Produces a single-page merchant experience with states: `dashboard`, `searching`, `recommendation`, `executing`, `success`, `no_offer`, `payment_failed`.
- Until direct Phinite invocation from the UI is available, the frontend may call backend tool endpoints to render the deterministic demo while Phinite is shown separately as the real orchestration trace. Do not fake a claim that React is directly invoking Phinite if it is not.

- [ ] **Step 1: Scaffold the smallest Vite React app**

Use JavaScript, not TypeScript. `package.json` needs only:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@vitejs/plugin-react": "latest",
    "vite": "latest",
    "react": "latest",
    "react-dom": "latest"
  },
  "devDependencies": {}
}
```

Configure the React plugin in `vite.config.js`.

- [ ] **Step 2: Implement the API client**

Create `frontend/src/api.js` with functions:

```text
resetDemo()
getDashboard()
getStockout()
getSuppliers()
checkSupply(payload)
evaluateOffers(payload)
reserveInventory(payload)
executeRescue(payload)
```

Use `import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"`. For non-2xx responses, throw an `Error` using the backend `detail` where possible.

- [ ] **Step 3: Implement one-page state flow**

Create `frontend/src/App.jsx` with a compact state machine:

1. on load fetch `/api/dashboard/sharma-kirana`;
2. `Find Rescue Stock` sets `searching`;
3. fetch stockout + suppliers;
4. call supply check for each supplier;
5. call offer evaluation;
6. set `recommendation` with ranked offers;
7. `Accept Rescue` reserves ranked[0];
8. execute payment with forced success for happy path;
9. show success or payment failure.

Add a small `Reset Demo` control calling `/api/reset` and restoring `dashboard` state.

Do not add routing, global state libraries, authentication, or reusable design-system infrastructure.

- [ ] **Step 4: Build presentation-ready styling**

Create `frontend/src/styles.css` around these visual priorities:

- Paytm-inspired professional blue/white merchant dashboard, without copying proprietary assets.
- prominent inventory-risk card;
- clearly visible `₹320 sales at risk` before rescue;
- two supplier offer cards on recommendation state;
- visibly highlight Gupta as recommended while still showing ABC's cheaper price;
- explanation: `₹13 more, ~30 minutes faster, creating a much larger safety buffer before stockout`;
- success state emphasizing `Stockout Rescued`, quantity, payment created, ETA, and expected sales protected;
- responsive enough for a laptop projector.

- [ ] **Step 5: Verify frontend build**

```bash
cd frontend
npm install
npm run build
```

Expected: Vite production build succeeds with no compile errors.

- [ ] **Step 6: Run the full local demo**

Terminal 1:

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

Terminal 2:

```bash
cd frontend
npm run dev
```

Manually run the happy path at least three times using `Reset Demo`. Expected each run: Gupta recommendation → reservation → payment success → committed rescue, with no manual data repair.

- [ ] **Step 7: Commit Task 5**

```bash
git add frontend
 git commit -m "feat: add Shelf Rescue merchant dashboard"
```

---

### Task 6: Integration verification, failure paths, README, and demo freeze

**Files:**
- Modify: `backend/tests/test_api.py`
- Modify: `frontend/src/App.jsx`
- Modify: `README.md`
- Modify: `phinite/README.md`

**Interfaces:**
- Produces the final repeatable demo and documentation.
- No new product features in this task.

- [ ] **Step 1: Add API-level payment-failure verification**

Extend `backend/tests/test_api.py` with a flow that reserves Gupta stock, calls `/api/rescues/execute` with `force_payment_status="failed"`, asserts reservation status `released`, then successfully creates a fresh reservation for the same quantity to prove capacity was restored.

- [ ] **Step 2: Add no-offer UI handling**

In `App.jsx`, if `evaluateOffers()` returns an empty list, transition to `no_offer` and display:

```text
No rescue stock is available within the current constraints.
Try your regular distributor or retry with a wider deadline.
```

Do not auto-select a late/ineligible supplier.

- [ ] **Step 3: Add payment-failure UI handling**

If execution returns payment `failed`, transition to `payment_failed` and display:

```text
Payment failed. The seller reservation was released automatically, so no stock was locked.
```

- [ ] **Step 4: Run all verification commands**

Backend:

```bash
cd backend
python -m pytest -q
```

Frontend:

```bash
cd frontend
npm run build
```

Expected: all backend tests PASS and frontend build succeeds.

- [ ] **Step 5: Create the root README**

Document only what is true:

- product one-liner;
- architecture diagram in text;
- what is real vs controlled demo data;
- run commands;
- Phinite manual configuration path;
- happy-path demo steps;
- two failure paths;
- `PAYMENT_PROVIDER=mock` default;
- optional Paytm staging adapter as future/optional integration, not as completed production functionality unless it was actually implemented.

- [ ] **Step 6: Rehearse the exact judge demo**

Run three consecutive resets/happy paths and one payment-failure path. Confirm:

```text
Dashboard → Find Rescue Stock → Gupta/ABC offers → Gupta recommended → Accept Rescue → Stockout Rescued
```

Then open the Phinite graph/trace and show Buyer → Supplier → Rescue → approval/execution.

- [ ] **Step 7: Freeze features and commit**

```bash
git add README.md backend/tests/test_api.py frontend/src/App.jsx phinite/README.md
 git commit -m "chore: verify and document Shelf Rescue demo"
```

Do not add a stretch feature after this commit unless all verification still passes and at least 20 minutes remain before submission.

---

## Optional Stretch: Paytm staging payment provider

Attempt this only after Task 6 passes and only if credentials/documentation are immediately available.

**Files:**
- Modify: `backend/app/payments.py`
- Modify: `backend/app/main.py` or provider construction location
- Modify: `.env.example`
- Add focused provider tests with mocked HTTP; never make CI tests depend on live Paytm.

**Contract:** preserve `PaymentProvider.create_payment(...) -> PaymentRecord`. No caller changes are allowed.

Stop the attempt if integration is not working within 20 minutes. Revert to `PAYMENT_PROVIDER=mock` for demo reliability.

---

## Completion Checklist

The build is ready to submit only when all are true:

- [ ] Core backend tests pass.
- [ ] Gupta safe surplus is deterministically 13.
- [ ] Supplier offer cannot exceed safe surplus.
- [ ] Gupta ranks above cheaper/slower ABC in the approved scenario.
- [ ] Reservation occurs before payment execution.
- [ ] Payment failure releases reservation.
- [ ] Successful commit happens exactly once.
- [ ] `/api/reset` makes the happy path repeatable.
- [ ] React production build succeeds.
- [ ] Merchant sees ₹320 sales at risk and the recommendation trade-off.
- [ ] Success screen reports a rescued stockout and sales protected.
- [ ] Phinite Buyer/Supplier/Rescue trace can be shown to judges.
- [ ] Controlled POS/inventory data is never presented as a live Paytm POS integration.
