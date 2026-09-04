"""Drift comparison logic: pure functions, no I/O, no external calls."""

from resolver.lookup import SUCCESS, PENDING, FAILED

MATCH = "MATCH"
DRIFT_SAFE = "DRIFT_SAFE"
DRIFT_RISKY = "DRIFT_RISKY"
DRIFT_OTHER = "DRIFT_OTHER"


def determine_drift(razorpay_signal: str, merchant_status: str) -> str:
    """Classify the relationship between a normalized razorpay signal and
    the merchant's own order status.

    Only the exact safe-direction pattern (razorpay=SUCCESS, merchant
    behind at PENDING/FAILED) is eligible for auto-correction. The exact
    risky-direction pattern (razorpay=FAILED, merchant=SUCCESS) is flagged.
    Any other mismatch is conservatively treated the same as the risky
    direction: flagged, never auto-corrected.
    """
    if razorpay_signal == merchant_status:
        return MATCH
    if razorpay_signal == SUCCESS and merchant_status in (PENDING, FAILED):
        return DRIFT_SAFE
    if razorpay_signal == FAILED and merchant_status == SUCCESS:
        return DRIFT_RISKY
    return DRIFT_OTHER
