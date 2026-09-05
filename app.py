"""Payment Resolver Engine dashboard — reads directly from the SQLite audit_log
produced by run_reconciliation.py."""

import html

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

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
from resolver.data_generator import generate_batch
from resolver.pipeline import run_batch

st.set_page_config(page_title="Payment Resolver Engine", page_icon="⚡", layout="wide")

FRIENDLY_LABEL = {
    VERIFIED_IN_SYNC: "Verified in sync",
    AUTO_CORRECTED: "Auto-corrected",
    FLAGGED_RISKY_DRIFT: "Flagged · risky drift",
    FLAGGED_UNCLASSIFIED: "Flagged · unclassified",
    DISPUTED: "Disputed",
    UNCONFIRMED_CLASSIFICATION: "AI-classified (unmapped)",
    CORRELATION_FAILED: "Correlation failed",
}

ACTION_ACCENT = {
    VERIFIED_IN_SYNC: "#6b7280",
    AUTO_CORRECTED: "#15803d",
    FLAGGED_RISKY_DRIFT: "#c2410c",
    FLAGGED_UNCLASSIFIED: "#a16207",
    DISPUTED: "#b91c1c",
    UNCONFIRMED_CLASSIFICATION: "#6d28d9",
    CORRELATION_FAILED: "#374151",
}

ACTION_BG = {
    VERIFIED_IN_SYNC: "#f1f2f4",
    AUTO_CORRECTED: "#e3f9ea",
    FLAGGED_RISKY_DRIFT: "#fde3d3",
    FLAGGED_UNCLASSIFIED: "#faf0d1",
    DISPUTED: "#fde4e4",
    UNCONFIRMED_CLASSIFICATION: "#f0eafd",
    CORRELATION_FAILED: "#f4f5f6",
}

CHART_ORDER = [
    VERIFIED_IN_SYNC,
    AUTO_CORRECTED,
    FLAGGED_RISKY_DRIFT,
    FLAGGED_UNCLASSIFIED,
    DISPUTED,
    UNCONFIRMED_CLASSIFICATION,
    CORRELATION_FAILED,
]

