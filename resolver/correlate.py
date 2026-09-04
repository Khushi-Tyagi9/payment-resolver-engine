"""Correlation logic: run before any status comparison.

A record correlates only if its razorpay_payment_id maps to exactly one
order_id and one amount across the whole batch. Never compare unrelated
transactions.
"""

CorrelationIndex = dict[str, set[tuple[str, int]]]


def build_correlation_index(records: list[dict]) -> CorrelationIndex:
    index: CorrelationIndex = {}
    for r in records:
        key = r["razorpay_payment_id"]
        index.setdefault(key, set()).add((r["order_id"], r["amount"]))
    return index


def correlate(record: dict, index: CorrelationIndex) -> bool:
    entries = index.get(record["razorpay_payment_id"], set())
    order_ids = {order_id for order_id, _ in entries}
    amounts = {amount for _, amount in entries}
    if len(order_ids) != 1 or len(amounts) != 1:
        return False
    return record["order_id"] in order_ids and record["amount"] in amounts
