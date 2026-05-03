with banks as (
    select distinct
        bank_name,
        bank_type
    from {{ ref('stg_bankrate_rates') }}
),

with_key as (
    select
        row_number() over (order by bank_name)  as bank_key,
        bank_name,
        bank_type
    from banks
)

select * from with_key
