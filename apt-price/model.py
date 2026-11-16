"""실거래가 기반 시세 추정·예측. 외부 라이브러리 없이 순수 계산만 한다.

방법 요약
- 지역 지수: 시군구 전체 거래의 ㎡당 가격 중위값(직전 3개월 묶음). 시장 전체 흐름을 나타낸다.
- 특이 거래 제외: 같은 단지·평형의 앞뒤 6개월 거래(지역 지수로 시점 보정)와 25% 넘게 차이 나는 거래.
- 현재 추정 시세: 선택 평형의 최근 거래를 지역 지수로 현재 시점에 맞춰 보정한 뒤
  최근 거래일수록 크게(반감기 6개월) 가중 평균.
- 예측 중심값: 향후 1년은 지역의 최근 12개월 시세 변화율(연 -10% ~ +12% 로 제한)을 적용하고,
  그 이후는 방향을 예측하지 않고 1년 뒤 수준을 유지한다.
  (마포구·해운대구 실데이터 검증에서 추세를 2~3년 연장하면 "변화 없음" 가정보다 오차가 컸다.)
- 예측 구간(80%): 지역 지수의 과거 1년 변동성과 단지 내 거래가 편차로 기본 폭을 잡은 뒤,
  과거 시점 검증에서 실제로 빗나간 정도에 맞춰 기간별로 폭을 넓힌다(배율 k, 1 미만으로 좁히지는 않음).
"""
import math
from collections import defaultdict
from statistics import median, pstdev

Z80 = 1.2816
G_MIN, G_MAX = -0.10, 0.12
HORIZONS = (12, 24, 36)
OUTLIER_LOG = 0.25  # 주변 거래 중위값 대비 로그 차이 한도(약 -22% / +28%)
K_DEFAULT = 1.5     # 지역 보정값을 못 구할 때 쓰는 배율
K_PRIOR_N = 5       # 단지 자체 검증 시점이 적을 때 지역 배율 쪽으로 당기는 가중


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


def outlier_flags(trades, idx):
    """trades: (mi, 가격). 각 거래가 특이 거래인지 여부 목록.
    앞뒤 6개월의 다른 거래가 5건 이상일 때만 판정한다."""
    rel = [math.log(p / idx[m]) if m in idx else None for m, p in trades]
    flags = []
    for i, (m, _) in enumerate(trades):
        near = [r for j, ((n, _), r) in enumerate(zip(trades, rel))
                if j != i and r is not None and abs(n - m) <= 6]
        flags.append(rel[i] is not None and len(near) >= 5
                     and abs(rel[i] - median(near)) > OUTLIER_LOG)
    return flags


def drop_outliers(trades, idx):
    return [t for t, bad in zip(trades, outlier_flags(trades, idx)) if not bad]


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


def forecast(trades, idx, as_of, k=None):
    """trades: 선택 평형의 (mi, 가격[만원]) 목록(해제·특이 거래 제외). as_of 시점 기준 예측.
    k: {기간(월): 구간 폭 배율}. 현재 시세 구간에는 적용하지 않는다."""
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

    # 향후 1년 변화율: 지역의 최근 12개월 변화. 지수가 1년치가 안 되면 전체 기간 추세.
    if i0 and idx.get(as_of - 12):
        g = math.log(i0 / idx[as_of - 12])
    else:
        g = (_slope([(m, math.log(v)) for m, v in idx.items() if m <= as_of]) or 0.0) * 12
    g = min(max(g, G_MIN), G_MAX)

    yoy = [math.log(idx[m] / idx[m - 12]) for m in idx if m <= as_of and m - 12 in idx]
    sigma = max(pstdev(yoy), 0.04) if len(yoy) >= 6 else 0.08

    widest = 0.0

    def at(h):
        nonlocal widest
        sd = math.sqrt(sigma ** 2 * h / 12 + spread ** 2)
        half = Z80 * sd * ((k or {}).get(h, 1.0) if h else 1.0)
        if h:  # 기간별 배율이 달라도 먼 미래의 구간이 더 좁아지지는 않게 한다
            half = widest = max(half, widest)
        c = mu + g * min(h, 12) / 12
        return {"months": h, "sd": sd, "base": round(math.exp(c)),
                "low": round(math.exp(c - half)), "high": round(math.exp(c + half))}

    return {"now": at(0), "forecasts": [at(h) for h in HORIZONS],
            "g": g, "sigma": sigma, "n_used": len(rec), "window": window}


