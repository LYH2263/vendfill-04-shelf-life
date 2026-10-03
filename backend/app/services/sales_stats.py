"""近七日销量统计：货道页 / 销量页 / 补货单共用同一套口径。"""
from __future__ import annotations
from datetime import datetime, timedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.models import Sale

WINDOW_DAYS = 7

def sold_qty_since(db: Session, since: datetime, lane_ids: list[int] | None = None) -> dict[int, int]:
    """返回 {lane_id: 销量合计}，窗口内无销量的货道记 0。"""
    q = select(Sale.lane_id, func.coalesce(func.sum(Sale.qty), 0)).where(Sale.sold_at >= since)
    if lane_ids is not None:
        q = q.where(Sale.lane_id.in_(lane_ids))
    q = q.group_by(Sale.lane_id)
    return {int(lane_id): int(qty or 0) for lane_id, qty in db.execute(q).all()}

def sold_last_7d(db: Session, lane_ids: list[int] | None = None, *, now: datetime | None = None) -> dict[int, int]:
    now = now or datetime.utcnow()
    return sold_qty_since(db, now - timedelta(days=WINDOW_DAYS), lane_ids)
