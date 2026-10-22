with cleaned as (
 select trim(sku) as sku, cast(valid_from as date) as valid_from, raw_cost, source_file,
 translate(replace(replace(trim(raw_cost), '٫', '.'), ',', '.'),
 '٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789') as cost_text
 from {{ source('raw', 'supplier_prices') }}
)
select sku, valid_from, raw_cost, source_file,
 round(try_cast(cost_text as double), 2) as unit_cost_sar
from cleaned
