from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Lane, Sale
from app.services.fill_engine import build_fill_lines
from app.services.sales_stats import sold_last_7d

router = APIRouter(prefix="/sales", tags=["sales"])


def lane_sales_view(db: Session) -> list[dict]:
    """每道近七日日均与由此算出的可补上限——与货道页、补货单同一套口径。"""
    lanes = db.scalars(select(Lane).order_by(Lane.slot_no)).all()
    sold = sold_last_7d(db, [l.id for l in lanes])
    payload = [{"id": l.id, "slot_no": l.slot_no, "sku_name": l.sku_name,
                "capacity": l.capacity, "stock": l.stock, "in_transit": l.in_transit,
                "sellable_days": l.sellable_days, "sold_7d": sold.get(l.id, 0)} for l in lanes]
    return [
        {"lane_id": x.lane_id, "slot_no": x.slot_no, "sku_name": x.sku_name,
         "sold_7d": x.sold_7d, "daily_avg": x.daily_avg,
         "sellable_days": x.sellable_days, "gap": x.gap,
         "expiry_cap": x.expiry_cap, "refill_cap": x.refill_cap}
        for x in build_fill_lines(payload)
    ]


@router.get("")
def list_sales(db: Session = Depends(get_db)):
    lanes = {l.id: l for l in db.scalars(select(Lane)).all()}
    rows = db.scalars(select(Sale).order_by(Sale.sold_at.desc())).all()
    return {
        "rows": [{"id": r.id, "lane_id": r.lane_id,
                  "slot_no": lanes[r.lane_id].slot_no if r.lane_id in lanes else "",
                  "sku_name": lanes[r.lane_id].sku_name if r.lane_id in lanes else "",
                  "qty": r.qty, "sold_at": r.sold_at.isoformat()} for r in rows],
        "lanes": lane_sales_view(db),
    }
