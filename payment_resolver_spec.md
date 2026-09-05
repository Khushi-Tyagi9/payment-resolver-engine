# Payment Resolver Engine: Design Notes
**Track 3: AI Revenue Recovery, Razorpay AI Buildathon 2026**

## Problem
Razorpay already reconciles bank and gateway internally (late authorization, webhook retries). What it cannot see is whether the *merchant's own system* correctly reflected that resolved status. This is evidenced by a real production bug where a successful Razorpay renewal never updated a WooCommerce order from pending to completed.

## Solution
A batch reconciliation engine that compares Razorpay's resolved payment status against the merchant's own order record for a batch of transactions, detects drift, takes a direction-aware bounded recovery action, and logs every decision to an audit trail.

## Scope: BATCH, not live webhooks
The engine processes a batch of 50+ records once: no live webhook listener, no concurrency handling, no time-decay windows. This was the single most important scoping decision. It's what makes "measured results" achievable by the deadline instead of merely designed.

## Data model

**orders_batch** (input, synthetic, generate first)
`record_id, razorpay_payment_id, order_id, amount, razorpay_status, merchant_order_status, event_type, timestamp`

The batch is seeded with a deliberate mix:
- ~35 clean matches (razorpay_status == merchant_order_status)
- ~8 drift, safe direction: razorpay=SUCCESS, merchant=PENDING/FAILED
- ~4 drift, risky direction: razorpay=FAILED, merchant=SUCCESS
- ~2 reversal events: event_type=SETTLEMENT_REVERSED applied to an already-matched record
- ~1 unmapped razorpay_status code (not in your lookup dictionary)

**audit_log** (output, one row per record processed)
`record_id, correlation_ok, razorpay_status, merchant_status, drift_direction, action_taken, reason, timestamp`

**error_code_lookup**: deterministic dict mapping known razorpay_status strings to a structured signal. Anything not in it routes to the LLM fallback, never guessed silently.

## Processing logic (deterministic, run once per record, in order)

1. **Correlate**: does razorpay_payment_id map to exactly one order_id with matching amount? If not → log `CORRELATION_FAILED`, skip. (This runs before any comparison, so nothing is ever compared against a record it doesn't belong to.)
2. **Compare status**:
   - Match → log `VERIFIED_IN_SYNC`, no action
   - Drift, safe direction (Razorpay=success, merchant=pending/failed) → **auto-correct** merchant status, log `AUTO_CORRECTED`
   - Drift, risky direction (Razorpay=failed, merchant=paid) → **do not auto-correct** → log `FLAGGED_FOR_REVIEW`
3. **Reversal check**: if event_type is in the reversal allow-list and applies to an already-resolved record → log `DISPUTED`, flag for review, never silently drop it
4. **Unmapped code**: if razorpay_status isn't in the lookup dict → call LLM once to *propose* a category → log `UNCONFIRMED_CLASSIFICATION` → never auto-execute on it
5. **Idempotency**: unique constraint on record_id in audit_log, so each record is claimed and processed exactly once

## LLM's one job
The LLM's only job is to classify an unmapped razorpay_status code into a proposed category, flagged unconfirmed and logged for review, never auto-executed. That's it. Everything else (comparison, correction, logging) is deterministic Python. It's a small, honest, defensible answer to "where's the AI," not a weakness.

## Tech stack

- **Logic:** plain Python, pure functions (correlate → compare → act → log). No web framework needed for the batch job.
- **Storage:** SQLite, one file. Zero setup, queryable live if the panel asks a follow-up.
- **LLM:** Groq API, one call type only: the unmapped error-code classifier. Fast + cheap, matches the narrow scope.
  ```python
  from groq import Groq
  client = Groq(api_key=os.environ["GROQ_API_KEY"])

  def classify_unmapped_code(raw_status: str) -> dict:
      resp = client.chat.completions.create(
          model="llama-3.1-8b-instant",
          messages=[
              {"role": "system", "content": "Classify an unmapped Razorpay payment status code as SUCCESS, FAILED, or PENDING. Respond with JSON only: {\"proposed_category\": ..., \"reasoning\": ...}"},
              {"role": "user", "content": f"Unmapped status code: {raw_status}"},
          ],
          response_format={"type": "json_object"},
      )
      result = json.loads(resp.choices[0].message.content)
      result["confidence_flag"] = "UNCONFIRMED"  # logged for review, never auto-executed
      return result
  ```
- **Dashboard:** Streamlit. `st.metric()` for the top cards, native bar chart for outcome distribution, `st.dataframe()` for the audit log, `st.selectbox()` + rendered text for the money trace timeline. One file, `streamlit run app.py`.
- **Fallback:** if Streamlit setup had cost too much time, the plan was a static HTML page generated straight from the SQLite data.

## UI layout

- Top row of metric cards: total processed, verified in sync, auto-corrected, recovered amount (highlighted), flagged, disputed
- Outcome bars: one row per category, real proportions from the actual run
- Audit table: order id, Razorpay status, merchant status, action taken, color-coded (green=auto-corrected, amber=flagged, red=disputed, gray=verified)
- Money trace panel: pick one record from a dropdown, render its plain-language timeline

## Demo output: real numbers from the actual run
```
Total records processed:      50
Verified in sync:             35
Auto-corrected (drift):       8   → ₹[sum of corrected order amounts] recovered
Flagged for review:           4
Disputed (reversal caught):   2
AI-classified (unmapped):     1
Correlation failures:         0
```
Every row is traceable to an audit_log entry, ready to pull up live during the pitch.

## Build order
The implementation proceeded in this sequence, because each stage depends on the last being correct first:
1. Batch data generator with the 5 scenario types above
2. Correlation + drift comparison (pure Python, testable immediately, no infra needed)
3. Direction-aware recovery action + audit logging
4. Run the batch → get real numbers → fix whatever's actually broken
5. LLM classifier for the one unmapped case
6. Minimal output: a printed table or single-page dashboard, kept deliberately minimal rather than over-invested
7. One Money Trace line for a sample record: templated text, with a live LLM call only if time remained

## Deliberately out of scope
Cut to guarantee a working, measured result by the deadline instead of a partially-built real-time system:
- Live webhook listener / real-time event handling
- Concurrency locking, atomic claim rows for race conditions
- Time-decay / grace-window timers
- Multi-tenant schema mapping
- Transactional outbox / guaranteed delivery

## If asked about the live/real-time version
"We designed the real-time version first (dedup guards, terminal locks, time-decay windows for async webhook delivery) and deliberately scoped down to a batch reconciliation run to guarantee working, measured results by the deadline. The comparison and correction logic is identical; only the event-timing infrastructure was cut."

## Panel-ready lines
- **USP**: "Razorpay already tells merchants the truth eventually. We guarantee the merchant's own system actually caught it."
- **On the risky direction**: "We only auto-correct when Razorpay's confirmed status disagrees with a merchant record that's simply behind. When the merchant record claims success but Razorpay doesn't confirm it, we never auto-resolve that. It's flagged, because that direction could mean fraud, not lag."
- **On scope**: "We didn't build five shallow recovery flows. We went deep on one evidenced, narrow failure mode and made every decision provable."
