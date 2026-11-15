"""아파트 실거래가 예측 로컬 웹앱.  실행: python3 server.py  ->  http://127.0.0.1:8000"""
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import model
import molit
import sample

HERE = Path(__file__).parent
PORT = int(os.environ.get("PORT", "8000"))


def load_key():
    key = os.environ.get("MOLIT_SERVICE_KEY", "")
    env = HERE / ".env"
    if not key and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("MOLIT_SERVICE_KEY="):
                key = line.split("=", 1)[1].strip().strip("\"'")
    return key


KEY = load_key()
DEMO = not KEY
REGIONS = [sample.SAMPLE_REGION] if DEMO else json.loads((HERE / "regions.json").read_text(encoding="utf-8"))


def now_mi():
    t = date.today()
    return t.year * 12 + t.month - 1


def norm(s):
    return re.sub(r"\s+", "", s).lower()


def complexes(lawd, q):
    with molit.db() as con:
        rows = con.execute(
            "SELECT cid, apt, dong, MAX(build) build, CAST(area AS INT) a, COUNT(*) n, MAX(ym) last "
            "FROM trades WHERE lawd=? AND canceled=0 GROUP BY cid, a", (lawd,)).fetchall()
    out = {}
    for r in rows:
        if q and q not in norm(r["apt"]) and q not in norm(r["dong"]):
            continue
        c = out.setdefault(r["cid"], {"id": r["cid"], "name": r["apt"], "dong": r["dong"],
                                      "build": r["build"], "n": 0, "last": 0, "areas": []})
        c["n"] += r["n"]
        c["last"] = max(c["last"], r["last"])
        c["areas"].append({"area": r["a"], "n": r["n"]})
    res = sorted(out.values(), key=lambda c: -c["n"])[:40]
    for c in res:
        c["areas"].sort(key=lambda a: a["area"])
    return res


_calib = {}  # lawd -> (지역 거래 수, region_k 결과). 거래 수가 바뀌면 다시 계산한다.


def calibration(lawd, con, region):
    if lawd in _calib and _calib[lawd][0] == len(region):
        return _calib[lawd][1]
    groups = defaultdict(list)
    for r in con.execute("SELECT cid, CAST(area AS INT) a, ym, price FROM trades "
                         "WHERE lawd=? AND canceled=0", (lawd,)):
        groups[(r["cid"], r["a"])].append((model.mi_of(r["ym"]), r["price"]))
    # 거래가 충분한 단지·평형 위주로 최대 80개
    top = sorted((g for g in groups.values() if len(g) >= 40), key=len, reverse=True)[:80]
    res = model.region_k(top, model.region_index(region, now_mi()), now_mi())
    _calib[lawd] = (len(region), res)
    return res


def analysis(lawd, cid, area):
    with molit.db() as con:
        region = [(model.mi_of(r[0]), r[1]) for r in con.execute(
            "SELECT ym, price/area FROM trades WHERE lawd=? AND canceled=0", (lawd,))]
        calib = calibration(lawd, con, region)
        rows = con.execute(
            "SELECT * FROM trades WHERE lawd=? AND cid=? AND CAST(area AS INT)=? "
            "ORDER BY ym, day", (lawd, cid, area)).fetchall()
    if not rows:
        return {"error": "해당 평형의 거래가 없습니다."}
    valid = [r for r in rows if not r["canceled"]]
    res = model.analyze(region, [(model.mi_of(r["ym"]), r["price"]) for r in valid], now_mi(), calib)
    if not res:
        return {"error": "거래가 3건 미만이라 예측할 수 없습니다."}
    build = max(r["build"] for r in rows)
    first_ym = molit.month_list()[0]
    res.update({
        "name": rows[0]["apt"], "dong": rows[0]["dong"], "area": area, "build": build,
        # 10년 미만 단지는 입주년도부터, 아니면 최근 10년
        "since": f"{build}년 입주 이후" if build * 100 + 1 > first_ym else "최근 10년",
        "from_ym": first_ym, "now_ym": model.ym_of(now_mi()),
        "canceled": len(rows) - len(valid),
        "trades": [{"ym": r["ym"], "day": r["day"], "price": r["price"], "floor": r["floor"],
                    "area": r["area"]} for r in valid],
    })
    return res


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path in ("/", "/index.html"):
            body = (HERE / "static" / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if not u.path.startswith("/api/"):
            return self.send_json({"error": "not found"}, 404)
        try:
            self.send_json(self.api(u.path[5:], q))
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    do_POST = do_GET

    def api(self, name, q):
        if name == "regions":
            return {"demo": DEMO, "regions": REGIONS}
        lawd = q.get("lawd", "")
        if not any(r["code"] == lawd for r in REGIONS):
            return {"error": "지역을 다시 선택하세요."}
        if name == "load":
            if DEMO:
                return {"total": 0, "done": 0, "error": None, "running": False}
            return molit.start_load(KEY, lawd, q.get("force") == "1")
        if name == "progress":
            return molit.jobs.get(lawd) or {"total": 0, "done": 0, "error": None, "running": False}
        if name == "complexes":
            return {"complexes": complexes(lawd, norm(q.get("q", "")))}
        if name == "analysis":
            return analysis(lawd, q.get("id", ""), int(q.get("area", "0")))
        return {"error": "not found"}


if __name__ == "__main__":
    if DEMO:
        print("인증키가 없어 가상 데이터(데모)로 실행합니다. 실데이터는 .env 에 MOLIT_SERVICE_KEY 를 넣으세요.")
        sample.generate()
    print(f"http://127.0.0.1:{PORT} 에서 실행 중 (종료: Ctrl+C)")
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)
