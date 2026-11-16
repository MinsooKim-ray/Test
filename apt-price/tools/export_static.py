"""캐시에 받아 둔 지역을 서버 없이 볼 수 있는 정적 자료(JSON)로 내보낸다.

사용: python3 tools/export_static.py 출력폴더 11440 26350
  출력폴더/index.json  지역 목록과 기준일
  출력폴더/11440.json  지역별 단지·평형의 거래와 분석 결과
snapshot/page.html 이 이 파일들을 읽는다. 내보낸 시점의 자료로 고정된다.
"""
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import model
import molit
import server


def export_region(lawd, now):
    with molit.db() as con:
        rows = con.execute("SELECT * FROM trades WHERE lawd=? ORDER BY ym, day", (lawd,)).fetchall()
        region = [(model.mi_of(r["ym"]), r["price"] / r["area"]) for r in rows if not r["canceled"]]
        calib = server.calibration(lawd, con, region)
    idx = model.region_index(region, now)
    groups = defaultdict(lambda: defaultdict(list))
    for r in rows:
        groups[r["cid"]][int(r["area"])].append(r)
    complexes = []
    for by_area in groups.values():
        first = next(iter(by_area.values()))[0]
        areas = []
        for area, rs in sorted(by_area.items()):
            valid = [r for r in rs if not r["canceled"]]
            if not valid:
                continue
            res = model.analyze(None, [(model.mi_of(r["ym"]), r["price"]) for r in valid], now, calib, idx)
            flags = res["outliers"] if res else [False] * len(valid)
            out = {"area": area, "c": len(rs) - len(valid),
                   "t": [[r["ym"], r["day"], r["price"], r["floor"], r["area"], int(f)]
                         for r, f in zip(valid, flags)], "r": None}
            if res:
                band = lambda f: {k: f[k] for k in ("months", "base", "low", "high")}
                out["r"] = {"now": band(res["now"]), "f": [band(f) for f in res["forecasts"]],
                            "g": round(res["g"], 4), "k": round(res["k"], 3),
                            "k_region": res["k_region"] and round(res["k_region"], 3),
                            "k_n": res["k_n"], "n_used": res["n_used"], "window": res["window"],
                            "bt": res["backtest"] and {"n": res["backtest"]["n"],
                                                       "mape": round(res["backtest"]["mape"], 4),
                                                       "coverage": round(res["backtest"]["coverage"], 4)}}
            areas.append(out)
        if areas:
            complexes.append({"name": first["apt"], "dong": first["dong"],
                              "build": max(r["build"] for rs in by_area.values() for r in rs),
                              "n": sum(len(a["t"]) for a in areas), "areas": areas})
    complexes.sort(key=lambda c: -c["n"])
    return complexes


def main(out_dir, lawds):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    names = {r["code"]: r["name"] for r in json.loads((Path(__file__).parent.parent / "regions.json").read_text(encoding="utf-8"))}
    now = server.now_mi()
    index = {"exported": date.today().isoformat(), "now_ym": model.ym_of(now),
             "from_ym": molit.month_list()[0], "regions": []}
    for lawd in lawds:
        complexes = export_region(lawd, now)
        if not complexes:
            sys.exit(f"{lawd}: 캐시에 거래가 없습니다. 먼저 앱에서 이 지역을 받아 주세요.")
        (out / f"{lawd}.json").write_text(
            json.dumps(complexes, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        trades = sum(c["n"] for c in complexes)
        index["regions"].append({"code": lawd, "name": names.get(lawd, lawd),
                                 "complexes": len(complexes), "trades": trades})
        print(lawd, names.get(lawd), "단지", len(complexes), "거래", trades,
              f"{(out / f'{lawd}.json').stat().st_size / 1e6:.2f}MB")
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2:])
