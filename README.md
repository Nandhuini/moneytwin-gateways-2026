# MoneyTwin

A digital twin of your spending. It learns how *you* spend, shows where money leaks (hidden fees, unrecovered
returns, autopay), predicts regret and overspending, and lets you test "what if" choices before you make them.
Built for GATEWAYS 2026, Domain 3 (Personal Productivity & Lifestyle). Demo data is fully synthetic.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m moneytwin.synthetic                         # optional: regenerates data/*.csv (app does it if missing)
streamlit run app.py
```

## Environment variables (all optional)

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Enables LLM-written advice. Without it the advisor uses a built-in explanation. |
| `MONEYTWIN_LLM_MODEL` | Model name for the advisor (default `claude-sonnet-5-5`). |
| `MONEYTWIN_DATA_DIR` | Where demo data and `twin_profile.json` live (default `./data`). |

Copy `.env.example` to `.env` for local use. Never commit `.env`. Only summary numbers are sent to the LLM, never raw transactions.
## Live Demo

🌐 https://moneytwin-gateways-2026.onrender.com/

## Deploy (Render)

MoneyTwin is deployed on Render.

For local development:

```bash
streamlit run app.py

## Upload format

Transactions CSV (required): `order_id, date, merchant, total`. Optional: `time, category, item_amount, fees` or
`delivery_fee, platform_fee, handling_fee, surge_fee`. Returns CSV: `order_id, return_date, refund_amount, refund_status, refund_date`.
Autopay CSV: `merchant, amount, day_of_month, cycle, start_date`. See `data/` for examples.

## How it maps to the Round 1 architecture

| Round 1 component | Code |
|---|---|
| Consent & Intake Layer | `moneytwin/consent.py`, `views/privacy.py` |
| Cleaning & Categorisation Agent | `moneytwin/cleaning.py` |
| Leak Detector Agent | `moneytwin/leaks.py` |
| Behaviour Pattern Agent | `moneytwin/behaviour.py` |
| Prediction Agent | `moneytwin/prediction.py`, `moneytwin/forecast.py` |
| Twin Profile Store | `moneytwin/twin_store.py` |
| Scenario Simulator | `moneytwin/simulator.py` |
| Advisor Agent (LLM + fallback) | `moneytwin/advisor.py` |
| Dashboard and feedback loop | `app.py`, `moneytwin/views/` |

## Tests

```bash
python -m unittest discover -s tests -t .     # or: python -m pytest -q
```

## Demo script (3 minutes)

1. **Overview**: fees add up to about a fifth of food-delivery prices; note the budget line.
2. **Money leaks**: pending refunds, one orphan return left out instead of guessed, a new Coursera autopay and an undeclared YouTube renewal.
3. **Behaviour**: heatmap shows early-month and late-night peaks; try the regret predictor on a Rs. 999 late-night sale purchase.
4. **What-if**: type "cook 3 nights and save Rs. 1000"; no single change reaches the goal but the combined plan does.
5. Press **Ignore**: the twin lowers its trust in that advice and the numbers change. **Privacy**: switch off Food Delivery and watch every chart update.

## Known limitations

- The overspend-risk estimate is statistical (history for the same days of the month), not a trained model. Only the return-probability model uses scikit-learn.
- The simulator covers the rest of the current month and adds the effect of each change together, so the combined plan is approximate.
- Feedback adjusts a few personal factors by fixed steps; it does not retrain models.
- Trained on small synthetic data, so probabilities are illustrative.
