from app.services.fill_engine import build_fill_lines, compute_gap, summarize, daily_avg_from_sold


def _lane(**kw):
    base = {"id": 1, "slot_no": "A1", "sku_name": "水", "capacity": 20, "stock": 5, "in_transit": 0}
    base.update(kw)
    return base


def test_gap_basic():
    assert compute_gap(20, 5, 0) == 15
    assert compute_gap(20, 10, 5) == 5


def test_no_negative_fill():
    lines = build_fill_lines([_lane(capacity=10, stock=12)])
    assert lines[0].fill_qty == 0
    assert lines[0].status == "overbooked"


def test_cap_by_gap():
    lines = build_fill_lines([_lane()], requested={1: 100})
    assert lines[0].fill_qty == 15
    assert lines[0].gap == 15


def test_full_zero_fill():
    s = summarize(build_fill_lines([_lane(capacity=10, stock=8, in_transit=2)]))
    assert s["full_count"] == 1
    assert s["total_fill"] == 0


def test_blank_days_disables_expiry_cap():
    # 留空表示不启用临期封顶，与只按缺口补相同
    lines = build_fill_lines([_lane(sellable_days=None, sold_7d=0)])
    assert lines[0].expiry_cap is None
    assert lines[0].refill_cap == 15
    assert lines[0].fill_qty == 15
    assert lines[0].status == "need_fill"


def test_daily_avg_zero_sales():
    assert daily_avg_from_sold(0) == 0
    lines = build_fill_lines([_lane(sellable_days=2, sold_7d=0)])
    assert lines[0].daily_avg == 0
    assert lines[0].expiry_cap == 0
    assert lines[0].refill_cap == 0
    assert lines[0].fill_qty == 0
    # 少补原因必须是临期可售不足，不得写成已满仓
    assert lines[0].status == "expiry_limited"
    assert lines[0].reason == "临期可售不足"


def test_expiry_cap_floors_daily_times_days():
    # 近7日合计 15 → 日均 15/7；天数 2 → floor(30/7)=4，小于缺口 15
    lines = build_fill_lines([_lane(sellable_days=2, sold_7d=15)])
    assert lines[0].daily_avg == round(15 / 7, 4)
    assert lines[0].expiry_cap == 4
    assert lines[0].refill_cap == 4
    assert lines[0].fill_qty == 4
    assert lines[0].status == "expiry_limited"
    assert lines[0].reason == "临期可售不足"


def test_expiry_cap_not_binding_when_above_gap():
    # 日均×天数 >= 缺口时按缺口补，仍标记为待补货
    lines = build_fill_lines([_lane(sellable_days=30, sold_7d=70)])
    assert lines[0].expiry_cap == 300
    assert lines[0].fill_qty == 15
    assert lines[0].status == "need_fill"


def test_requested_cannot_break_expiry_cap():
    lines = build_fill_lines([_lane(sellable_days=2, sold_7d=14)], requested={1: 100})
    assert lines[0].gap == 15
    assert lines[0].expiry_cap == 4
    assert lines[0].refill_cap == 4
    assert lines[0].fill_qty == 4


def test_full_lane_not_marked_expiry():
    lines = build_fill_lines([_lane(capacity=10, stock=10, in_transit=0, sellable_days=1, sold_7d=70)])
    assert lines[0].status == "full"
    assert lines[0].reason == "已满仓"
    assert lines[0].fill_qty == 0
