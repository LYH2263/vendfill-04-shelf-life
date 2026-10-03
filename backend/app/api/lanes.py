from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Lane
from app.services.fill_engine import build_fill_lines
from app.services.sales_stats import sold_last_7d

router = APIRouter(prefix="/lanes", tags=["lanes"])


class SellableDaysIn(BaseModel):
    # None / 留空表示不启用临期封顶
    sellable_days: int | None = None


def lane_view(db: Session, location_id: int | None) -> list[dict]:
    """货道页与补货单共用：近七日日均 + 可售天数 + 可补上限，同一套口径。"""
    q = select(Lane).order_by(Lane.slot_no)
    if location_id is not None:
        q = q.where(Lane.location_id == location_id)
    lanes = db.scalars(q).all()
    sold = sold_last_7d(db, [l.id for l in lanes])
    payload = [{"id": l.id, "slot_no": l.slot_no, "sku_name": l.sku_name,
                "capacity": l.capacity, "stock": l.stock, "in_transit": l.in_transit,
                "sellable_days": l.sellable_days, "sold_7d": sold.get(l.id, 0)} for l in lanes]
    out = []
    for l, line in zip(lanes, build_fill_lines(payload)):
        d = {
            "id": l.id, "location_id": l.location_id, "slot_no": l.slot_no, "sku_name": l.sku_name,
            "capacity": l.capacity, "stock": l.stock, "in_transit": l.in_transit, "gap": line.gap,
            "fill_pct": round(l.stock / l.capacity * 100, 1) if l.capacity else 0,
            "sellable_days": line.sellable_days, "sold_7d": line.sold_7d,
            "daily_avg": line.daily_avg, "expiry_cap": line.expiry_cap,
            "refill_cap": line.refill_cap,
        }
        out.append(d)
    return out


@router.get("")
def list_lanes(location_id: int | None = None, db: Session = Depends(get_db)):
    return lane_view(db, location_id)


@router.put("/{lane_id}")
def update_lane(lane_id: int, body: SellableDaysIn, db: Session = Depends(get_db)):
    lane = db.get(Lane, lane_id)
    if not lane:
        raise HTTPException(404, "货道不存在")
    days = body.sellable_days
    if days is not None and days <= 0:
        # 天数 ≤0 拒绝保存，三页保持改前
        raise HTTPException(400, "临期可售天数必须大于 0；留空表示不启用临期封顶")
    lane.sellable_days = days
    db.commit()
    return next(v for v in lane_view(db, lane.location_id) if v["id"] == lane_id)
