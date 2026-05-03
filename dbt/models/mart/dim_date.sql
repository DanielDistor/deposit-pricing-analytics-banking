with fred_dates as (
    select distinct date_day
    from {{ ref('stg_fred_observations') }}
    where series_id = 'FEDFUNDS'
),

with_attrs as (
    select
        date_day,
        year(date_day)    as year,
        month(date_day)   as month,
        quarter(date_day) as quarter,
        case
            when date_day between '2022-03-01' and '2023-07-31' then 'hiking'
            when date_day between '2024-09-01' and '2025-01-31' then 'cutting'
            else 'hold'
        end               as fed_rate_cycle
    from fred_dates
)

select * from with_attrs
