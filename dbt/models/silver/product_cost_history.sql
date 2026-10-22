with valid as (
 select s.* from {{ ref('stg_supplier_prices') }} s
 join (select distinct trim(sku) as sku from {{ source('raw','products') }}) p using(sku)
 where s.unit_cost_sar > 0
), winner as (
 select * from valid qualify row_number() over(partition by sku, valid_from order by source_file desc)=1
), changed as (
 select *, lag(unit_cost_sar) over(partition by sku order by valid_from) as previous_cost from winner
), versions as (
 select sku, cast(unit_cost_sar as double) as unit_cost_sar, valid_from
 from changed where previous_cost is null or previous_cost <> unit_cost_sar
), history as (
 select *, lead(valid_from) over(partition by sku order by valid_from) as valid_to from versions
)
select sku, unit_cost_sar, valid_from, valid_to, valid_to is null as is_current from history
