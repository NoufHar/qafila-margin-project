with eligible as (
 select i.order_id, i.line_no, trim(p.sku) as sku, p.category, s.city,
 cast(o.created_at as timestamp) + interval '3 hours' as local_time,
 i.quantity, round(i.quantity * i.unit_price - i.discount, 2) as revenue
 from {{ source('raw','order_items') }} i
 join {{ source('raw','orders') }} o on i.order_id=o.order_id
 join {{ source('raw','products') }} p on i.product_id=p.product_id
 join {{ source('raw','stores') }} s on o.store_id=s.store_id
 where o.status='delivered' and i.quantity>0
 and cast(cast(o.created_at as timestamp) + interval '3 hours' as date)>=date '2026-08-31'
), costed as (
 select e.*, h.unit_cost_sar,
 cast(extract(week from e.local_time) as integer) as iso_week
 from eligible e left join {{ ref('product_cost_history') }} h
 on e.sku=h.sku and cast(e.local_time as date)>=h.valid_from
 and (cast(e.local_time as date)<h.valid_to or h.valid_to is null)
), totals as (
 select iso_week, city, category, cast(count(*) as integer) as lines,
 cast(round(sum(revenue),2) as double) as revenue_sar,
 cast(round(sum(case when unit_cost_sar is not null then revenue else 0 end),2) as double) as costed_revenue_sar,
 cast(round(sum(coalesce(quantity*unit_cost_sar,0)),2) as double) as cost_sar,
 cast(sum(case when unit_cost_sar is null then 1 else 0 end) as integer) as uncosted_lines
 from costed group by 1,2,3
)
select *, cast(round(costed_revenue_sar-cost_sar,2) as double) as margin_sar from totals
