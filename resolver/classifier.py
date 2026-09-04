"""LLM fallback: classify a single unmapped razorpay_status code.

This is the only LLM call anywhere in the system. It proposes a category
only — the result is always logged as UNCONFIRMED and never triggers an
automatic action.

Placeholder until the Groq classifier is wired in (build stage 6).
"""


def classify_unmapped_code(raw_status: str) -> dict:
    return {
        "proposed_category": "UNKNOWN",
        "reasoning": "LLM classifier not yet integrated",
        "confidence_flag": "UNCONFIRMED",
    }
