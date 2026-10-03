from datetime import datetime, timedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.models import Lane, Location, Sale

def seed_if_empty(db: Session) -> None:
    if (db.scalar(select(func.count()).select_from(Location)) or 0) > 0:
        return
    loc = Location(code="VM-01", name="地铁口 A 点位", address="城东地铁 1 号口")
    db.add(loc); db.flush()
    # (槽位, 商品, 容量, 库存, 在途, 临期可售天数[None=不启用封顶])
    lanes = [
        ("A1", "矿泉水", 20, 5, 0, 2),
        ("A2", "可乐", 18, 18, 0, None),
        ("B1", "薯片", 12, 3, 2, None),
        ("B2", "巧克力", 15, 10, 5, None),
        ("C1", "能量棒", 10, 0, 0, None),
        ("C2", "口香糖", 24, 24, 2, None),
    ]
    lane_ids = []
    for slot, sku, cap, stock, transit, sellable_days in lanes:
        lane = Lane(location_id=loc.id, slot_no=slot, sku_name=sku, capacity=cap,
                    stock=stock, in_transit=transit, sellable_days=sellable_days)
        db.add(lane); db.flush()
        lane_ids.append(lane.id)
    now = datetime.utcnow()
    # A1：近七日每日出货 2，合计 14 → 日均 2；可售天数 2 → 可补上限 4，小于缺口 15
    a1 = lane_ids[0]
    for d in range(7):
        db.add(Sale(lane_id=a1, qty=2, sold_at=now - timedelta(days=d)))
    # 其余货道各一条近期出货
    for i, lid in enumerate(lane_ids[1:], start=1):
        db.add(Sale(lane_id=lid, qty=2 + i, sold_at=now - timedelta(hours=i)))
    db.commit()
