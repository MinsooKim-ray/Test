"""실거래가 기반 시세 추정·예측. 외부 라이브러리 없이 순수 계산만 한다.

방법 요약
- 지역 지수: 시군구 전체 거래의 ㎡당 가격 중위값(직전 3개월 묶음). 시장 전체 흐름을 나타낸다.
- 현재 추정 시세: 선택 평형의 최근 거래를 지역 지수로 현재 시점에 맞춰 보정한 뒤
  최근 거래일수록 크게(반감기 6개월) 가중 평균.
- 연 상승률: (단지 장기 추세 + 지역 최근 3년 추세) / 2, 연 -10% ~ +12% 로 제한.
- 예측 구간(80%): 지역 지수의 과거 1년 변동성과 단지 내 거래가 편차로 계산.
"""
import math
from collections import defaultdict
from statistics import median, pstdev

Z80 = 1.2816
G_MIN, G_MAX = -0.10, 0.12
HORIZONS = (12, 24, 36)


def mi_of(ym):
    """YYYYMM -> 연속 월 번호."""
    return (ym // 100) * 12 + ym % 100 - 1


def ym_of(mi):
    return (mi // 12) * 100 + mi % 12 + 1


def region_index(rows, end_mi):
    """rows: (mi, ㎡당 가격). 직전 3개월 묶음 중위값이라 미래 정보를 쓰지 않는다."""
    by = defaultdict(list)
    for mi, ppa in rows:
        by[mi].append(ppa)
    if not by:
        return {}
    idx, last = {}, None
    for m in range(min(by), end_mi + 1):
        pool = by.get(m, []) + by.get(m - 1, []) + by.get(m - 2, [])
        if len(pool) >= 5:
            last = median(pool)
        if last is not None:
            idx[m] = last
    return idx


def _slope(pts):
    """(x, y) 최소제곱 기울기. 점이 부족하면 None."""
    n = len(pts)
    if n < 2:
        return None
    mx = sum(x for x, _ in pts) / n
    my = sum(y for _, y in pts) / n
    sxx = sum((x - mx) ** 2 for x, _ in pts)
    if sxx == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in pts) / sxx


def forecast(trades, idx, as_of):
    """trades: 선택 평형의 (mi, 가격[만원]) 목록(해제 제외). as_of 시점 기준 예측."""
    past = [(m, p) for m, p in trades if m <= as_of]
    if len(past) < 3:
        return None
    for window in (12, 24, 36, None):
        rec = [(m, p) for m, p in past if window is None or m > as_of - window]
        if len(rec) >= 3:
            break
    i0 = idx.get(as_of)
    xs, ws = [], []
    for m, p in rec:
        adj = math.log(i0 / idx[m]) if i0 and idx.get(m) else 0.0
        xs.append(math.log(p) + adj)
        ws.append(0.5 ** ((as_of - m) / 6))
    wsum = sum(ws)
    mu = sum(w * x for w, x in zip(ws, xs)) / wsum
    spread = max(math.sqrt(sum(w * (x - mu) ** 2 for w, x in zip(ws, xs)) / wsum), 0.03)

    ipts = [(m, math.log(v)) for m, v in idx.items() if m <= as_of]
    g_region = (_slope(ipts) or 0.0) * 12
    by = defaultdict(list)
    for m, p in past:
        by[m].append(p)
    cpts = [(m, math.log(median(v))) for m, v in by.items()]
    span = max(by) - min(by)
    g_long = _slope(cpts) * 12 if len(cpts) >= 8 and span >= 24 else g_region
    rpts = [(m, y) for m, y in ipts if m > as_of - 36]
    g_recent = _slope(rpts) * 12 if len(rpts) >= 12 else g_long
    g = min(max((g_long + g_recent) / 2, G_MIN), G_MAX)

    yoy = [math.log(idx[m] / idx[m - 12]) for m in idx if m <= as_of and m - 12 in idx]
    sigma = max(pstdev(yoy), 0.04) if len(yoy) >= 6 else 0.08

    def at(h):
        half = Z80 * math.sqrt(sigma ** 2 * h / 12 + spread ** 2)
        c = mu + g * h / 12
        return {"months": h, "base": round(math.exp(c)),
                "low": round(math.exp(c - half)), "high": round(math.exp(c + half))}

    return {"now": at(0), "forecasts": [at(h) for h in HORIZONS],
            "g": g, "g_long": g_long, "g_recent": g_recent, "sigma": sigma,
            "n_used": len(rec), "window": window}


def backtest(trades, idx, now_mi):
    """과거 여러 시점에서 같은 방법으로 1년 뒤를 예측했을 때의 실제 오차."""
    if not trades:
        return None
    first = min(m for m, _ in trades)
    errs, inside = [], 0
    for a in range(now_mi - 12, first + 23, -6):
        f = forecast(trades, idx, a)
        actual = [p for m, p in trades if a + 10 <= m <= a + 14]
        if not f or not actual:
            continue
        act, pred = median(actual), f["forecasts"][0]
        errs.append(abs(pred["base"] - act) / act)
        inside += pred["low"] <= act <= pred["high"]
    if not errs:
        return None
    return {"n": len(errs), "mape": sum(errs) / len(errs), "coverage": inside / len(errs)}


def analyze(region_rows, trades, now_mi):
    """region_rows: 시군구 전체 (mi, ㎡당 가격). trades: 선택 평형 (mi, 가격)."""
    idx = region_index(region_rows, now_mi)
    f = forecast(trades, idx, now_mi)
    if not f:
        return None
    by = defaultdict(list)
    for m, p in trades:
        by[m].append(p)
    f["monthly"] = [{"ym": ym_of(m), "median": round(median(by[m]))} for m in sorted(by)]
    f["backtest"] = backtest(trades, idx, now_mi)
    return f
