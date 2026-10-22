select s.source_file, s.sku, s.valid_from, s.raw_cost,
 case when p.sku is null then 'unknown_sku' else 'invalid_cost' end as reason
from {{ ref('stg_supplier_prices') }} s
left join (select distinct trim(sku) as sku from {{ source('raw','products') }}) p on s.sku=p.sku
where p.sku is null or s.unit_cost_sar is null or s.unit_cost_sar <= 0
