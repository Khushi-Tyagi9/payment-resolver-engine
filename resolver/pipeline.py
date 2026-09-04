"""Orchestrates the per-record pipeline: correlate -> reversal check ->
unmapped check -> compare -> act -> log.

Processes records in chronological order so that a reversal event is only
ever evaluated after the original transaction it reverses.
"""

from resolver import db
from resolver.actions import (
    resolve_outcome,
    VERIFIED_IN_SYNC,
    AUTO_CORRECTED,
)
from resolver.classifier import classify_unmapped_code
from resolver.compare import determine_drift
from resolver.correlate import build_correlation_index, correlate
from resolver.data_generator import REVERSAL_EVENT_TYPES
from resolver.lookup import normalize_razorpay_status

RESOLVED_ACTIONS = {VERIFIED_IN_SYNC, AUTO_CORRECTED}


def process_batch(records: list[dict], classify_fn=classify_unmapped_code) -> tuple[list[dict], list[tuple[str, str]]]:
    """Pure(ish) processing pass over a batch: no DB I/O, one optional LLM
    call per unmapped record. Returns (audit_rows, corrections)."""
    index = build_correlation_index(records)
    resolved_order_ids: set[str] = set()
    audit_rows: list[dict] = []
    corrections: list[tuple[str, str]] = []

    ordered = sorted(records, key=lambda r: (r["timestamp"], r["record_id"]))

    for record in ordered:
        correlation_ok = correlate(record, index)
        is_reversal_event = record["event_type"] in REVERSAL_EVENT_TYPES
        is_reversal_of_resolved = (
            correlation_ok and is_reversal_event and record["order_id"] in resolved_order_ids
        )

        razorpay_signal = normalize_razorpay_status(record["razorpay_status"])
        drift = None
        classification = None

        if correlation_ok and not is_reversal_of_resolved:
            if razorpay_signal is None:
                classification = classify_fn(record["razorpay_status"])
            else:
                drift = determine_drift(razorpay_signal, record["merchant_order_status"])

        action_taken, reason, corrected_status = resolve_outcome(
            correlation_ok,
            is_reversal_of_resolved,
            razorpay_signal,
            record["merchant_order_status"],
            drift,
        )

        if classification is not None:
            reason = (
                f"{reason} | LLM proposed_category={classification.get('proposed_category')} "
                f"reasoning={classification.get('reasoning')}"
            )

        audit_rows.append({
            "record_id": record["record_id"],
            "correlation_ok": int(correlation_ok),
            "razorpay_status": record["razorpay_status"],
            "merchant_status": record["merchant_order_status"],
            "drift_direction": drift,
            "action_taken": action_taken,
            "reason": reason,
            "timestamp": record["timestamp"],
        })

        if action_taken in RESOLVED_ACTIONS:
            resolved_order_ids.add(record["order_id"])

        if corrected_status is not None:
            corrections.append((record["order_id"], corrected_status))

    return audit_rows, corrections


def run_batch(conn, records: list[dict], classify_fn=classify_unmapped_code) -> list[dict]:
    """Process a batch and persist audit rows + merchant corrections to SQLite."""
    audit_rows, corrections = process_batch(records, classify_fn)

    for row in audit_rows:
        db.insert_audit_row(conn, row)

    for order_id, new_status in corrections:
        db.update_merchant_status(conn, order_id, new_status)

    return audit_rows
