"""LLM fallback: classify a single unmapped razorpay_status code.

This is the only LLM call anywhere in the system. It proposes a category
only — the result is always logged as UNCONFIRMED and never triggers an
automatic action.
"""

import json
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Set it in the environment or a .env file "
                "before processing a batch containing an unmapped razorpay_status."
            )
        _client = Groq(api_key=api_key)
    return _client


def classify_unmapped_code(raw_status: str) -> dict:
    resp = _get_client().chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "system",
                "content": (
                    "Classify an unmapped Razorpay payment status code as SUCCESS, "
                    'FAILED, or PENDING. Respond with JSON only: '
                    '{"proposed_category": ..., "reasoning": ...}'
                ),
            },
            {"role": "user", "content": f"Unmapped status code: {raw_status}"},
        ],
        response_format={"type": "json_object"},
    )
    result = json.loads(resp.choices[0].message.content)
    result["confidence_flag"] = "UNCONFIRMED"  # logged for review, never auto-executed
    return result
