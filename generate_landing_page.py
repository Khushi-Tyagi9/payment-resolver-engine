"""Generates docs/index.html from landing/template.html, filling in every
number from the real audit_log — run this after run_reconciliation.py.

Does not touch the reconciliation pipeline, data generator, or dashboard.
Read-only against the SQLite database they already produced.
"""

from datetime import datetime
from pathlib import Path

from resolver import db
from resolver.actions import (
    VERIFIED_IN_SYNC,
    AUTO_CORRECTED,
    FLAGGED_FOR_REVIEW,
    DISPUTED,
    UNCONFIRMED_CLASSIFICATION,
    CORRELATION_FAILED,
)

REPO_ROOT = Path(__file__).resolve().parent
TEMPLATE_PATH = REPO_ROOT / "landing" / "template.html"
OUTPUT_PATH = REPO_ROOT / "docs" / "index.html"
GITHUB_URL = "https://github.com/Khushi-Tyagi9/payment-resolver-engine"


def format_amount(amount: int) -> str:
    return f"{amount:,}"


def format_timestamp(iso_ts: str) -> str:
    dt = datetime.fromisoformat(iso_ts)
    return dt.strftime("%d %b %Y, %H:%M")


def pick_proof_record(merged: list[dict]) -> dict:
    """The most compelling real row: the highest-amount AUTO_CORRECTED record."""
    auto_corrected = [r for r in merged if r["action_taken"] == AUTO_CORRECTED]
    if not auto_corrected:
        raise RuntimeError("No AUTO_CORRECTED records found — run run_reconciliation.py first.")
    return max(auto_corrected, key=lambda r: r["amount"])


def main() -> None:
    if not db.DEFAULT_DB_PATH.exists():
        raise RuntimeError(
            f"No database found at {db.DEFAULT_DB_PATH}. Run `python run_reconciliation.py` first."
        )

    conn = db.get_connection()
    orders = {r["record_id"]: r for r in db.fetch_orders_batch(conn)}
    audit = db.fetch_audit_log(conn)
    conn.close()

    if not audit:
        raise RuntimeError("audit_log is empty. Run `python run_reconciliation.py` first.")

    merged = [{**audit_row, **orders[audit_row["record_id"]]} for audit_row in audit]

    counts = {
        VERIFIED_IN_SYNC: 0,
        AUTO_CORRECTED: 0,
        FLAGGED_FOR_REVIEW: 0,
        DISPUTED: 0,
        UNCONFIRMED_CLASSIFICATION: 0,
        CORRELATION_FAILED: 0,
    }
    for row in audit:
        counts[row["action_taken"]] = counts.get(row["action_taken"], 0) + 1

    recovered_amount = sum(r["amount"] for r in merged if r["action_taken"] == AUTO_CORRECTED)
    proof = pick_proof_record(merged)

    replacements = {
        "__RECOVERED_AMOUNT_DISPLAY__": f"&#8377;{format_amount(recovered_amount)}",
        "__TOTAL_PROCESSED__": str(len(audit)),
        "__VERIFIED_COUNT__": str(counts[VERIFIED_IN_SYNC]),
        "__AUTO_CORRECTED_COUNT__": str(counts[AUTO_CORRECTED]),
        "__FLAGGED_COUNT__": str(counts[FLAGGED_FOR_REVIEW]),
        "__DISPUTED_COUNT__": str(counts[DISPUTED]),
        "__UNCONFIRMED_COUNT__": str(counts[UNCONFIRMED_CLASSIFICATION]),
        "__CORRELATION_FAILED_COUNT__": str(counts[CORRELATION_FAILED]),
        "__PROOF_ORDER_ID__": str(proof["order_id"]),
        "__PROOF_RECORD_ID__": str(proof["record_id"]),
        "__PROOF_TIMESTAMP__": format_timestamp(proof["timestamp"]),
        "__PROOF_RAZORPAY_STATUS__": str(proof["razorpay_status"]),
        "__PROOF_MERCHANT_STATUS__": str(proof["merchant_status"]),
        "__PROOF_AMOUNT__": format_amount(proof["amount"]),
        "__PROOF_REASON__": str(proof["reason"]),
        "__GITHUB_URL__": GITHUB_URL,
    }

    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")

    print(f"Wrote {OUTPUT_PATH} from {len(audit)} audit_log rows")
    print(f"  Recovered: Rs.{format_amount(recovered_amount)}")
    print(f"  Proof record: {proof['order_id']} / {proof['record_id']}")


if __name__ == "__main__":
    main()
