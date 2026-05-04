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
st.markdown(
    "A wealth management analytics tool that identifies which U.S. banks pass Federal Reserve rate increases to depositors "
    "and which ones keep the spread as profit. Built to support deposit placement decisions for high-net-worth clients."
)

df = load_fact_data()
fred = load_fred_history()
current_fed_rate = float(df["fed_funds_rate"].iloc[0]) if not df.empty else 0.0

st.metric("Current Fed Funds Rate", f"{current_fed_rate:.2f}%",
          help="The benchmark interest rate set by the Federal Reserve. Banks use this as a floor when pricing loans and deposits.")

# ── Terminology Glossary ──────────────────────────────────────────────────────
with st.expander("📖 Key Terms — What does all this mean? (click to expand)"):
    st.markdown("""
    **APY (Annual Percentage Yield)**
    The effective annual interest rate a deposit account earns, accounting for compounding. A $100,000 deposit at 4.00% APY generates $4,000 in interest per year.

    **Fed Funds Rate**
    The benchmark overnight lending rate set by the Federal Reserve. When this rate rises, banks earn more on loans but are not required to raise deposit rates. The gap between what banks earn on assets and what they pay depositors is where this analysis focuses.

    **Pass-Through Rate (%)**
    The share of the Fed's rate increase that a bank passed on to depositors. A bank at 100% gave savers the full Fed rate. A bank at 1% absorbed nearly all of it as additional margin. High pass-through indicates a bank that competes for deposits on rate. Low pass-through indicates one that relies on customer inertia.

    **Spread (%)**
    The difference between the Fed funds rate and a bank's deposit APY. A wider spread means the bank is retaining more of the interest environment as profit. Chase's savings spread exceeds 4.6%. Marcus's is under 1%.

    **Online Bank vs. Traditional Bank**
    Online banks such as Marcus, Ally, and SoFi have no physical branches and compete almost entirely on deposit rate. Traditional banks such as Chase, Bank of America, and Wells Fargo compete on convenience and brand. Because their deposit bases are less rate-sensitive, they face less pressure to raise APYs when the Fed hikes.

    **Are deposit rates fixed or variable?**
    Savings account APYs are variable. Banks can adjust them at any time, and they typically follow Fed rate moves. CD rates are fixed for the full term. A depositor who locks in a CD today keeps that rate until maturity regardless of future Fed decisions, which makes CDs attractive when rates are expected to fall.
    """)

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
        "Green = higher APY (better for savers). Red = lower APY (bank keeping more as profit)."
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
    st.info("**What to look for:** Banks at the top of this list are paying you the most. "
            "The Spread column shows how much of the Fed rate the bank is keeping as profit instead of paying you.")


# ── Tab 2: Rate Timeline ──────────────────────────────────────────────────────
with tab2:
    st.subheader("Rate Timeline: The Fed vs. Where Banks Stand Today")
    st.markdown(
        "The black dashed line shows how the Federal Reserve's benchmark rate moved over 25 years. "
        "The colored horizontal lines show where each bank's deposit rate sits right now. "
        "This view matters because it reveals each bank's behavioral pattern. "
        "A bank that followed the Fed on the way up will likely follow it back down when rates get cut. "
        "A bank that never moved during the 2022 to 2023 hiking cycle will not move for your client in the future either. "
        "The gap between a bank's line and the Fed line is the yield your client is leaving on the table every single year."
    )

    bank_options = sorted(df["bank_name"].unique().tolist())

    default_banks = [b for b in ["SoFi", "Marcus by Goldman Sachs", "Ally Bank",
                                  "JPMorgan Chase", "Bank of America", "Wells Fargo"]
                     if b in bank_options]

    selected_banks = st.multiselect(
        "Select banks to compare",
        options=bank_options,
        default=default_banks,
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

    fig.add_trace(go.Scatter(
        x=fred["date_day"],
        y=fred["rate_pct"],
        name="Fed Funds Rate (historical)",
        line=dict(color="black", width=3, dash="dash"),
    ))

    bank_slice = df[
        (df["bank_name"].isin(selected_banks)) &
        (df["product_name"] == product_tab2)
    ].drop_duplicates("bank_name")

    online_colors = ["#2ecc71", "#27ae60", "#1abc9c", "#16a085"]
    trad_colors   = ["#e74c3c", "#c0392b", "#e67e22", "#d35400"]
    oi, ti = 0, 0

    for _, row in bank_slice.iterrows():
        is_online = row["bank_type"] == "online"
        color = online_colors[oi % len(online_colors)] if is_online else trad_colors[ti % len(trad_colors)]
        if is_online:
            oi += 1
        else:
            ti += 1
        fig.add_hline(
            y=float(row["apy_pct"]),
            line_color=color,
            line_width=2,
            annotation_text=f"{row['bank_name']} ({float(row['apy_pct']):.2f}%)",
            annotation_position="right",
        )

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Rate (%)",
        height=520,
        legend_title="",
    )
    st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)
    col_a.success("**Green lines = online banks** — their rates sit near the Fed peak. Good for savers.")
    col_b.error("**Red lines = traditional banks** — their rates barely moved from 0%. Bad for savers.")


