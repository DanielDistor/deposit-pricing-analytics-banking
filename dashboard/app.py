import streamlit as st
import snowflake.connector
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="Deposit Pricing Analytics",
    page_icon="🏦",
    layout="wide",
)

def _new_connection():
    return snowflake.connector.connect(
        account=st.secrets["snowflake"]["account"],
        user=st.secrets["snowflake"]["user"],
        password=st.secrets["snowflake"]["password"],
        warehouse=st.secrets["snowflake"]["warehouse"],
        database=st.secrets["snowflake"]["database"],
        schema=st.secrets["snowflake"]["schema"],
    )


@st.cache_data(ttl=3600)
def run_query(sql: str) -> pd.DataFrame:
    conn = _new_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [desc[0].lower() for desc in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)
    finally:
        conn.close()


def load_fact_data() -> pd.DataFrame:
    return run_query("""
        SELECT
            b.bank_name,
            b.bank_type,
            p.product_display_name,
            p.product_name,
            p.term_months,
            f.apy_pct,
            f.fed_funds_rate,
            f.spread_pct,
            f.passthrough_pct,
            f.scrape_date
        FROM DEPOSIT_ANALYTICS.MART.FACT_DEPOSIT_RATES f
        JOIN DEPOSIT_ANALYTICS.MART.DIM_BANK b    ON b.bank_key    = f.bank_key
        JOIN DEPOSIT_ANALYTICS.MART.DIM_PRODUCT p ON p.product_key = f.product_key
        ORDER BY f.apy_pct DESC
    """)


def load_fred_history() -> pd.DataFrame:
    return run_query("""
        SELECT date_day, rate_pct, series_name
        FROM DEPOSIT_ANALYTICS.STAGING.STG_FRED_OBSERVATIONS
        WHERE series_id = 'FEDFUNDS'
        ORDER BY date_day
    """)


# ── Header ────────────────────────────────────────────────────────────────────
st.title("🏦 Deposit Pricing Analytics")
st.caption(
    "Tracking how major U.S. banks respond to Federal Reserve rate changes. "
    "Data: FRED API (Fed rates) + Bankrate (bank deposit rates)."
)

df = load_fact_data()
fred = load_fred_history()
current_fed_rate = float(df["fed_funds_rate"].iloc[0]) if not df.empty else 0.0

st.metric("Current Fed Funds Rate", f"{current_fed_rate:.2f}%")
st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Current Rates",
    "📈 Rate Timeline",
    "⚡ Pass-Through Analysis",
    "💡 Bank Recommender",
])


# ── Tab 1: Current Rates ──────────────────────────────────────────────────────
with tab1:
    st.subheader("Current Deposit Rates — All Banks")
    st.caption(
        "A snapshot of today's deposit rates across all banks, ranked by APY. "
        "Green = higher pass-through to savers, Red = bank keeping more of the Fed rate as margin."
    )

    product_filter = st.selectbox(
        "Filter by product",
        options=["All", "savings", "cd"],
        format_func=lambda x: "All Products" if x == "All" else ("Savings Accounts" if x == "savings" else "CDs"),
        key="tab1_product",
    )

    display_df = df.copy()
    if product_filter != "All":
        display_df = display_df[display_df["product_name"] == product_filter]

    display_df = display_df[[
        "bank_name", "bank_type", "product_display_name",
        "apy_pct", "fed_funds_rate", "spread_pct", "passthrough_pct"
    ]].rename(columns={
        "bank_name": "Bank",
        "bank_type": "Type",
        "product_display_name": "Product",
        "apy_pct": "APY (%)",
        "fed_funds_rate": "Fed Rate (%)",
        "spread_pct": "Spread (%)",
        "passthrough_pct": "Pass-Through (%)",
    })

    st.dataframe(
        display_df.style.background_gradient(subset=["APY (%)"], cmap="RdYlGn"),
        use_container_width=True,
        hide_index=True,
    )


# ── Tab 2: Rate Timeline ──────────────────────────────────────────────────────
with tab2:
    st.subheader("Rate Timeline: Banks vs. the Fed")
    st.caption(
        "How have deposit rates changed over time relative to the Federal Reserve's benchmark rate? "
        "Banks that closely track the Fed line are passing more value to savers."
    )

    bank_options = sorted(df["bank_name"].unique().tolist())
    selected_banks = st.multiselect(
        "Select banks to display",
        options=bank_options,
        default=bank_options[:6],
        key="tab2_banks",
    )

    product_tab2 = st.radio(
        "Product type",
        options=["savings", "cd"],
        format_func=lambda x: "Savings Accounts" if x == "savings" else "CDs",
        horizontal=True,
        key="tab2_product",
    )

    fig = go.Figure()

    # Fed funds rate line
    fig.add_trace(go.Scatter(
        x=fred["date_day"],
        y=fred["rate_pct"],
        name="Fed Funds Rate",
        line=dict(color="black", width=3, dash="dash"),
    ))

    # Current bank rates as horizontal reference lines
    bank_slice = df[
        (df["bank_name"].isin(selected_banks)) &
        (df["product_name"] == product_tab2)
    ]
    colors = px.colors.qualitative.Set2
    for i, (_, row) in enumerate(bank_slice.iterrows()):
        fig.add_hline(
            y=float(row["apy_pct"]),
            line_color=colors[i % len(colors)],
            line_width=2,
            annotation_text=f"{row['bank_name']} ({float(row['apy_pct']):.2f}%)",
            annotation_position="right",
        )

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Rate (%)",
        legend_title="Series",
        height=500,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.info(
        "**Takeaway:** The Fed raised rates from ~0% to 5.25%+ during 2022–2023. "
        "Online banks tracked this rise; big traditional banks barely moved their savings rates."
    )


