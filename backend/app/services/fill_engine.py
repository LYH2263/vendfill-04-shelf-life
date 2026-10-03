"""Vending refill engine.

gap = capacity - stock - in_transit；补量先按缺口（或期望量）封顶、不为负。
当货道登记了临期可售天数时，再以「近七日日均销量 × 可售天数（向下取整）」
二次封顶；因临期封顶而少补时状态为临期可售不足，不得记为已满仓。
可售天数留空（None）表示不启用临期封顶，与只按缺口补货相同。
"""
from __future__ import annotations
from dataclasses import asdict, dataclass

STATUS_NEED_FILL = "need_fill"
STATUS_FULL = "full"
STATUS_OVERBOOKED = "overbooked"
STATUS_EXPIRY_LIMITED = "expiry_limited"

REASON_NEED_FILL = "待补货"
REASON_FULL = "已满仓"
REASON_OVERBOOKED = "已超占"
REASON_EXPIRY = "临期可售不足"

@dataclass
class FillLine:
    lane_id: int
    slot_no: str
    sku_name: str
    capacity: int
    stock: int
    in_transit: int
    gap: int
    sellable_days: int | None       # None=不启用临期封顶
    sold_7d: int                    # 近七日销量合计
    daily_avg: float                # 日均 = 近七日合计 / 7（销量为 0 则为 0）
    expiry_cap: int | None          # floor(日均 × 可售天数)；None=不启用
    refill_cap: int                 # 实际可补上限：启用时 min(缺口, expiry_cap)，否则 max(缺口,0)
    fill_qty: int
    status: str  # need_fill | full | overbooked | expiry_limited
    reason: str

def compute_gap(capacity: int, stock: int, in_transit: int) -> int:
    return capacity - stock - in_transit

def daily_avg_from_sold(sold_7d: int) -> float:
    """近七日销量合计除以 7；销量为 0 则日均为 0。"""
    return (sold_7d or 0) / 7

def expiry_cap_from_sold(sold_7d: int, sellable_days: int | None) -> int | None:
    """floor(日均 × 可售天数)。用整数除法 floor(合计×天数/7) 与该口径严格等价。"""
    if sellable_days is None:
        return None
    return (int(sold_7d or 0) * int(sellable_days)) // 7

def build_fill_lines(lanes: list[dict], requested: dict[int, int] | None = None) -> list[FillLine]:
    """requested 为每道期望补量；先受缺口封顶，启用临期时再受日均×天数封顶。"""
    lines: list[FillLine] = []
    for lane in lanes:
        gap = compute_gap(int(lane["capacity"]), int(lane["stock"]), int(lane["in_transit"]))
        sellable_days = lane.get("sellable_days")
        if sellable_days is not None:
            sellable_days = int(sellable_days)
        sold_7d = int(lane.get("sold_7d", 0) or 0)
        daily_avg = daily_avg_from_sold(sold_7d)
        expiry_cap = expiry_cap_from_sold(sold_7d, sellable_days)

        if gap < 0:
            status, reason, fill = STATUS_OVERBOOKED, REASON_OVERBOOKED, 0
            refill_cap = 0
        elif gap == 0:
            status, reason, fill = STATUS_FULL, REASON_FULL, 0
            refill_cap = 0
        else:
            desire = gap if requested is None else int(requested.get(lane["id"], gap))
            gap_fill = max(0, min(desire, gap))
            if expiry_cap is None:
                refill_cap = gap
                fill = gap_fill
                status, reason = STATUS_NEED_FILL, REASON_NEED_FILL
            else:
                refill_cap = min(gap, expiry_cap)
                fill = max(0, min(gap_fill, refill_cap))
                # 只因临期上限被压低而少补（含补量被压到 0）才标记临期可售不足
                if expiry_cap < gap_fill:
                    status, reason = STATUS_EXPIRY_LIMITED, REASON_EXPIRY
                else:
                    status, reason = STATUS_NEED_FILL, REASON_NEED_FILL
        lines.append(FillLine(
            lane_id=lane["id"], slot_no=lane["slot_no"], sku_name=lane["sku_name"],
            capacity=lane["capacity"], stock=lane["stock"], in_transit=lane["in_transit"],
            gap=gap, sellable_days=sellable_days, sold_7d=sold_7d,
            daily_avg=round(daily_avg, 4), expiry_cap=expiry_cap, refill_cap=refill_cap,
            fill_qty=fill, status=status, reason=reason,
        ))
    return lines

def summarize(lines: list[FillLine]) -> dict:
    return {
        "total_fill": sum(l.fill_qty for l in lines),
        "need_fill_count": sum(1 for l in lines if l.status == STATUS_NEED_FILL),
        "full_count": sum(1 for l in lines if l.status == STATUS_FULL),
        "overbooked_count": sum(1 for l in lines if l.status == STATUS_OVERBOOKED),
        "expiry_limited_count": sum(1 for l in lines if l.status == STATUS_EXPIRY_LIMITED),
        "lines": [asdict(l) for l in lines],
    }
