"""Deterministic mapping from raw Razorpay status codes to a normalized signal.

Anything not present here is an unmapped code and must route to the LLM
fallback classifier — never guessed silently by Python.
"""

SUCCESS = "SUCCESS"
FAILED = "FAILED"
PENDING = "PENDING"

ERROR_CODE_LOOKUP = {
    "captured": SUCCESS,
    "authorized": PENDING,
    "created": PENDING,
    "pending": PENDING,
    "failed": FAILED,
    "refunded": FAILED,
}


def normalize_razorpay_status(raw_status: str) -> str | None:
    """Return the normalized signal for a raw razorpay_status, or None if unmapped."""
    return ERROR_CODE_LOOKUP.get(raw_status)
