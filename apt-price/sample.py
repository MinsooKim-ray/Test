"""인증키가 없을 때 화면을 확인하기 위한 가상 데이터. 실제 단지·가격이 아니다."""
import math
import random
from datetime import date

import molit

SAMPLE_LAWD = "00000"
SAMPLE_REGION = {"code": SAMPLE_LAWD, "name": "샘플시 데모구 (가상 데이터)"}

# (이름, 동, 건축년도, 지역 대비 가격 수준, 월평균 거래 수, 평형들)
COMPLEXES = [
    ("샘플마을 1단지", "가람동", 1998, 1.00, 2.5, (59.9, 84.9)),
    ("샘플타운 2차", "가람동", 2008, 1.15, 1.8, (84.7, 114.6)),
    ("샘플포레 신축", "나래동", date.today().year - 5, 1.45, 1.2, (59.8, 84.9)),
    ("샘플빌라트", "나래동", 2003, 0.85, 0.3, (84.5,)),
]


def _cycle(k):
    """k: 0(10년 전) ~ 119(현재). 상승 -> 조정 -> 회복 흐름의 로그 지수."""
    t = k / 119
    return 0.55 * t + 0.18 * math.sin(2 * math.pi * (t - 0.15) * 1.3)


def generate():
    rnd = random.Random(42)
    yms = molit.month_list()
    for k, ym in enumerate(yms):
        base = 900 * math.exp(_cycle(k))  # 만원/㎡
        trades = []
        for n, (apt, dong, build, level, rate, areas) in enumerate(COMPLEXES):
            if ym // 100 < build:
                continue
            count = sum(rnd.random() < rate / 4 for _ in range(4))
            for _ in range(count):
                area, floor = rnd.choice(areas), rnd.randint(1, 20)
                price = base * level * area * (1 + 0.004 * min(floor, 10)) * math.exp(rnd.gauss(0, 0.04))
                trades.append({
                    "cid": f"S{n}", "apt": apt, "dong": dong, "area": area,
                    "price": round(price / 100) * 100, "ym": ym,
                    "day": rnd.randint(1, 28), "floor": floor, "build": build,
                    "canceled": 1 if rnd.random() < 0.02 else 0})
        molit.store_month(SAMPLE_LAWD, ym, trades)
