with bankrate as (
    select
        bank_name,
        product_type,
        term_months,
        apy_pct,
        scrape_date,
        'bankrate'  as source_name
    from {{ source('raw', 'bankrate_rates') }}
),

big_four as (
    select
        bank_name,
        product_type,
        term_months,
        apy_pct,
        cast(scrape_date as date) as scrape_date,
        'seed'      as source_name
    from {{ ref('big_four_rates') }}
),

combined as (
    select * from bankrate
    union all
    select * from big_four
),

cleaned as (
    select
        bank_name,
        lower(trim(product_type))                          as product_type,
        term_months,
        round(apy_pct, 4)                                  as apy_pct,
        scrape_date,
        source_name,
        case
            when bank_name in ('JPMorgan Chase', 'Bank of America', 'Wells Fargo', 'Citibank')
                then 'traditional'
            else 'online'
        end                                                as bank_type
    from combined
    where apy_pct > 0
      and apy_pct < 15
)

select * from cleaned
