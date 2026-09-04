# Payment Resolver Engine

Track 3: AI Revenue Recovery — Razorpay AI Buildathon 2026

## Problem

Razorpay already reconciles bank and gateway internally (late authorization, webhook
retries). What it cannot see is whether the *merchant's own system* correctly reflected
that resolved status — evidenced by a real production bug where a successful Razorpay
renewal never updated a WooCommerce order from pending to completed.

This is a batch reconciliation engine that compares Razorpay's resolved payment status
against the merchant's own order record for a batch of transactions, detects drift,
takes a direction-aware bounded recovery action, and logs every decision to an audit
trail.

Scope is deliberately a single batch run of 50+ records — no live webhook listener, no
concurrency handling, no time-decay windows. That scoping is what makes the numbers
below real and measured rather than merely designed.

## Architecture

```
resolver/
  data_generator.py   synthetic orders_batch: 35 clean matches, 8 safe-direction
                       drift, 4 risky-direction drift, 2 reversal events, 1 unmapped code
  lookup.py            error_code_lookup: raw razorpay_status -> SUCCESS/FAILED/PENDING
  correlate.py          correlation: payment_id must map to exactly one order_id + amount
  compare.py            pure drift comparison (MATCH / DRIFT_SAFE / DRIFT_RISKY / DRIFT_OTHER)
  actions.py             direction-aware recovery decision (pure, no I/O)
  classifier.py           Groq LLM call — classifies an unmapped status code only
  db.py                    SQLite: orders_batch (input) + audit_log (output)
  pipeline.py               orchestrates correlate -> reversal check -> unmapped check
                             -> compare -> act -> log, in chronological order

run_reconciliation.py   entry point: generate batch, run pipeline, print summary
app.py                  Streamlit dashboard, reads audit_log directly from SQLite
tests/                  unit tests for correlation + drift comparison (pure Python)
```

Processing logic per record, in order:

1. **Correlate** — does `razorpay_payment_id` map to exactly one `order_id` with a
   matching `amount` across the whole batch? If not, log `CORRELATION_FAILED` and skip.
   This always runs before any status comparison.
2. **Reversal check** — if the event is `SETTLEMENT_REVERSED` and this order was
   already resolved earlier in the batch, log `DISPUTED`. Never dropped or ignored.
3. **Unmapped code check** — if `razorpay_status` isn't in `error_code_lookup`, call the
   Groq classifier once to propose a category, log `UNCONFIRMED_CLASSIFICATION`. The
   proposal is never auto-executed.
4. **Compare status**:
   - Match → `VERIFIED_IN_SYNC`, no action
   - Safe-direction drift (Razorpay=SUCCESS, merchant=PENDING/FAILED) → **auto-correct**
     the merchant status, log `AUTO_CORRECTED`
   - Risky-direction drift (Razorpay=FAILED, merchant=SUCCESS), or any other mismatch →
     **flag only**, log `FLAGGED_FOR_REVIEW` — never auto-corrected, regardless of
     confidence
5. **Idempotency** — `audit_log.record_id` is a primary key; re-running the pipeline
   against an already-processed batch does not duplicate rows.

All comparison, correction, and gating logic is deterministic Python. The only LLM call
anywhere in the system is the unmapped-code classifier, and its output is always logged
as `UNCONFIRMED`, never acted on automatically.

## Setup

```bash
pip install -r requirements.txt
```

Set a Groq API key (needed once per run, for the single unmapped status code in the
batch):

```bash
cp .env.example .env
# then edit .env and set GROQ_API_KEY=your_key
```

## Running it

Generate the batch and run the full reconciliation pipeline:

```bash
python run_reconciliation.py
```

This regenerates `data/payment_resolver.db` from scratch, seeds `orders_batch`,
processes every record, and prints a summary block with real counts from that run.

Then view the dashboard, reading directly from the same SQLite database:

```bash
streamlit run app.py
```

(If `streamlit` isn't on your PATH, use `python -m streamlit run app.py`.)

Run the unit tests for the correlation and drift comparison logic (pure Python, no
external calls):

```bash
python -m unittest discover -s tests
```
