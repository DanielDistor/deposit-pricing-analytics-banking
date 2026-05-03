with rates as (
    select * from {{ ref('stg_bankrate_rates') }}
),

banks as (
    select * from {{ ref('dim_bank') }}
),

products as (
    select * from {{ ref('dim_product') }}
),

latest_fed as (
    select rate_pct as fed_funds_rate
    from {{ ref('stg_fred_observations') }}
    where series_id = 'FEDFUNDS'
    order by date_day desc
    limit 1
),

fact as (
    select
        b.bank_key,
        p.product_key,
        r.scrape_date,
        r.apy_pct,
        lf.fed_funds_rate,
        round(lf.fed_funds_rate - r.apy_pct, 4)                          as spread_pct,
        round(r.apy_pct / nullif(lf.fed_funds_rate, 0) * 100, 2)         as passthrough_pct,
        r.source_name
    from rates r
    left join banks b
        on b.bank_name = r.bank_name
    left join products p
        on p.product_name = r.product_type
       and coalesce(p.term_months, -1) = coalesce(r.term_months, -1)
    cross join latest_fed lf
)

select * from fact
