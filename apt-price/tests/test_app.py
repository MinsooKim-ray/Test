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

    def test_real_response(self):
        """실제 API 응답(강남구 2026-08, 3건으로 줄임). 빈 값은 공백 한 칸으로 온다."""
        body = (Path(__file__).parent / "real_response.xml").read_text(encoding="utf-8")
        total, trades = molit.parse_response(body)
        self.assertEqual((total, len(trades)), (100, 3))
        self.assertEqual(trades[0], {
            "cid": "11680-279", "apt": "삼익대청아파트", "dong": "개포동", "area": 51.12,
            "price": 205000, "ym": 202608, "day": 22, "floor": 6, "build": 1992, "canceled": 0})
        self.assertEqual([t["canceled"] for t in trades], [0, 1, 0])  # cdealType "O" = 해제
        # 데이터가 없는 달·폐지된 지역 코드: 오류가 아니라 000 + 빈 items
        empty = ('<?xml version="1.0" encoding="utf-8" standalone="yes"?><response><header>'
                 "<resultCode>000</resultCode><resultMsg>OK</resultMsg></header><body><items/>"
                 "<numOfRows>2</numOfRows><pageNo>1</pageNo><totalCount>0</totalCount></body></response>")
        self.assertEqual(molit.parse_response(empty), (0, []))

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
        # 실제 게이트웨이 응답(2026-11 확인): 코드가 errMsg 에 온다
        live = ("<OpenAPI_ServiceResponse><cmmMsgHeader><errMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</errMsg>"
                "<returnAuthMsg>등록되지 않은 서비스키</returnAuthMsg><returnReasonCode>30</returnReasonCode>"
                "</cmmMsgHeader></OpenAPI_ServiceResponse>")
        with self.assertRaisesRegex(molit.ApiError, "1~2시간"):
            molit.parse_response(live)

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


class LoadTest(unittest.TestCase):
    def test_region_with_no_trades_reports_error(self):
        """폐지된 코드는 0건만 온다 -> 조용히 '완료'가 아니라 안내 메시지를 낸다."""
        import tempfile
        old = molit.DB_PATH
        with tempfile.TemporaryDirectory() as d:
            molit.DB_PATH = Path(d) / "data" / "cache.db"
            try:
                job = {"total": 2, "done": 0, "error": None, "running": True}
                orig = molit.fetch_month
                molit.fetch_month = lambda key, lawd, ym: []
                try:
                    molit._run("k", "41190", [202609, 202610], job)
                finally:
                    molit.fetch_month = orig
                self.assertEqual((job["done"], job["running"]), (2, False))
                self.assertIn("regions.json", job["error"])
                todo, molit.months_to_fetch = molit.months_to_fetch, lambda lawd, force=False: []
                try:  # 전부 캐시된 뒤 다시 선택해도 같은 안내
                    self.assertIn("regions.json", molit.start_load("k", "41190")["error"])
                finally:
                    molit.months_to_fetch = todo
                molit.store_month("41192", 202609, molit.parse_response(xml([ITEM.format(cancel="")], 1))[1])
                self.assertIsNone(molit._empty_error("41192"))
            finally:
                molit.DB_PATH = old
                molit.jobs.pop("41190", None)

    def test_regions_file(self):
        import json
        regions = json.loads((Path(__file__).parent.parent / "regions.json").read_text(encoding="utf-8"))
        codes = [r["code"] for r in regions]
        self.assertEqual(len(codes), len(set(codes)))
        self.assertTrue(all(len(c) == 5 and c.isdigit() for c in codes))
        # 폐지되어 API가 0건만 돌려주는 코드(2026-11 실제 확인)는 없어야 한다
        dead = {"41190", "41590", "47720", "28110", "28140", "28260", "48245"}
        self.assertFalse(dead & set(codes))
        self.assertFalse([c for c in codes if c[:2] in ("42", "45")])


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
