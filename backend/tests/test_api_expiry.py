from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import Lane
from app.services.seed import seed_if_empty
from fastapi.testclient import TestClient


def _client_with_seed():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    db = TestSession()
    seed_if_empty(db)
    a1 = db.scalar(select(Lane).where(Lane.slot_no == "A1"))
    db.close()

    def _override():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    client = TestClient(app)  # 不进入 with，避免 lifespan 连接真实 Postgres
    return client, a1.id


def test_seed_a1_sellable_days_and_cap():
    client, a1_id = _client_with_seed()
    # 种子：A1 可售天数 2，近 7 日每日 2 → 日均 2 → 上限 4 < 缺口 15
    run = client.post("/api/refills/run?location_id=1").json()
    a1_line = next(l for l in run["lines"] if l["lane_id"] == a1_id)
    assert a1_line["sellable_days"] == 2
    assert a1_line["sold_7d"] == 14
    assert a1_line["daily_avg"] == 2
    assert a1_line["gap"] == 15
    assert a1_line["expiry_cap"] == 4
    assert a1_line["refill_cap"] == 4
    assert a1_line["fill_qty"] == 4  # 补货单补量等于上限
    assert a1_line["status"] == "expiry_limited"
    assert a1_line["reason"] == "临期可售不足"


def test_sales_page_cap_matches_order():
    client, a1_id = _client_with_seed()
    sales = client.get("/api/sales").json()
    a1 = next(l for l in sales["lanes"] if l["lane_id"] == a1_id)
    run = client.post("/api/refills/run?location_id=1").json()
    a1_line = next(l for l in run["lines"] if l["lane_id"] == a1_id)
    # 销量页展示的上限与补货单一致
    assert a1["daily_avg"] == a1_line["daily_avg"] == 2
    assert a1["refill_cap"] == a1_line["refill_cap"] == 4
    assert a1_line["fill_qty"] <= a1["refill_cap"]


def test_lanes_page_shares_same_cap():
    client, a1_id = _client_with_seed()
    lanes = client.get("/api/lanes").json()
    a1 = next(l for l in lanes if l["id"] == a1_id)
    assert a1["sellable_days"] == 2
    assert a1["daily_avg"] == 2
    assert a1["refill_cap"] == 4


def test_non_positive_days_rejected_and_pages_unchanged():
    client, a1_id = _client_with_seed()
    for bad in (0, -3):
        r = client.put(f"/api/lanes/{a1_id}", json={"sellable_days": bad})
        assert r.status_code == 400
    # 三页保持改前：仍为天数 2、上限 4、补量 4
    saved = client.get("/api/lanes").json()
    a1 = next(l for l in saved if l["id"] == a1_id)
    assert a1["sellable_days"] == 2
    run = client.post("/api/refills/run?location_id=1").json()
    assert next(l for l in run["lines"] if l["lane_id"] == a1_id)["fill_qty"] == 4


def test_blank_days_disables_cap():
    client, a1_id = _client_with_seed()
    r = client.put(f"/api/lanes/{a1_id}", json={"sellable_days": None})
    assert r.status_code == 200
    assert r.json()["sellable_days"] is None
    run = client.post("/api/refills/run?location_id=1").json()
    a1_line = next(l for l in run["lines"] if l["lane_id"] == a1_id)
    assert a1_line["expiry_cap"] is None
    assert a1_line["fill_qty"] == 15  # 回退为只按缺口补