def backtest(trades, idx, now_mi):
    """과거 여러 시점에서 같은 방법으로 예측했을 때의 실제 오차.
    mape/n 은 1년 뒤 기준, resid 는 기간별 표준화 잔차(기본 구간 폭 대비 빗나간 정도)."""
    if not trades:
        return None
    first = min(m for m, _ in trades)
    errs, resid = [], {h: [] for h in HORIZONS}
    for a in range(now_mi - 12, first + 23, -6):
        f = forecast(trades, idx, a)
        if not f:
            continue
        for pred in f["forecasts"]:
            h = pred["months"]
            actual = [p for m, p in trades if a + h - 2 <= m <= a + h + 2]
            if not actual:
                continue
            act = median(actual)
            resid[h].append(math.log(act / pred["base"]) / pred["sd"])
            if h == 12:
                errs.append(abs(pred["base"] - act) / act)
    if not errs:
        return None
    return {"n": len(errs), "mape": sum(errs) / len(errs), "resid": resid}


def region_k(groups, idx, now_mi):
    """지역 내 여러 단지·평형의 검증 잔차를 모아, 80% 구간이 실제로 80%를 덮게 하는 기간별 배율.
    groups: [(mi, 가격) 목록, ...]. 반환 {기간: (k, 잔차 수)} (잔차 30개 미만인 기간은 빠짐)."""
    pool = {h: [] for h in HORIZONS}
    for trades in groups:
        bt = backtest(drop_outliers(trades, idx), idx, now_mi)
        if bt:
            for h in HORIZONS:
                pool[h] += [abs(r) for r in bt["resid"][h]]
    out = {}
    for h, resid in pool.items():
        if len(resid) >= 30:
            resid.sort()
            q80 = resid[min(len(resid) - 1, int(0.8 * len(resid)))]
            out[h] = (max(1.0, q80 / Z80), len(resid))
    return out


def band_k(resid, prior):
    """단지 자체 잔차와 지역 배율을 섞은 최종 배율. 좁히는 방향(1 미만)으로는 쓰지 않는다."""
    ss = sum(r * r for r in resid) + K_PRIOR_N * prior ** 2
    return max(1.0, math.sqrt(ss / (len(resid) + K_PRIOR_N)))


def analyze(region_rows, trades, now_mi, calib=None, idx=None):
    """region_rows: 시군구 전체 (mi, ㎡당 가격). trades: 선택 평형 (mi, 가격).
    calib: region_k() 결과. 없는 기간은 K_DEFAULT 를 지역 배율로 쓴다.
    idx: 이미 구한 지역 지수가 있으면 넘겨서 다시 계산하지 않는다."""
    calib = calib or {}
    if idx is None:
        idx = region_index(region_rows, now_mi)
    flags = outlier_flags(trades, idx)
    trades = [t for t, bad in zip(trades, flags) if not bad]
    bt = backtest(trades, idx, now_mi)
    resid = bt.pop("resid") if bt else {h: [] for h in HORIZONS}
    k = {h: band_k(resid[h], calib[h][0] if h in calib else K_DEFAULT) for h in HORIZONS}
    f = forecast(trades, idx, now_mi, k)
    if not f:
        return None
    if bt:  # 보정된 1년 구간이 과거 시점에서 실제 가격을 덮은 비율
        bt["coverage"] = sum(abs(r) <= Z80 * k[12] for r in resid[12]) / len(resid[12])
    by = defaultdict(list)
    for m, p in trades:
        by[m].append(p)
    f.update({
        "k": k[12], "k_region": calib[12][0] if 12 in calib else None,
        "k_n": calib[12][1] if 12 in calib else 0,
        "outliers": flags,
        "monthly": [{"ym": ym_of(m), "median": round(median(by[m]))} for m in sorted(by)],
        "backtest": bt,
    })
    return f
