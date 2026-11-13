"""실행: python3 -m unittest discover -s tests   (apt-price 폴더에서)"""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import model
import molit

ITEM = """<item><aptNm>테스트아파트</aptNm><aptSeq>11680-1</aptSeq><buildYear>2015</buildYear>
<cdealType>{cancel}</cdealType><dealAmount> 123,000</dealAmount><dealDay>7</dealDay><dealMonth>3</dealMonth>
<dealYear>2024</dealYear><excluUseAr>84.97</excluUseAr><floor>12</floor><jibun>1</jibun><umdNm>대치동</umdNm></item>"""


def xml(items, total, code="000"):
    return (f"<response><header><resultCode>{code}</resultCode><resultMsg>OK</resultMsg></header>"
            f"<body><items>{''.join(items)}</items><totalCount>{total}</totalCount></body></response>")


class ParseTest(unittest.TestCase):
    def test_english_tags(self):
        total, trades = molit.parse_response(xml([ITEM.format(cancel=""), ITEM.format(cancel="O")], 2))
        self.assertEqual(total, 2)
        t = trades[0]
        self.assertEqual((t["price"], t["ym"], t["day"], t["floor"], t["build"], t["area"]),
                         (123000, 202403, 7, 12, 2015, 84.97))
        self.assertEqual((t["cid"], t["canceled"], trades[1]["canceled"]), ("11680-1", 0, 1))

    def test_korean_tags(self):
        item = ("<item><아파트>옛아파트</아파트><거래금액>50,000</거래금액><년>2019</년><월>11</월><일>3</일>"
                "<전용면적>59.9</전용면적><층>-1</층><건축년도>1999</건축년도><법정동>역삼동</법정동><지번>10</지번></item>")
        _, trades = molit.parse_response(xml([item], 1, code="00"))
        self.assertEqual((trades[0]["price"], trades[0]["ym"], trades[0]["cid"]),
                         (50000, 201911, "역삼동|옛아파트|10"))

    def test_gateway_error(self):
        body = ("<OpenAPI_ServiceResponse><cmmMsgHeader><errMsg>SERVICE ERROR</errMsg>"
                "<returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg>"
                "<returnReasonCode>30</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>")
        with self.assertRaisesRegex(molit.ApiError, "등록되지"):
            molit.parse_response(body)

    def test_pagination_and_key_encoding(self):
        urls = []

        def fake(url):
            urls.append(url)
            n = 1000 if "pageNo=1&" in url else 5
            return xml([ITEM.format(cancel="")] * n, 1005)

        self.assertEqual(len(molit.fetch_month("a+b/c==", "11680", 202403, fake)), 1005)
        self.assertEqual(len(urls), 2)
        self.assertIn("serviceKey=a%2Bb%2Fc%3D%3D&", urls[0])
        molit.fetch_month("a%2Bb", "11680", 202403, lambda u: urls.append(u) or xml([], 0))
        self.assertIn("serviceKey=a%2Bb&", urls[-1])  # 이미 인코딩된 키는 그대로

    def test_month_list(self):
        from datetime import date
        yms = molit.month_list(date(2026, 2, 10))
        self.assertEqual((len(yms), yms[0], yms[-1]), (120, 201603, 202602))


class ModelTest(unittest.TestCase):
    def series(self, annual, months=120, start=24000):
        """매달 3건, 연 annual 로 일정하게 오르는 단지. 지역도 같은 흐름."""
        trades = [(m, start * math.exp(annual * m / 12) * f) for m in range(months) for f in (0.97, 1.0, 1.03)]
        region = [(m, p / 84) for m, p in trades] * 3
        return region, trades

    def test_steady_growth_recovered(self):
        region, trades = self.series(0.05)
        r = model.analyze(region, trades, 119)
        self.assertAlmostEqual(r["g"], 0.05, places=2)
        truth = 24000 * math.exp(0.05 * 119 / 12)
        self.assertLess(abs(r["now"]["base"] / truth - 1), 0.02)
        f1 = r["forecasts"][0]
        self.assertLess(abs(f1["base"] / (truth * math.exp(0.05)) - 1), 0.03)
        self.assertTrue(f1["low"] < f1["base"] < f1["high"])
        # 먼 미래일수록 구간이 넓어진다
        widths = [f["high"] / f["low"] for f in r["forecasts"]]
        self.assertEqual(widths, sorted(widths))
        self.assertLess(r["backtest"]["mape"], 0.03)

    def test_growth_is_capped(self):
        region, trades = self.series(0.30)
        self.assertEqual(model.analyze(region, trades, 119)["g"], model.G_MAX)

    def test_stale_trades_follow_region(self):
        """단지 거래가 2년 전에 끊겨도 지역이 오른 만큼 현재 시세를 올려 잡는다."""
        region, trades = self.series(0.06)
        old = [t for t in trades if t[0] <= 95]
        r = model.analyze(region, old, 119)
        truth = 24000 * math.exp(0.06 * 119 / 12)
        self.assertLess(abs(r["now"]["base"] / truth - 1), 0.05)

    def test_too_few_trades(self):
        self.assertIsNone(model.analyze([], [(100, 50000), (101, 51000)], 119))


if __name__ == "__main__":
    unittest.main()
