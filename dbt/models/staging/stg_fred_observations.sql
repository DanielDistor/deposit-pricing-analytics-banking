with source as (
    select * from {{ source('raw', 'fred_observations') }}
),

cleaned as (
    select
        series_id,
        observation_date                           as date_day,
        value                                      as rate_pct,
        case series_id
            when 'FEDFUNDS'  then 'Fed Funds Rate (Monthly Avg)'
            when 'DFF'       then 'Fed Funds Rate (Daily)'
            when 'TB3MS'     then '3-Month Treasury Bill'
            when 'GS1'       then '1-Year Treasury'
            when 'GS2'       then '2-Year Treasury'
            when 'GS5'       then '5-Year Treasury'
            when 'GS10'      then '10-Year Treasury'
            when 'DPCREDIT'  then 'Discount Window Rate'
            else series_id
        end                                        as series_name,
        loaded_at
    from source
    where value is not null
)

select * from cleaned