# ── Tab 3: Pass-Through Analysis ─────────────────────────────────────────────
with tab3:
    st.subheader("Pass-Through Analysis: Who Actually Shared the Fed's Rate Hikes with Savers?")

    st.markdown(
        "When the Fed raises rates, banks earn more on every loan they make. The question is whether they share any of that with depositors. "
        "Pass-through rate measures exactly that. It is the bank's current APY divided by the Fed funds rate, expressed as a percentage. "
        "This chart is not just historical trivia. It tells you which banks have a track record of rewarding savers and which ones treat your client's deposit as free money. "
        "A bank with 100 percent pass-through is giving savers the full Fed rate. A bank at 1 percent is keeping 99 percent of every rate hike as pure profit while your client earns almost nothing. "
        "Use this to back up your recommendation with a reason, not just a number."
    )

    st.markdown("""
    | Pass-Through | What it means |
    |---|---|
    | **80% or higher** | Bank consistently rewards savers. Strong choice for your client. |
    | **10% to 50%** | Bank shares some but keeps most. Mediocre. |
    | **Under 10%** | Bank is keeping almost everything as margin. Avoid for deposit accounts. |
    """)

    product_tab3 = st.radio(
        "Product type",
        options=["savings", "cd"],
        format_func=lambda x: "Savings Accounts" if x == "savings" else "CDs",
        horizontal=True,
        key="tab3_product",
    )

    pt_df = df[df["product_name"] == product_tab3].drop_duplicates(
        subset=["bank_name", "product_name", "term_months"]
    ).sort_values("passthrough_pct", ascending=True)

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
        title=f"Pass-Through Rate by Bank — {'Savings Accounts' if product_tab3 == 'savings' else 'CDs'}",
        hover_data={"apy_pct": ":.2f"},
    )
    fig2.add_vline(x=100, line_dash="dot", line_color="gray",
                   annotation_text="100% = full Fed rate", annotation_position="top right")
    fig2.update_layout(height=max(420, len(pt_df) * 32))
    st.plotly_chart(fig2, use_container_width=True)

    col_good, col_bad = st.columns(2)
    col_good.success(
        "**Green bars (online banks) = high pass-through.**\n\n"
        "SoFi, Marcus, Ally are passing 100%+ of the Fed rate to savers. "
        "This means when the Fed raised rates, these banks raised *your* rate too."
    )
    col_bad.error(
        "**Red bars (traditional banks) = low pass-through.**\n\n"
        "Chase, BofA, and Wells Fargo pass through under 1% on savings. "
        "They kept ~99% of the Fed's rate hike as extra profit. You earned almost nothing extra."
    )

    st.info(
        "**Dollar impact:** On a $100,000 deposit — SoFi earns you ~$4,300/year. "
        "Chase earns you ~$10/year. That $4,290 difference is the cost of staying at a traditional bank."
    )


# ── Tab 4: Bank Recommender ───────────────────────────────────────────────────
with tab4:
    st.subheader("Bank Recommender")
    st.caption(
        "Select a deposit amount and product type to see which banks offer the highest returns "
        "and how much that deposit grows over time."
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

    rec_df = rec_df.drop_duplicates("bank_name")
    rec_df = rec_df.sort_values("apy_pct", ascending=False).head(5)

    def future_value(principal, apy_pct, years):
        return round(principal * (1 + apy_pct / 100) ** years, 2)

    rec_df["rationale"] = rec_df.apply(
        lambda r: (
            f"Online bank with {float(r['passthrough_pct']):.0f}% Fed rate pass-through. FDIC insured."
            if r["bank_type"] == "online"
            else f"Traditional bank with {float(r['passthrough_pct']):.0f}% pass-through. Large branch network."
        ),
        axis=1,
    )

    st.subheader(f"Top Banks for ${deposit_amount:,.0f} Deposit")
    for idx, (_, row) in enumerate(rec_df.iterrows()):
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        apy = float(row["apy_pct"])
        fv_1  = future_value(deposit_amount, apy, 1)
        fv_5  = future_value(deposit_amount, apy, 5)
        fv_10 = future_value(deposit_amount, apy, 10)
        with st.container():
            st.markdown(f"### {medals[idx]} {row['bank_name']}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("APY", f"{apy:.2f}%")
            c2.metric("Balance after 1 Year",  f"${fv_1:,.2f}")
            c3.metric("Balance after 5 Years", f"${fv_5:,.2f}")
            c4.metric("Balance after 10 Years", f"${fv_10:,.2f}")
            st.caption(row["rationale"])
            st.divider()
