"""Payment Resolver Engine dashboard — reads directly from the SQLite audit_log
produced by run_reconciliation.py."""

import pandas as pd
import streamlit as st

from resolver import db
from resolver.actions import (
    VERIFIED_IN_SYNC,
    AUTO_CORRECTED,
    FLAGGED_FOR_REVIEW,
    DISPUTED,
    UNCONFIRMED_CLASSIFICATION,
    CORRELATION_FAILED,
)

st.set_page_config(page_title="Payment Resolver Engine", layout="wide")

ROW_COLORS = {
    AUTO_CORRECTED: "#d4f4dd",
    FLAGGED_FOR_REVIEW: "#fdecc8",
    DISPUTED: "#fbd5d5",
    VERIFIED_IN_SYNC: "#e8e8e8",
    UNCONFIRMED_CLASSIFICATION: "#e0d9f7",
    CORRELATION_FAILED: "#f5f5f5",
}


@st.cache_data(ttl=5)
def load_data():
    conn = db.get_connection()
    orders = pd.DataFrame(db.fetch_orders_batch(conn))
    audit = pd.DataFrame(db.fetch_audit_log(conn))
    conn.close()
    return orders, audit


def money_trace(record: dict) -> str:
    action = record["action_taken"]
    order_id = record["order_id"]
    payment_id = record["razorpay_payment_id"]
    amount = record["amount"]
    razorpay_status = record["razorpay_status"]
    merchant_status = record["merchant_status"]

    lines = [
        f"Order **{order_id}** — payment `{payment_id}` — amount Rs.{amount:,}",
        f"Razorpay reported: **{razorpay_status}** | Merchant system showed: **{merchant_status}**",
    ]

    if action == VERIFIED_IN_SYNC:
        lines.append("Both systems agreed. No action needed.")
    elif action == AUTO_CORRECTED:
        lines.append(
            f"Razorpay's confirmed status disagreed with a merchant record that was simply behind. "
            f"The merchant order status was auto-corrected to match Razorpay — Rs.{amount:,} recovered."
        )
    elif action == FLAGGED_FOR_REVIEW:
        lines.append(
            "Merchant claimed success but Razorpay did not confirm it. This direction is never "
            "auto-resolved — it's flagged for manual review, since it could mean fraud, not lag."
        )
    elif action == DISPUTED:
        lines.append(
            "This record was already resolved once, then a SETTLEMENT_REVERSED event arrived. "
            "Routed to DISPUTED rather than silently dropped."
        )
    elif action == UNCONFIRMED_CLASSIFICATION:
        lines.append(
            "Razorpay returned a status code outside the known lookup table. The LLM proposed a "
            "category, logged as UNCONFIRMED — no automatic action was taken."
        )
    elif action == CORRELATION_FAILED:
        lines.append("This payment_id did not map cleanly to a single order_id/amount. Skipped before any comparison.")

    lines.append(f"Reason logged: {record['reason']}")
    return "\n\n".join(lines)


def main():
    st.title("Payment Resolver Engine")
    st.caption("Razorpay vs. merchant order status — batch reconciliation audit trail")

    try:
        orders, audit = load_data()
    except Exception:
        st.error("No data found. Run `python run_reconciliation.py` first to generate and process a batch.")
        return

    if audit.empty:
        st.error("audit_log is empty. Run `python run_reconciliation.py` first.")
        return

    merged = audit.merge(orders, on="record_id", suffixes=("", "_order"))

    counts = audit["action_taken"].value_counts()
    recovered_amount = merged.loc[merged["action_taken"] == AUTO_CORRECTED, "amount"].sum()

    st.subheader("Summary")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total processed", len(audit))
    c2.metric("Verified in sync", int(counts.get(VERIFIED_IN_SYNC, 0)))
    c3.metric("Auto-corrected", int(counts.get(AUTO_CORRECTED, 0)))
    c4.metric("Recovered amount", f"Rs.{recovered_amount:,.0f}")
    c5.metric("Flagged for review", int(counts.get(FLAGGED_FOR_REVIEW, 0)))
    c6.metric("Disputed", int(counts.get(DISPUTED, 0)))

    st.subheader("Outcome distribution")
    outcome_counts = counts.reindex(
        [VERIFIED_IN_SYNC, AUTO_CORRECTED, FLAGGED_FOR_REVIEW, DISPUTED, UNCONFIRMED_CLASSIFICATION, CORRELATION_FAILED],
        fill_value=0,
    )
    st.bar_chart(outcome_counts)

    st.subheader("Audit log")
    display_cols = ["order_id", "razorpay_status", "merchant_status", "action_taken", "reason"]
    display_df = merged[display_cols].rename(columns={
        "order_id": "Order ID",
        "razorpay_status": "Razorpay Status",
        "merchant_status": "Merchant Status",
        "action_taken": "Action Taken",
        "reason": "Reason",
    })

    st.caption(
        "Green = auto-corrected · Amber = flagged for review · Red = disputed · Gray = verified in sync"
    )

    def highlight_row(row):
        color = ROW_COLORS.get(row["Action Taken"], "#ffffff")
        return [f"background-color: {color}; color: #1a1a1a"] * len(row)

    # st.dataframe renders through a canvas grid that ignores Styler colors —
    # st.table renders static HTML, which is what actually shows the color-coding.
    st.table(display_df.style.apply(highlight_row, axis=1))

    st.subheader("Money trace")
    options = merged["order_id"] + " — " + merged["record_id"]
    choice = st.selectbox("Pick a record", options)
    chosen_record_id = choice.split(" — ")[-1]
    record = merged[merged["record_id"] == chosen_record_id].iloc[0].to_dict()
    st.markdown(money_trace(record))


if __name__ == "__main__":
    main()
