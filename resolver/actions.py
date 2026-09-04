"""Direction-aware recovery action logic: pure, no I/O.

Given the outcome of correlation, the reversal check, and drift comparison,
decide what action to take and why. This is the only place action_taken
values are produced, so every gating rule lives in one spot:

  - Correlation failure always wins: skip, never compare.
  - A reversal on an already-resolved record always routes to DISPUTED,
    ahead of a fresh status compare.
  - An unmapped razorpay_status always routes to UNCONFIRMED_CLASSIFICATION,
    ahead of a status compare that would need the (missing) signal.
  - Safe-direction drift is the only case that auto-corrects.
  - Risky-direction drift, and any other mismatch, is flagged only — but
    kept as two distinct outcomes, since the reasoning behind each differs
    even though neither auto-corrects.
"""

from resolver.compare import MATCH, DRIFT_SAFE, DRIFT_RISKY, DRIFT_OTHER

CORRELATION_FAILED = "CORRELATION_FAILED"
VERIFIED_IN_SYNC = "VERIFIED_IN_SYNC"
AUTO_CORRECTED = "AUTO_CORRECTED"
FLAGGED_RISKY_DRIFT = "FLAGGED_RISKY_DRIFT"
FLAGGED_UNCLASSIFIED = "FLAGGED_UNCLASSIFIED"
DISPUTED = "DISPUTED"
UNCONFIRMED_CLASSIFICATION = "UNCONFIRMED_CLASSIFICATION"


def resolve_outcome(
    correlation_ok: bool,
    is_reversal_of_resolved: bool,
    razorpay_signal: str | None,
    merchant_status: str,
    drift: str | None,
) -> tuple[str, str, str | None]:
    """Return (action_taken, reason, corrected_merchant_status).

    corrected_merchant_status is only set for AUTO_CORRECTED — the new
    value the merchant's order status should be updated to.
    """
    if not correlation_ok:
        return (
            CORRELATION_FAILED,
            "razorpay_payment_id does not map to a single consistent order_id/amount in the batch",
            None,
        )

    if is_reversal_of_resolved:
        return (
            DISPUTED,
            "SETTLEMENT_REVERSED event received for a record already resolved; routed to dispute review, not dropped",
            None,
        )

    if razorpay_signal is None:
        return (
            UNCONFIRMED_CLASSIFICATION,
            "razorpay_status not present in error_code_lookup; routed to LLM classifier as unconfirmed, no automatic action taken",
            None,
        )

    if drift == MATCH:
        return (
            VERIFIED_IN_SYNC,
            f"razorpay_status and merchant_order_status both resolve to {razorpay_signal}",
            None,
        )

    if drift == DRIFT_SAFE:
        return (
            AUTO_CORRECTED,
            f"razorpay confirmed {razorpay_signal}; merchant record was behind at {merchant_status} — auto-corrected",
            razorpay_signal,
        )

    if drift == DRIFT_RISKY:
        return (
            FLAGGED_RISKY_DRIFT,
            f"razorpay={razorpay_signal} disagrees with merchant={merchant_status}; risky direction, never auto-corrected",
            None,
        )

    # DRIFT_OTHER — any mismatch outside the two defined directions
    return (
        FLAGGED_UNCLASSIFIED,
        f"razorpay={razorpay_signal} disagrees with merchant={merchant_status}; unrecognized direction, flagged rather than guessed",
        None,
    )
