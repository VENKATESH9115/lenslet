from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from ..db import q
from ..services import expire_unpaid

router = APIRouter(prefix="/api", tags=["catalog"])

# state = what a customer sees for the requested window (or "right now" when no window is given)
STATE = """case when e.status <> 'available' then e.status
  when exists (select 1 from booking_items bi where bi.equipment_id = e.id and bi.active
               and bi.period && tstzrange(coalesce(%(s)s::timestamptz, now()), coalesce(%(e)s::timestamptz, now() + interval '1 minute'), '[)'))
  then 'booked' else 'available' end"""
SORTS = {"popular": "e.review_count desc", "price_asc": "e.price_day asc", "price_desc": "e.price_day desc", "newest": "e.created_at desc"}


@router.get("/categories")
def categories():
    return q("select slug,name from categories order by sort")


@router.get("/gear")
def gear(start: datetime | None = None, end: datetime | None = None, category: str | None = None,
         search: str | None = Query(None, max_length=60), brand: str | None = None, max_price: int | None = None,
         available_only: bool = False, sort: str = "popular"):
    expire_unpaid()
    rows = q(f"""select * from (
        select e.id,e.slug,e.brand,e.name,e.short_spec,e.price_day,e.deposit,e.rating,e.review_count,e.includes,
               c.slug category, c.name category_name, {STATE} as state
        from equipment e join categories c on c.id = e.category_id
        where e.status <> 'archived'
          and (%(cat)s::text is null or c.slug = %(cat)s)
          and (%(q)s::text is null or e.name ilike '%%' || %(q)s || '%%' or e.brand ilike '%%' || %(q)s || '%%')
          and (%(brand)s::text is null or e.brand = %(brand)s)
          and (%(mp)s::int is null or e.price_day <= %(mp)s * 100)
        order by {SORTS.get(sort, SORTS['popular'])}) t
      where (not %(av)s or state = 'available')""",
             {"s": start, "e": end, "cat": category, "q": search, "brand": brand, "mp": max_price, "av": available_only})
    return rows


@router.get("/gear/{slug}")
def gear_detail(slug: str):
    e = q("""select e.*, c.slug category, c.name category_name from equipment e join categories c on c.id=e.category_id
             where e.slug=%s and e.status <> 'archived'""", (slug,), one=True)
    if not e:
        raise HTTPException(404, "We could not find that item.")
    e.pop("serial_no", None)
    e["busy"] = q("select lower(period) start_at, upper(period) end_at from booking_items where equipment_id=%s and active and upper(period) > now() order by 1", (e["id"],))
    return e