CUSTOM_CSS = """
<style>
footer, header {visibility: hidden;}
#MainMenu {visibility: visible !important; z-index: 999;}
.block-container {padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1200px;}

.hero {
    background: linear-gradient(120deg, #0c1e3e 0%, #14336b 55%, #1d4fd8 100%);
    border-radius: 18px;
    padding: 30px 36px;
    color: #f3f6ff;
    margin-bottom: 28px;
    box-shadow: 0 12px 30px rgba(20, 51, 107, 0.28);
}
.hero-badge {
    display: inline-block;
    background: rgba(255,255,255,0.14);
    border: 1px solid rgba(255,255,255,0.28);
    color: #cfe0ff;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    padding: 4px 12px;
    border-radius: 999px;
    margin-bottom: 14px;
}
.hero h1 {
    font-size: 30px;
    font-weight: 800;
    margin: 0 0 8px 0;
    color: #ffffff;
}
.hero p {
    font-size: 15px;
    color: #cdd9f5;
    margin: 0;
    max-width: 680px;
    line-height: 1.5;
}

.section-title {
    font-size: 18px;
    font-weight: 700;
    color: #111827;
    margin: 30px 0 14px 0;
    display: flex;
    align-items: center;
    gap: 8px;
}
.section-title .dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: #1d4fd8; display: inline-block;
}

.metric-card {
    background: #ffffff;
    border: 1px solid #e7e9ee;
    border-radius: 14px;
    padding: 16px 18px;
    box-shadow: 0 2px 10px rgba(17, 24, 39, 0.04);
    height: 100%;
}
.metric-card .label {
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: #6b7280;
    margin-bottom: 6px;
}
.metric-card .value {
    font-size: 26px;
    font-weight: 800;
    color: #111827;
}
.metric-card.hero-metric {
    background: linear-gradient(135deg, #16a34a 0%, #0d8a3e 100%);
    border: none;
    box-shadow: 0 8px 20px rgba(21, 128, 61, 0.30);
}
.metric-card.hero-metric .label { color: #d7f5e3; }
.metric-card.hero-metric .value { color: #ffffff; }


[data-testid="stVegaLiteChart"] {
    border: 1px solid rgba(148, 163, 184, 0.3);
    border-radius: 16px;
    padding: 20px 18px 6px 6px;
    box-shadow: 0 2px 12px rgba(17, 24, 39, 0.05);
}

.legend-row { display: flex; gap: 14px; flex-wrap: wrap; margin: 4px 0 14px 0; }
.legend-chip { display: flex; align-items: center; gap: 6px; font-size: 12.5px; color: #4b5563; }
.legend-swatch { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }

.audit-scroll {
    max-height: 560px;
    overflow-y: auto;
    border-radius: 14px;
    border: 1px solid #e7e9ee;
    box-shadow: 0 2px 10px rgba(17, 24, 39, 0.04);
}
table.audit-table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
table.audit-table thead th {
    position: sticky; top: 0;
    background: #111827; color: #f3f4f6;
    text-transform: uppercase; font-size: 11px; letter-spacing: 0.04em;
    padding: 10px 14px; text-align: left; z-index: 1;
}
table.audit-table td {
    padding: 10px 14px;
    border-bottom: 1px solid #eef0f3;
    color: #1f2937;
    vertical-align: top;
}
table.audit-table tbody tr:hover { filter: brightness(0.97); }
table.audit-table td.amount { text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; }
table.audit-table td.reason { color: #6b7280; font-size: 12.5px; max-width: 340px; }

.badge {
    display: inline-block; padding: 3px 11px; border-radius: 999px;
    font-size: 11.5px; font-weight: 700; color: #ffffff; white-space: nowrap;
}

.trace-card {
    background: #ffffff; border: 1px solid #e7e9ee; border-radius: 16px;
    padding: 22px 26px; box-shadow: 0 2px 10px rgba(17,24,39,0.04);
}
.trace-flow { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin: 14px 0 18px 0; }
.trace-chip {
    background: #f8f9fb; border: 1px solid #eceef2; border-radius: 12px;
    padding: 10px 16px; min-width: 150px;
}
.trace-chip .k { font-size: 11px; text-transform: uppercase; letter-spacing: 0.03em; color: #9ca3af; font-weight: 700; }
.trace-chip .v { font-size: 15px; font-weight: 700; color: #111827; margin-top: 2px; }
.trace-arrow { color: #9ca3af; font-size: 20px; }
.trace-note {
    background: #f8f9fb; border-left: 3px solid #1d4fd8; border-radius: 8px;
    padding: 12px 16px; font-size: 13.5px; color: #374151; line-height: 1.55;
}
.trace-reason { margin-top: 10px; font-size: 12.5px; color: #9ca3af; }

[data-testid="stMultiSelect"] [data-baseweb="tag"] {
    background-color: #1d4fd8 !important;
    border-radius: 999px !important;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] span[title] {
    color: #ffffff !important;
}
</style>
"""

# st.markdown's unsafe_allow_html inserts via innerHTML, which never executes
# <script> tags -- st.components.v1.html renders in a real (same-origin)
# iframe where <script> does execute, so it's used here to reach into the
# parent page and read the *actual* rendered background continuously, to
# keep .section-title legible -- prefers-color-scheme only reflects
# OS/browser preference and misses an explicit in-app theme override made
# in Settings, independent of it.
SECTION_TITLE_THEME_SCRIPT = """
<script>
(function(){
  var doc = window.parent.document;
  function isDarkBg(){
    var bg = getComputedStyle(doc.body).backgroundColor;
    var m = bg.match(/\\d+/g);
    if(!m) return false;
    return (parseInt(m[0])+parseInt(m[1])+parseInt(m[2]))/3 < 128;
  }
  function applyTheme(){
    var color = isDarkBg() ? '#e5e7eb' : '#111827';
    doc.querySelectorAll('.section-title').forEach(function(el){
      if (el.style.color !== color) el.style.color = color;
    });
  }
  if (window.parent.__sectionTitleThemeInterval) clearInterval(window.parent.__sectionTitleThemeInterval);
  applyTheme();
  window.parent.__sectionTitleThemeInterval = setInterval(applyTheme, 400);
})();
</script>
"""


