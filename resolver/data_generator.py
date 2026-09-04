"""Synthetic orders_batch generator.

Seeds the five scenario types called out in the spec:
  - ~35 clean matches (razorpay_status == merchant_order_status)
  - ~8 drift, safe direction   (razorpay=SUCCESS, merchant=PENDING/FAILED)
  - ~4 drift, risky direction  (razorpay=FAILED,  merchant=SUCCESS)
  - ~2 reversal events (SETTLEMENT_REVERSED applied to an already-matched record)
  - ~1 unmapped razorpay_status code

Reversal rows are additional rows appended to the batch, layered on top of
two of the clean-match SUCCESS/SUCCESS records — so the total row count is
35 + 8 + 4 + 1 + 2 = 50, matching the spec's demo output.
"""

import random
import string
from datetime import datetime, timedelta

from resolver.lookup import SUCCESS, PENDING, FAILED

RAW_CODES_BY_SIGNAL = {
    SUCCESS: ["captured"],
    PENDING: ["authorized", "created", "pending"],
    FAILED: ["failed", "refunded"],
}

UNMAPPED_RAW_STATUS = "npci_timeout"

PAYMENT_UPDATE = "PAYMENT_UPDATE"
SETTLEMENT_REVERSED = "SETTLEMENT_REVERSED"
REVERSAL_EVENT_TYPES = {SETTLEMENT_REVERSED}


def _random_payment_id(rng: random.Random) -> str:
    suffix = "".join(rng.choices(string.ascii_letters + string.digits, k=14))
    return f"pay_{suffix}"


def _random_order_id(rng: random.Random, seq: int) -> str:
    return f"ORD{1000 + seq}"


def _random_amount(rng: random.Random) -> int:
    return rng.randint(199, 49999)


def generate_batch(seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    base_time = datetime(2026, 9, 1, 9, 0, 0)
    rows: list[dict] = []
    reversal_targets: list[dict] = []

    seq = 0

    # ~35 clean matches, weighted across SUCCESS/PENDING/FAILED
    clean_signal_plan = [SUCCESS] * 20 + [PENDING] * 8 + [FAILED] * 7
    rng.shuffle(clean_signal_plan)
    for signal in clean_signal_plan:
        seq += 1
        raw_status = rng.choice(RAW_CODES_BY_SIGNAL[signal])
        row = {
            "razorpay_payment_id": _random_payment_id(rng),
            "order_id": _random_order_id(rng, seq),
            "amount": _random_amount(rng),
            "razorpay_status": raw_status,
            "merchant_order_status": signal,
            "event_type": PAYMENT_UPDATE,
            "timestamp": base_time + timedelta(minutes=seq * 3),
        }
        rows.append(row)
        if signal == SUCCESS:
            reversal_targets.append(row)

    # ~8 safe-direction drift: razorpay=SUCCESS, merchant=PENDING/FAILED
    for _ in range(8):
        seq += 1
        rows.append({
            "razorpay_payment_id": _random_payment_id(rng),
            "order_id": _random_order_id(rng, seq),
            "amount": _random_amount(rng),
            "razorpay_status": rng.choice(RAW_CODES_BY_SIGNAL[SUCCESS]),
            "merchant_order_status": rng.choice([PENDING, FAILED]),
            "event_type": PAYMENT_UPDATE,
            "timestamp": base_time + timedelta(minutes=seq * 3),
        })

    # ~4 risky-direction drift: razorpay=FAILED, merchant=SUCCESS
    for _ in range(4):
        seq += 1
        rows.append({
            "razorpay_payment_id": _random_payment_id(rng),
            "order_id": _random_order_id(rng, seq),
            "amount": _random_amount(rng),
            "razorpay_status": rng.choice(RAW_CODES_BY_SIGNAL[FAILED]),
            "merchant_order_status": SUCCESS,
            "event_type": PAYMENT_UPDATE,
            "timestamp": base_time + timedelta(minutes=seq * 3),
        })

    # ~1 unmapped razorpay_status code
    seq += 1
    rows.append({
        "razorpay_payment_id": _random_payment_id(rng),
        "order_id": _random_order_id(rng, seq),
        "amount": _random_amount(rng),
        "razorpay_status": UNMAPPED_RAW_STATUS,
        "merchant_order_status": PENDING,
        "event_type": PAYMENT_UPDATE,
        "timestamp": base_time + timedelta(minutes=seq * 3),
    })

    # ~2 reversal events, layered on top of two SUCCESS/SUCCESS clean matches
    chosen_targets = rng.sample(reversal_targets, 2)
    for target in chosen_targets:
        seq += 1
        rows.append({
            "razorpay_payment_id": target["razorpay_payment_id"],
            "order_id": target["order_id"],
            "amount": target["amount"],
            "razorpay_status": target["razorpay_status"],
            "merchant_order_status": target["merchant_order_status"],
            "event_type": SETTLEMENT_REVERSED,
            "timestamp": target["timestamp"] + timedelta(days=1),
        })

    # Assign record_id in chronological (processing) order.
    rows.sort(key=lambda r: r["timestamp"])
    for i, row in enumerate(rows, start=1):
        row["record_id"] = f"REC{i:04d}"
        row["timestamp"] = row["timestamp"].isoformat()

    # Reorder keys to match the spec's column order.
    ordered = [
        {
            "record_id": r["record_id"],
            "razorpay_payment_id": r["razorpay_payment_id"],
            "order_id": r["order_id"],
            "amount": r["amount"],
            "razorpay_status": r["razorpay_status"],
            "merchant_order_status": r["merchant_order_status"],
            "event_type": r["event_type"],
            "timestamp": r["timestamp"],
        }
        for r in rows
    ]
    return ordered


if __name__ == "__main__":
    batch = generate_batch()
    print(f"Generated {len(batch)} records")
    for row in batch:
        print(row)
