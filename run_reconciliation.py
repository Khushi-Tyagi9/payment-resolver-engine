"""Entry point: generate a batch, run the reconciliation pipeline, print the summary."""

from collections import Counter

from resolver import db
from resolver.actions import (
    VERIFIED_IN_SYNC,
    AUTO_CORRECTED,
    FLAGGED_FOR_REVIEW,
    DISPUTED,
    UNCONFIRMED_CLASSIFICATION,
    CORRELATION_FAILED,
)
from resolver.data_generator import generate_batch
from resolver.pipeline import run_batch


def main() -> None:
    conn = db.get_connection()
    db.reset_schema(conn)

    batch = generate_batch()
    db.seed_orders_batch(conn, batch)
    batch_by_id = {r["record_id"]: r for r in batch}

    audit_rows = run_batch(conn, batch)
    counts = Counter(r["action_taken"] for r in audit_rows)

    recovered_amount = sum(
        batch_by_id[r["record_id"]]["amount"]
        for r in audit_rows
        if r["action_taken"] == AUTO_CORRECTED
    )

    print(f"Total records processed:      {len(audit_rows)}")
    print(f"Verified in sync:             {counts[VERIFIED_IN_SYNC]}")
    print(f"Auto-corrected (drift):       {counts[AUTO_CORRECTED]}   -> Rs.{recovered_amount:,} recovered")
    print(f"Flagged for review:           {counts[FLAGGED_FOR_REVIEW]}")
    print(f"Disputed (reversal caught):   {counts[DISPUTED]}")
    print(f"AI-classified (unmapped):     {counts[UNCONFIRMED_CLASSIFICATION]}")
    print(f"Correlation failures:         {counts[CORRELATION_FAILED]}")

    conn.close()


if __name__ == "__main__":
    main()
