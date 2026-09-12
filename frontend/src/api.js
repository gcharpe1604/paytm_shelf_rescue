const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"
).replace(/\/$/, "");

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    });
  } catch {
    throw new Error(
      "Could not reach the Shelf Rescue API. Check that the backend is running.",
    );
  }

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(body?.detail || `Request failed with status ${response.status}`);
  }
  return body;
}

export function resetDemo() {
  return request("/api/reset", { method: "POST" });
}

export function getDashboard() {
  return request("/api/dashboard/sharma-kirana");
}

export function getStockout() {
  return request("/api/stockout/sharma-kirana/AMUL_TAAZA_500");
}

export function getSuppliers(buyerId, sku) {
  return request(`/api/suppliers/${buyerId}/${sku}`);
}

export function checkSupply(payload) {
  return request("/api/supply/check", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function evaluateOffers(payload) {
  return request("/api/offers/evaluate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function reserveInventory(payload) {
  return request("/api/reservations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function executeRescue(payload) {
  return request("/api/rescues/execute", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
