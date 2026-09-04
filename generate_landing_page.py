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
    FLAGGED_RISKY_DRIFT,
    FLAGGED_UNCLASSIFIED,
    DISPUTED,
    UNCONFIRMED_CLASSIFICATION,
    CORRELATION_FAILED,
)

REPO_ROOT = Path(__file__).resolve().parent
TEMPLATE_PATH = REPO_ROOT / "landing" / "template.html"
OUTPUT_PATH = REPO_ROOT / "docs" / "index.html"
GITHUB_URL = "https://github.com/Khushi-Tyagi9/payment-resolver-engine"

# Proof-strip presentation, keyed by the real action_taken value pulled from audit_log.
PROOF_TAG_COLOR = {
    AUTO_CORRECTED: "#5fbf8a",
    DISPUTED: "#e2867e",
    UNCONFIRMED_CLASSIFICATION: "#b9a6f0",
}
PROOF_TAG_LABEL = {
    AUTO_CORRECTED: "AUTO_CORRECTED",
    DISPUTED: "DISPUTED",
    UNCONFIRMED_CLASSIFICATION: "AI-CLASSIFIED &middot; UNCONFIRMED",
}


def format_amount(amount: int) -> str:
    return f"{amount:,}"


def format_timestamp(iso_ts: str) -> str:
    dt = datetime.fromisoformat(iso_ts)
    return dt.strftime("%d %b %Y, %H:%M")


def pick_by_action(merged: list[dict], action: str) -> dict:
    """The most compelling real row for a given action: the highest amount."""
    matches = [r for r in merged if r["action_taken"] == action]
    if not matches:
        raise RuntimeError(f"No {action} records found — run run_reconciliation.py first.")
    return max(matches, key=lambda r: r["amount"])


def render_proof_entry(record: dict) -> str:
    action = record["action_taken"]
    tag_color = PROOF_TAG_COLOR[action]
    tag_label = PROOF_TAG_LABEL[action]

    recovered_clause = ""
    if action == AUTO_CORRECTED:
        recovered_clause = (
            f' &rarr; <span class="tag" style="color:{PROOF_TAG_COLOR[AUTO_CORRECTED]}">'
            f'&#8377;{format_amount(record["amount"])} recovered</span>'
        )

    return (
        '<div class="proof-entry">'
        '<div class="proof-line">'
        f'<span class="tag" style="color:{tag_color}">{tag_label}</span> &middot; '
        f'order <span class="field">{record["order_id"]}</span> &middot; '
        f'record <span class="field">{record["record_id"]}</span> &middot; '
        f'{format_timestamp(record["timestamp"])}<br>'
        f'razorpay=<span class="field">{record["razorpay_status"]}</span> &rarr; '
        f'merchant was <span class="field">{record["merchant_status"]}</span>{recovered_clause}'
        '</div>'
        f'<div class="proof-reason">"{record["reason"]}"</div>'
        '</div>'
    )


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
        FLAGGED_RISKY_DRIFT: 0,
        FLAGGED_UNCLASSIFIED: 0,
        DISPUTED: 0,
        UNCONFIRMED_CLASSIFICATION: 0,
        CORRELATION_FAILED: 0,
    }
    for row in audit:
        counts[row["action_taken"]] = counts.get(row["action_taken"], 0) + 1

    flagged_total = counts[FLAGGED_RISKY_DRIFT] + counts[FLAGGED_UNCLASSIFIED]
    recovered_amount = sum(r["amount"] for r in merged if r["action_taken"] == AUTO_CORRECTED)

    auto_record = pick_by_action(merged, AUTO_CORRECTED)
    dispute_record = pick_by_action(merged, DISPUTED)
    unconfirmed_record = pick_by_action(merged, UNCONFIRMED_CLASSIFICATION)
    proof_entries = [
        render_proof_entry(auto_record),
        render_proof_entry(dispute_record),
        render_proof_entry(unconfirmed_record),
    ]

    replacements = {
        "__RECOVERED_AMOUNT_DISPLAY__": f"&#8377;{format_amount(recovered_amount)}",
        "__TOTAL_PROCESSED__": str(len(audit)),
        "__VERIFIED_COUNT__": str(counts[VERIFIED_IN_SYNC]),
        "__AUTO_CORRECTED_COUNT__": str(counts[AUTO_CORRECTED]),
        "__FLAGGED_COUNT__": str(flagged_total),
        "__DISPUTED_COUNT__": str(counts[DISPUTED]),
        "__UNCONFIRMED_COUNT__": str(counts[UNCONFIRMED_CLASSIFICATION]),
        "__CORRELATION_FAILED_COUNT__": str(counts[CORRELATION_FAILED]),
        "__PROOF_ENTRIES__": "".join(proof_entries),
        "__GITHUB_URL__": GITHUB_URL,
    }

    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")

    print(f"Wrote {OUTPUT_PATH} from {len(audit)} audit_log rows")
    print(f"  Recovered: Rs.{format_amount(recovered_amount)}")
    print(
        f"  Proof entries: {auto_record['order_id']} (auto-corrected), "
        f"{dispute_record['order_id']} (disputed), {unconfirmed_record['order_id']} (ai-classified)"
    )


if __name__ == "__main__":
    main()