# ── Tab 3: Pass-Through Analysis ─────────────────────────────────────────────
with tab3:
    st.subheader("Pass-Through Analysis: Who Shared Fed Hikes with Savers?")
    st.caption(
        "Pass-through % = bank's current APY ÷ current Fed funds rate × 100. "
        "A bank at 100% gives savers the full Fed rate. Lower = bank kept more as margin."
    )

    product_tab3 = st.radio(
        "Product type",
        options=["savings", "cd"],
        format_func=lambda x: "Savings Accounts" if x == "savings" else "CDs",
        horizontal=True,
        key="tab3_product",
    )

    pt_df = df[df["product_name"] == product_tab3].sort_values("passthrough_pct", ascending=True)

    fig2 = px.bar(
        pt_df,
        x="passthrough_pct",
        y="bank_name",
        orientation="h",
        color="bank_type",
        color_discrete_map={"online": "#2ecc71", "traditional": "#e74c3c"},
        labels={
            "passthrough_pct": "Pass-Through (%)",
            "bank_name": "Bank",
            "bank_type": "Type",
        },
        title=f"Pass-Through Rate by Bank — {'Savings' if product_tab3 == 'savings' else 'CD'}",
    )
    fig2.update_layout(height=max(400, len(pt_df) * 30))
    st.plotly_chart(fig2, use_container_width=True)
    st.info(
        "**Takeaway:** Online banks consistently pass through 70–90%+ of Fed rate increases. "
        "Traditional big banks pass through under 5% on savings accounts, keeping the spread as profit."
    )


# ── Tab 4: Bank Recommender ───────────────────────────────────────────────────
with tab4:
    st.subheader("💡 Bank Recommender")
    st.caption(
        "Based on current rates and historical fairness, which bank should your client choose? "
        "Enter the deposit amount and product preference to see projected annual earnings."
    )

    col1, col2 = st.columns(2)
    with col1:
        deposit_amount = st.slider(
            "Deposit amount ($)",
            min_value=1_000,
            max_value=1_000_000,
            value=50_000,
            step=1_000,
            format="$%d",
        )
    with col2:
        product_rec = st.radio(
            "Product type",
            options=["savings", "cd"],
            format_func=lambda x: "Savings Account" if x == "savings" else "Certificate of Deposit (CD)",
            key="tab4_product",
        )

    term_months = None
    if product_rec == "cd":
        term_label = st.selectbox(
            "CD term",
            options=["6-Month CD", "1-Year CD", "3-Year CD", "5-Year CD"],
        )
        term_map = {"6-Month CD": 6, "1-Year CD": 12, "3-Year CD": 36, "5-Year CD": 60}
        term_months = term_map[term_label]

    rec_df = df[df["product_name"] == product_rec].copy()
    if term_months:
        rec_df = rec_df[rec_df["term_months"] == term_months]

    rec_df["annual_earnings"] = (rec_df["apy_pct"].astype(float) / 100 * deposit_amount).round(2)
    rec_df = rec_df.sort_values("apy_pct", ascending=False).head(5)
    rec_df["rationale"] = rec_df.apply(
        lambda r: (
            f"Top-rated online bank with {float(r['passthrough_pct']):.0f}% Fed rate pass-through."
            if r["bank_type"] == "online"
            else f"Traditional bank — {float(r['passthrough_pct']):.0f}% pass-through, stable and FDIC insured."
        ),
        axis=1,
    )

    st.subheader(f"Top Banks for ${deposit_amount:,.0f} Deposit")
    for idx, (_, row) in enumerate(rec_df.iterrows()):
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        with st.container():
            st.markdown(f"### {medals[idx]} {row['bank_name']}")
            c1, c2, c3 = st.columns(3)
            c1.metric("APY", f"{float(row['apy_pct']):.2f}%")
            c2.metric("Annual Earnings", f"${float(row['annual_earnings']):,.2f}")
            c3.metric("Pass-Through", f"{float(row['passthrough_pct']):.0f}%")
            st.caption(row["rationale"])
            st.divider()
