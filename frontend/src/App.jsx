import { useEffect, useState } from "react";

import {
  executeRescue,
  getDashboard,
  getRecommendation,
  getStockout,
  reserveInventory,
  resetDemo,
} from "./api.js";

const BUYER_ID = "sharma-kirana";
const SKU = "AMUL_TAAZA_500";
const SEARCH_STEPS = [
  "Sending rescue request",
  "Buyer agent defining need",
  "Supplier agents checking stock",
  "Rescue agent ranking offers",
];

const money = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

function Metric({ label, value, note, accent }) {
  return (
    <article className={`metric ${accent ? "metric--accent" : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  );
}

function SearchProgress({ activeStep }) {
  return (
    <section className="workflow-card" aria-live="polite">
      <div className="radar" aria-hidden="true">
        <span />
      </div>
      <p className="eyebrow">Rescue network</p>
      <h2>Finding the fastest safe match</h2>
      <p className="workflow-copy">
        Phinite is coordinating the buyer, supplier, and rescue agents. Supplier
        inventory stays private.
      </p>
      <ol className="workflow-steps">
        {SEARCH_STEPS.map((step, index) => (
          <li
            className={
              index < activeStep
                ? "is-complete"
                : index === activeStep
                  ? "is-active"
                  : ""
            }
            key={step}
          >
            <span aria-hidden="true">{index < activeStep ? "✓" : index + 1}</span>
            {step}
          </li>
        ))}
      </ol>
    </section>
  );
}

function OfferCard({ offer, recommended }) {
  return (
    <article className={`offer-card ${recommended ? "is-recommended" : ""}`}>
      <div className="offer-heading">
        <div>
          <p className="eyebrow">{recommended ? "Best rescue match" : "Alternative"}</p>
          <h3>{offer.supplier_name}</h3>
        </div>
        <div className="offer-badges">
          {recommended && <span className="recommendation-badge">Recommended</span>}
          <span className="offer-score">Score {offer.score}</span>
        </div>
      </div>
      <div className="offer-price">
        <strong>{money.format(offer.total_cost)}</strong>
        <span>{money.format(offer.unit_price)} / unit</span>
      </div>
      <dl className="offer-details">
        <div>
          <dt>Quantity</dt>
          <dd>{offer.quantity} units</dd>
        </div>
        <div>
          <dt>Pickup ETA</dt>
          <dd>{offer.eta_minutes} min</dd>
        </div>
        <div>
          <dt>Sales protected</dt>
          <dd>{money.format(offer.expected_sales_protected)}</dd>
        </div>
        <div>
          <dt>Fulfilment</dt>
          <dd>{offer.fulfilment}</dd>
        </div>
      </dl>
    </article>
  );
}

function ErrorState({ error, onReset, resetting }) {
  return (
    <section className="state-card state-card--error" role="alert">
      <div className="state-icon" aria-hidden="true">!</div>
      <p className="eyebrow">Action needed</p>
      <h2>{error.title}</h2>
      <p>{error.message}</p>
      <button className="button button--secondary" disabled={resetting} onClick={onReset}>
        {resetting ? "Resetting…" : "Reset demo"}
      </button>
    </section>
  );
}

export default function App() {
  const [view, setView] = useState("loading");
  const [dashboard, setDashboard] = useState(null);
  const [stockout, setStockout] = useState(null);
  const [offers, setOffers] = useState([]);
  const [recommendation, setRecommendation] = useState(null);
  const [selectedOffer, setSelectedOffer] = useState(null);
  const [result, setResult] = useState(null);
  const [activeStep, setActiveStep] = useState(0);
  const [error, setError] = useState(null);
  const [resetting, setResetting] = useState(false);

  async function loadInitial() {
    const [dashboardData, stockoutData] = await Promise.all([
      getDashboard(),
      getStockout(),
    ]);
    setDashboard(dashboardData);
    setStockout(stockoutData);
    setView("dashboard");
  }

  useEffect(() => {
    let active = true;
    Promise.all([getDashboard(), getStockout()])
      .then(([dashboardData, stockoutData]) => {
        if (!active) return;
        setDashboard(dashboardData);
        setStockout(stockoutData);
        setView("dashboard");
      })
      .catch((requestError) => {
        if (!active) return;
        setError({
          title: "Dashboard unavailable",
          message: requestError.message,
        });
        setView("error");
      });
    return () => {
      active = false;
    };
  }, []);

  async function handleSearch() {
    setError(null);
    setActiveStep(0);
    setView("searching");
    const progressTimer = window.setInterval(
      () => setActiveStep((step) => Math.min(step + 1, SEARCH_STEPS.length - 1)),
      900,
    );
    try {
      const response = await getRecommendation({
        merchant_id: BUYER_ID,
        sku: SKU,
      });
      if (response.evaluated_offers.length === 0) {
        setView("no_offer");
        return;
      }
      const selected = response.evaluated_offers.find(
        (offer) => offer.supplier_id === response.top_supplier_id,
      );
      if (!selected) {
        throw new Error("Phinite did not return its selected supplier offer.");
      }
      setRecommendation(response);
      setOffers(response.evaluated_offers);
      setSelectedOffer(selected);
      setView("recommendation");
    } catch (requestError) {
      setError({
        title: "Phinite recommendation unavailable",
        message: requestError.message,
      });
      setView("error");
    } finally {
      window.clearInterval(progressTimer);
    }
  }

  async function handleAccept() {
    setView("executing");
    let reservation;
    try {
      reservation = await reserveInventory({
        supplier_id: recommendation.top_supplier_id,
        buyer_id: BUYER_ID,
        sku: SKU,
        quantity: recommendation.top_quantity,
      });
    } catch (requestError) {
      setError({
        title: "Stock could not be reserved",
        message: requestError.message,
      });
      setView("error");
      return;
    }

    try {
      const execution = await executeRescue({
        reservation_id: reservation.reservation_id,
      });
      if (
        execution.payment.status !== "success" ||
        execution.reservation.status !== "committed"
      ) {
        setError({
          title: "Payment was not completed",
          message:
            execution.reservation.status === "released"
              ? "The payment failed and the supplier reservation was released automatically."
              : "The rescue was not committed. No success state has been recorded.",
        });
        setView("error");
        return;
      }
      setResult(execution);
      setView("success");
    } catch (requestError) {
      setError({
        title: "Rescue execution failed",
        message: requestError.message,
      });
      setView("error");
    }
  }

  async function handleReset() {
    setResetting(true);
    try {
      await resetDemo();
      setOffers([]);
      setRecommendation(null);
      setSelectedOffer(null);
      setResult(null);
      setError(null);
      await loadInitial();
    } catch (requestError) {
      setError({ title: "Demo reset failed", message: requestError.message });
      setView("error");
    } finally {
      setResetting(false);
    }
  }

  const busy = view === "searching" || view === "executing" || resetting;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">SR</span>
          <div>
            <strong>Paytm Shelf Rescue</strong>
            <span>Merchant operations</span>
          </div>
        </div>
        <div className="merchant-status">
          <span className="status-dot" aria-hidden="true" />
          <div>
            <strong>{dashboard?.merchant_name || "Sharma Kirana"}</strong>
            <span>Operations active</span>
          </div>
        </div>
      </header>

      <main>
        <div className="page-heading">
          <div>
            <p className="eyebrow">Today · Store overview</p>
            <h1>Good morning, Sharma Kirana</h1>
            <p>One inventory risk needs attention before the next demand window.</p>
          </div>
          <button
            className="reset-button"
            disabled={busy || view === "loading"}
            onClick={handleReset}
          >
            {resetting ? "Resetting…" : "Reset demo"}
          </button>
        </div>

        {dashboard && (
          <section className="metrics" aria-label="Today's store summary">
            <Metric label="Today's sales" value={money.format(dashboard.today_sales)} note="Live demo snapshot" />
            <Metric label="Transactions" value={dashboard.transactions} note="Completed today" />
            <Metric
              accent
              label="Rescue window"
              value={`${stockout?.stockout_in_minutes ?? dashboard.stockout_in_minutes} min`}
              note="Before projected stockout"
            />
          </section>
        )}

        {view === "loading" && (
          <section className="loading-card" aria-live="polite">
            <span className="loading-line" />
            <span className="loading-line loading-line--short" />
            <p>Loading merchant inventory…</p>
          </section>
        )}

        {view === "dashboard" && dashboard && stockout && (
          <section className="risk-card">
            <div className="risk-main">
              <div className="risk-title-row">
                <span className="risk-label">Inventory risk · Action required</span>
                <span className="risk-timer">Stockout in {stockout.stockout_in_minutes} min</span>
              </div>
              <p className="eyebrow">Fast-moving dairy</p>
              <h2>{dashboard.sku_name}</h2>
              <p className="risk-lead">
                Only <strong>{stockout.current_stock} milk units remain.</strong> Demand is
                expected to exceed available stock before replenishment.
              </p>
              <dl className="risk-facts">
                <div>
                  <dt>Current stock</dt>
                  <dd>{stockout.current_stock}</dd>
                </div>
                <div>
                  <dt>Predicted demand</dt>
                  <dd>{stockout.predicted_demand}</dd>
                </div>
                <div className="risk-fact--warning">
                  <dt>Predicted shortage</dt>
                  <dd>{stockout.shortage} units</dd>
                </div>
              </dl>
            </div>
            <aside className="risk-action">
              <div>
                <span>Estimated sales at risk</span>
                <strong>{money.format(stockout.estimated_sales_at_risk)}</strong>
                <p>Protect this demand with nearby safe-surplus inventory.</p>
              </div>
              <button className="button button--primary" onClick={handleSearch}>
                Find Rescue Stock
                <span aria-hidden="true">→</span>
              </button>
            </aside>
          </section>
        )}

        {view === "searching" && <SearchProgress activeStep={activeStep} />}

        {view === "recommendation" && selectedOffer && recommendation && (
          <section className="recommendation-section">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Phinite recommendation</p>
                <h2>Rescue stock found</h2>
                <p>Supplier agents returned eligible offers. Phinite selected the safest match.</p>
              </div>
              <div className="window-pill">
                <span>{recommendation.deadline_minutes} min</span>
                <small>stockout window</small>
              </div>
            </div>

            <div className="offer-grid">
              {offers.map((offer) => (
                <OfferCard
                  key={offer.supplier_id}
                  offer={offer}
                  recommended={offer.supplier_id === recommendation.top_supplier_id}
                />
              ))}
            </div>

            <div className="decision-bar">
              <div className="decision-copy">
                <span className="decision-icon" aria-hidden="true">✓</span>
                <p>
                  <strong>{selectedOffer.supplier_name} is the safest match.</strong>
                  {` ${recommendation.recommendation_explanation}`}
                </p>
              </div>
              <button className="button button--primary" onClick={handleAccept}>
                Accept Rescue
                <span aria-hidden="true">→</span>
              </button>
            </div>
          </section>
        )}

        {view === "executing" && (
          <section className="workflow-card" aria-live="polite">
            <div className="payment-loader" aria-hidden="true" />
            <p className="eyebrow">Secure execution</p>
            <h2>Reservation confirmed. Creating payment…</h2>
            <p className="workflow-copy">
              Stock is reserved before payment and committed only after success.
            </p>
          </section>
        )}

        {view === "success" && result && selectedOffer && (
          <section className="success-card" aria-live="polite">
            <div className="success-mark" aria-hidden="true">✓</div>
            <p className="eyebrow">Rescue complete</p>
            <h2>STOCKOUT RESCUED</h2>
            <p className="success-lead">
              {result.reservation.quantity} units are secured from {selectedOffer.supplier_name}
              {" "}and expected in {selectedOffer.eta_minutes} minutes.
            </p>
            <dl className="success-details">
              <div>
                <dt>Total amount</dt>
                <dd>{money.format(result.reservation.total_amount)}</dd>
              </div>
              <div>
                <dt>Sales protected</dt>
                <dd>{money.format(selectedOffer.expected_sales_protected)}</dd>
              </div>
              <div>
                <dt>Payment status</dt>
                <dd className="success-status">{result.payment.status}</dd>
              </div>
              <div>
                <dt>Transaction reference</dt>
                <dd className="reference">{result.payment.reference}</dd>
              </div>
            </dl>
            <button className="button button--secondary" disabled={resetting} onClick={handleReset}>
              {resetting ? "Resetting…" : "Reset demo"}
            </button>
          </section>
        )}

        {view === "no_offer" && (
          <section className="state-card" role="status">
            <div className="state-icon" aria-hidden="true">×</div>
            <p className="eyebrow">No eligible match</p>
            <h2>No rescue stock is available within the current constraints.</h2>
            <p>Try your regular distributor or retry with a wider deadline.</p>
            <button className="button button--secondary" onClick={handleReset}>Reset demo</button>
          </section>
        )}

        {view === "error" && error && (
          <ErrorState error={error} onReset={handleReset} resetting={resetting} />
        )}
      </main>

      <footer>
        <span>Controlled hackathon demo data</span>
        <span>Payments use the mock provider</span>
      </footer>
    </div>
  );
}