def ensure_batch_exists():
    """Self-initialize on first load (e.g. a fresh Streamlit Cloud deploy)
    so the dashboard works without anyone running run_reconciliation.py
    by hand first. No-op once the database already exists."""
    if db.DEFAULT_DB_PATH.exists():
        return
    conn = db.get_connection()
    db.reset_schema(conn)
    batch = generate_batch()
    db.seed_orders_batch(conn, batch)
    run_batch(conn, batch)
    conn.close()


@st.cache_data(ttl=5)
def load_data():
    conn = db.get_connection()
    orders = pd.DataFrame(db.fetch_orders_batch(conn))
    audit = pd.DataFrame(db.fetch_audit_log(conn))
    conn.close()
    return orders, audit


def metric_card(label: str, value: str, hero: bool = False, accent: str | None = None) -> str:
    cls = "metric-card hero-metric" if hero else "metric-card"
    style = f' style="border-left: 4px solid {accent};"' if accent else ""
    return f'<div class="{cls}"{style}><div class="label">{html.escape(label)}</div><div class="value">{value}</div></div>'


def action_badge(action: str) -> str:
    return (
        f'<span class="badge" style="background:{ACTION_ACCENT[action]}">'
        f'{html.escape(FRIENDLY_LABEL[action])}</span>'
    )


def build_audit_table_html(rows: pd.DataFrame) -> str:
    body_rows = []
    for _, r in rows.iterrows():
        action = r["action_taken"]
        bg = ACTION_BG.get(action, "#ffffff")
        body_rows.append(
            f'<tr style="background:{bg}">'
            f'<td>{html.escape(str(r["order_id"]))}</td>'
            f'<td>{html.escape(str(r["razorpay_status"]))}</td>'
            f'<td>{html.escape(str(r["merchant_status"]))}</td>'
            f'<td class="amount">Rs.{r["amount"]:,}</td>'
            f'<td>{action_badge(action)}</td>'
            f'<td class="reason">{html.escape(str(r["reason"]))}</td>'
            f'</tr>'
        )
    return (
        '<div class="audit-scroll"><table class="audit-table">'
        '<thead><tr><th>Order ID</th><th>Razorpay Status</th><th>Merchant Status</th>'
        '<th>Amount</th><th>Action Taken</th><th>Reason</th></tr></thead>'
        f'<tbody>{"".join(body_rows)}</tbody></table></div>'
    )


def money_trace_html(record: dict) -> str:
    action = record["action_taken"]
    order_id = record["order_id"]
    payment_id = record["razorpay_payment_id"]
    amount = record["amount"]
    razorpay_status = record["razorpay_status"]
    merchant_status = record["merchant_status"]

    narrative = {
        VERIFIED_IN_SYNC: "Both systems agreed. No action needed.",
        AUTO_CORRECTED: (
            f"Razorpay's confirmed status disagreed with a merchant record that was simply behind. "
            f"The merchant order status was auto-corrected to match Razorpay — Rs.{amount:,} recovered."
        ),
        FLAGGED_RISKY_DRIFT: (
            "Merchant claimed success but Razorpay did not confirm it. This direction is never "
            "auto-resolved — it's flagged for manual review, since it could mean fraud, not lag."
        ),
        FLAGGED_UNCLASSIFIED: (
            "Razorpay and the merchant record disagree in a way that doesn't match either defined "
            "direction. Flagged rather than guessed — this combination isn't safe to auto-correct."
        ),
        DISPUTED: (
            "This record was already resolved once, then a SETTLEMENT_REVERSED event arrived. "
            "Routed to DISPUTED rather than silently dropped."
        ),
        UNCONFIRMED_CLASSIFICATION: (
            "Razorpay returned a status code outside the known lookup table. The LLM proposed a "
            "category, logged as UNCONFIRMED — no automatic action was taken."
        ),
        CORRELATION_FAILED: (
            "This payment_id did not map cleanly to a single order_id/amount. Skipped before any comparison."
        ),
    }[action]

    return f"""
    <div class="trace-card">
        <div style="font-size:15px; font-weight:700; color:#111827;">
            Order {html.escape(str(order_id))}
            <span style="color:#9ca3af; font-weight:500;">&middot; payment {html.escape(str(payment_id))}
            &middot; Rs.{amount:,}</span>
        </div>
        <div class="trace-flow">
            <div class="trace-chip"><div class="k">Razorpay status</div><div class="v">{html.escape(str(razorpay_status))}</div></div>
            <div class="trace-arrow">&#8594;</div>
            <div class="trace-chip"><div class="k">Merchant status</div><div class="v">{html.escape(str(merchant_status))}</div></div>
            <div class="trace-arrow">&#8594;</div>
            <div class="trace-chip" style="background:{ACTION_BG[action]}; border-color:{ACTION_ACCENT[action]}33;">
                <div class="k">Action taken</div><div class="v" style="color:{ACTION_ACCENT[action]};">{html.escape(FRIENDLY_LABEL[action])}</div>
            </div>
        </div>
        <div class="trace-note">{html.escape(narrative)}</div>
        <div class="trace-reason">Reason logged: {html.escape(str(record["reason"]))}</div>
    </div>
    """


