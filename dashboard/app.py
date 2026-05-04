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
    "A wealth management tool that tracks how major U.S. banks respond to Federal Reserve rate changes. "
    "Use it to see which banks are paying savers the most and where clients should be putting their money."
)

df = load_fact_data()
fred = load_fred_history()
current_fed_rate = float(df["fed_funds_rate"].iloc[0]) if not df.empty else 0.0
fred_as_of = pd.to_datetime(fred["date_day"].iloc[-1]).strftime("%B %Y") if not fred.empty else ""

st.metric("Current Fed Funds Rate", f"{current_fed_rate:.2f}%")
st.caption(
    f"As of {fred_as_of}. Source: Federal Reserve Bank of St. Louis (FRED), series FEDFUNDS. "
    "federalreserve.gov / fred.stlouisfed.org"
)
st.info(
    f"The Fed funds rate is the benchmark that sets the ceiling on what banks can earn. "
    f"At {current_fed_rate:.2f}%, a bank that fully passes this rate to depositors would offer a {current_fed_rate:.2f}% APY. "
    "In practice, most traditional banks pay a fraction of that and pocket the difference as profit margin. "
    "This dashboard measures exactly how much each bank shares with savers versus how much they keep."
)

# ── Terminology Glossary ──────────────────────────────────────────────────────
st.markdown("### 📖 Key Terms")
st.markdown("Familiarize yourself with these concepts before exploring the data.")

terms = [
    ("APY (Annual Percentage Yield)",
     "The annual interest rate a deposit earns. A 4.00% APY on $100,000 generates $4,000 per year."),
    ("Fed Funds Rate",
     "The Fed's benchmark rate. Banks earn more when it rises but are not required to pass any of that to depositors."),
    ("Pass-Through Rate (%)",
     "How much of the Fed's rate a bank shares with savers. 100% means full pass-through. Under 10% means the bank keeps almost everything."),
    ("Spread (%)",
     "The gap between the Fed rate and a bank's APY. A wider spread means more profit for the bank and less for the depositor."),
    ("Online vs. Traditional Bank",
     "Online banks like Marcus, Ally, and SoFi compete on rate. Traditional banks like Chase, BofA, and Wells Fargo compete on branch access and brand."),
    ("Fixed vs. Variable Rates",
     "Savings APYs are variable and move with the Fed. CD rates lock in at the time of deposit and hold for the full term."),
]

col_a, col_b = st.columns(2)
for i, (term, definition) in enumerate(terms):
    col = col_a if i % 2 == 0 else col_b
    with col:
        with st.container(border=True):
            st.markdown(f"**{term}**")
            st.caption(definition)

st.divider()

terms_confirmed = st.checkbox("I have read and understood the key terms above.")

if not terms_confirmed:
    st.stop()

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
        "apy_pct", "passthrough_pct"
    ]].copy()
    display_df["bank_type"] = display_df["bank_type"].str.capitalize()
    display_df["apy_pct"] = display_df["apy_pct"].astype(float).round(2)
    display_df["passthrough_pct"] = display_df["passthrough_pct"].astype(float).round(1)
    display_df = display_df.rename(columns={
        "bank_name": "Bank",
        "bank_type": "Type",
        "product_display_name": "Product",
        "apy_pct": "APY (%)",
        "passthrough_pct": "Pass-Through (%)",
    })

    def _color_apy(series):
        lo, hi = series.min(), series.max()
        out = []
        for v in series:
            ratio = (v - lo) / (hi - lo) if hi != lo else 0.5
            r = int(220 * (1 - ratio))
            g = int(180 * ratio + 40)
            out.append(f"background-color: rgb({r},{g},60)")
        return out

    st.dataframe(
        display_df.style.apply(_color_apy, subset=["APY (%)"]),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        "Banks at the top are paying depositors the most. "
        "Pass-Through shows how much of the Fed's rate each bank shares with savers — higher is better."
    )


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

    savings_df = df[df["product_name"] == "savings"].drop_duplicates("bank_name")
    online_avg = savings_df[savings_df["bank_type"] == "online"]["apy_pct"].astype(float).mean()
    trad_avg   = savings_df[savings_df["bank_type"] == "traditional"]["apy_pct"].astype(float).mean()

    fig = go.Figure()

    # Fed funds rate history
    fig.add_trace(go.Scatter(
        x=fred["date_day"],
        y=fred["rate_pct"],
        name="Fed Funds Rate",
        line=dict(color="black", width=3, dash="dash"),
    ))

    # Shaded band: where online banks sit today
    fig.add_hrect(
        y0=online_avg - 0.3, y1=online_avg + 0.3,
        fillcolor="#2ecc71", opacity=0.15, line_width=0,
        annotation_text=f"Online banks today (~{online_avg:.2f}% avg)",
        annotation_position="right",
    )

    # Shaded band: where traditional banks sit today
    fig.add_hrect(
        y0=0, y1=max(trad_avg + 0.05, 0.1),
        fillcolor="#e74c3c", opacity=0.15, line_width=0,
        annotation_text=f"Traditional banks today (~{trad_avg:.2f}% avg)",
        annotation_position="right",
    )

    # Annotate the 2022-2023 hiking cycle
    fig.add_vrect(
        x0="2022-03-01", x1="2023-07-31",
        fillcolor="orange", opacity=0.08, line_width=0,
        annotation_text="2022–2023 Fed Hiking Cycle (+5.25%)",
        annotation_position="top left",
    )

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Rate (%)",
        height=520,
        showlegend=True,
    )
    st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)
    col_a.success(
        f"Online banks (Marcus, Ally, SoFi) currently average {online_avg:.2f}% APY on savings. "
        "They tracked the Fed's rate hikes and their rates reflect it."
    )
    col_b.error(
        f"Traditional banks (Chase, BofA, Wells Fargo) currently average {trad_avg:.2f}% APY on savings. "
        "They did not raise deposit rates during the hiking cycle and remain near zero."
    )


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
        available_terms = sorted(df[df["product_name"] == "cd"]["term_months"].dropna().unique().astype(int).tolist())
        term_label_map = {6: "6-Month CD", 12: "1-Year CD", 36: "3-Year CD", 60: "5-Year CD"}
        term_options = [term_label_map.get(t, f"{t}-Month CD") for t in available_terms]
        term_label = st.selectbox("CD term", options=term_options)
        reverse_map = {v: k for k, v in term_label_map.items()}
        term_months = reverse_map.get(term_label, available_terms[0])

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
