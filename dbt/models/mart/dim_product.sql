with products as (
    select distinct
        product_type,
        term_months
    from {{ ref('stg_bankrate_rates') }}
),

with_key as (
    select
        row_number() over (order by product_type, coalesce(term_months, 0)) as product_key,
        product_type                                                          as product_name,
        term_months,
        case
            when product_type = 'savings' then 'High-Yield Savings Account'
            when product_type = 'cd' and term_months = 3  then '3-Month CD'
            when product_type = 'cd' and term_months = 6  then '6-Month CD'
            when product_type = 'cd' and term_months = 12 then '1-Year CD'
            when product_type = 'cd' and term_months = 24 then '2-Year CD'
            when product_type = 'cd' and term_months = 36 then '3-Year CD'
            when product_type = 'cd' and term_months = 60 then '5-Year CD'
            else product_type
        end                                                                   as product_display_name
    from products
)

select * from with_key