def render_outcome_chart(counts: pd.Series):
    df = pd.DataFrame({
        "action": CHART_ORDER,
        "count": [int(counts.get(a, 0)) for a in CHART_ORDER],
    })
    df["label"] = df["action"].map(FRIENDLY_LABEL)
    max_count = max(1, int(df["count"].max()))

    # Neutral gray verified against both the light (#ffffff) and dark
    # (#0e1117) app backgrounds -- 5.2:1 / 3.64:1 contrast respectively.
    # Canvas-rendered chart text can't be made theme-reactive via CSS, so
    # this single value has to hold up in both.
    NEUTRAL_TEXT = "#7c8798"
    GRID_COLOR = "rgba(148, 163, 184, 0.28)"

    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadius=8, size=22)
        .encode(
            x=alt.X(
                "count:Q",
                title=None,
                axis=alt.Axis(grid=True, gridColor=GRID_COLOR, gridDash=[3, 4], labelColor=NEUTRAL_TEXT, tickColor=GRID_COLOR, domain=False),
                scale=alt.Scale(domain=[0, max_count * 1.18]),
            ),
            y=alt.Y(
                "label:N",
                sort=None,
                title=None,
                axis=alt.Axis(labelLimit=240, labelColor=NEUTRAL_TEXT, labelFontSize=13, domain=False, ticks=False),
            ),
            color=alt.Color(
                "action:N",
                scale=alt.Scale(domain=CHART_ORDER, range=[ACTION_ACCENT[a] for a in CHART_ORDER]),
                legend=None,
            ),
            tooltip=[alt.Tooltip("label:N", title="Outcome"), alt.Tooltip("count:Q", title="Count")],
        )
        .properties(height=260)
    )
    text = chart.mark_text(align="left", dx=8, color=NEUTRAL_TEXT, fontWeight=700, fontSize=13).encode(text="count:Q")
    st.altair_chart(
        (chart + text).configure_view(strokeWidth=0).configure_axis(labelFontSize=12.5, labelPadding=6),
        use_container_width=True,
    )


def main():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    components.html(SECTION_TITLE_THEME_SCRIPT, height=0)

    st.markdown(
        """
        <div class="hero">
            <div class="hero-badge">Track 3 &middot; AI Revenue Recovery &middot; Razorpay AI Buildathon 2026</div>
            <h1>Payment Resolver Engine</h1>
            <p>Razorpay already tells merchants the truth eventually. We guarantee the merchant's own
            system actually caught it — batch reconciliation with a direction-aware recovery action
            and a full audit trail behind every decision.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        ensure_batch_exists()
    except Exception as e:
        st.error(
            "Could not self-initialize the batch on first load. This usually means "
            "GROQ_API_KEY isn't set (needed for the one unmapped-status-code record). "
            f"Underlying error: {e}"
        )
        return

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

    st.markdown('<div class="section-title"><span class="dot"></span>Summary</div>', unsafe_allow_html=True)

    row1 = st.columns(3)
    with row1[0]:
        st.markdown(metric_card("Total processed", str(len(audit)), accent="#9ca3af"), unsafe_allow_html=True)
    with row1[1]:
        st.markdown(
            metric_card("Verified in sync", str(int(counts.get(VERIFIED_IN_SYNC, 0))), accent=ACTION_ACCENT[VERIFIED_IN_SYNC]),
            unsafe_allow_html=True,
        )
    with row1[2]:
        st.markdown(
            metric_card("Auto-corrected", str(int(counts.get(AUTO_CORRECTED, 0))), accent=ACTION_ACCENT[AUTO_CORRECTED]),
            unsafe_allow_html=True,
        )

    row2 = st.columns(3)
    with row2[0]:
        st.markdown(metric_card("Recovered amount", f"Rs.{recovered_amount:,.0f}", hero=True), unsafe_allow_html=True)
    with row2[1]:
        st.markdown(
            metric_card(
                "Flagged · risky drift",
                str(int(counts.get(FLAGGED_RISKY_DRIFT, 0))),
                accent=ACTION_ACCENT[FLAGGED_RISKY_DRIFT],
            ),
            unsafe_allow_html=True,
        )
    with row2[2]:
        st.markdown(
            metric_card(
                "Flagged · unclassified",
                str(int(counts.get(FLAGGED_UNCLASSIFIED, 0))),
                accent=ACTION_ACCENT[FLAGGED_UNCLASSIFIED],
            ),
            unsafe_allow_html=True,
        )

    row3 = st.columns(3)
    with row3[0]:
        st.markdown(
            metric_card("Disputed", str(int(counts.get(DISPUTED, 0))), accent=ACTION_ACCENT[DISPUTED]),
            unsafe_allow_html=True,
        )
    with row3[1]:
        st.markdown(
            metric_card(
                "AI-classified",
                str(int(counts.get(UNCONFIRMED_CLASSIFICATION, 0))),
                accent=ACTION_ACCENT[UNCONFIRMED_CLASSIFICATION],
            ),
            unsafe_allow_html=True,
        )
    with row3[2]:
        st.markdown(
            metric_card(
                "Correlation failures",
                str(int(counts.get(CORRELATION_FAILED, 0))),
                accent=ACTION_ACCENT[CORRELATION_FAILED],
            ),
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-title"><span class="dot"></span>Outcome distribution</div>', unsafe_allow_html=True)
    render_outcome_chart(counts)

    st.markdown('<div class="section-title"><span class="dot"></span>Audit log</div>', unsafe_allow_html=True)
    legend_chips = "".join(
        f'<span class="legend-chip"><span class="legend-swatch" style="background:{ACTION_ACCENT[a]}"></span>{FRIENDLY_LABEL[a]}</span>'
        for a in CHART_ORDER
    )
    st.markdown(f'<div class="legend-row">{legend_chips}</div>', unsafe_allow_html=True)

    action_options = [a for a in CHART_ORDER if a in counts.index]
    selected_actions = st.multiselect(
        "Filter by action taken",
        options=action_options,
        default=action_options,
        format_func=lambda a: FRIENDLY_LABEL[a],
        label_visibility="collapsed",
    )
    filtered = merged[merged["action_taken"].isin(selected_actions)] if selected_actions else merged
    st.markdown(build_audit_table_html(filtered), unsafe_allow_html=True)

    st.markdown('<div class="section-title"><span class="dot"></span>Money trace</div>', unsafe_allow_html=True)
    options = (merged["order_id"] + " — " + merged["record_id"]).tolist()
    choice = st.selectbox("Pick a record", options, label_visibility="collapsed")
    chosen_record_id = choice.split(" — ")[-1]
    record = merged[merged["record_id"] == chosen_record_id].iloc[0].to_dict()
    st.markdown(money_trace_html(record), unsafe_allow_html=True)


if __name__ == "__main__":
    main()
