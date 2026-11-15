"""국토교통부 아파트 매매 실거래가(공공데이터포털 오픈API) 수집 + SQLite 캐시."""
import contextlib
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

API_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
DB_PATH = Path(__file__).parent / "data" / "cache.db"
MONTHS = 120            # 수집 기간: 최근 10년
RECENT_MONTHS = 3       # 최근 n개월은 신고 지연·해제 반영을 위해 다시 받는다
RECENT_TTL = 12 * 3600

ERROR_HINTS = {
    "SERVICE_KEY_IS_NOT_REGISTERED_ERROR": "인증키가 아직 등록되지 않았습니다. 활용신청 직후라면 1~2시간 뒤 다시 시도하세요.",
    "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR": "일일 호출 한도를 넘었습니다. 내일 다시 시도하면 이어서 받습니다.",
    "SERVICE_ACCESS_DENIED_ERROR": "이 API에 대한 활용신청이 되어 있지 않습니다.",
    "DEADLINE_HAS_EXPIRED_ERROR": "인증키 활용기간이 만료되었습니다. 포털에서 연장 신청하세요.",
}

# 응답 태그: 현재 영문 태그, 구버전 한글 태그 둘 다 받는다.
TAGS = {
    "apt": ("aptNm", "아파트"), "area": ("excluUseAr", "전용면적"),
    "price": ("dealAmount", "거래금액"), "year": ("dealYear", "년"),
    "month": ("dealMonth", "월"), "day": ("dealDay", "일"),
    "floor": ("floor", "층"), "build": ("buildYear", "건축년도"),
    "dong": ("umdNm", "법정동"), "jibun": ("jibun", "지번"),
    "seq": ("aptSeq", "일련번호"), "cancel": ("cdealType", "해제여부"),
}


class ApiError(Exception):
    pass


def _text(item, key):
    for tag in TAGS[key]:
        el = item.find(tag)
        if el is not None and el.text and el.text.strip():
            return el.text.strip()
    return ""


def _int(s, default=0):
    try:
        return int(float(s.replace(",", "")))
    except ValueError:
        return default


def parse_response(xml_text):
    """XML 응답 -> (totalCount, [거래 dict]). 오류 응답이면 ApiError."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise ApiError(f"응답을 해석할 수 없습니다: {xml_text[:200]!r}") from e
    if root.find(".//cmmMsgHeader") is not None:  # 게이트웨이 오류(인증키 등)
        # 오류 코드가 errMsg 에 오는 형식과 returnAuthMsg 에 오는 형식이 모두 있다
        parts = [(root.findtext(f".//{t}") or "").strip() for t in ("errMsg", "returnAuthMsg")]
        hint = next((ERROR_HINTS[x] for x in parts if x in ERROR_HINTS), None)
        raise ApiError(hint or " / ".join(x for x in parts if x) or "API 인증 오류")
    code = (root.findtext(".//resultCode") or "").strip()
    # 실제 응답(2026-11 확인): 성공은 "000". 데이터가 없어도 "000" + 빈 <items/> 로 온다.
    if code and code not in ("00", "000", "03"):
        msg = (root.findtext(".//resultMsg") or "").strip()
        raise ApiError(ERROR_HINTS.get(msg, f"API 오류 {code}: {msg}"))
    total = _int(root.findtext(".//totalCount") or "0")
    trades = []
    for it in root.iter("item"):
        price, area = _int(_text(it, "price")), _text(it, "area")
        try:
            area = float(area)
        except ValueError:
            continue
        if price <= 0 or area <= 0:
            continue
        apt, dong, jibun = _text(it, "apt"), _text(it, "dong"), _text(it, "jibun")
        trades.append({
            "cid": _text(it, "seq") or f"{dong}|{apt}|{jibun}",
            "apt": apt, "dong": dong, "area": area, "price": price,
            "ym": _int(_text(it, "year")) * 100 + _int(_text(it, "month")),
            "day": _int(_text(it, "day")), "floor": _int(_text(it, "floor")),
            "build": _int(_text(it, "build")),
            "canceled": 1 if _text(it, "cancel").upper() == "O" else 0,
        })
    return total, trades


def _http_get(url):
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if body.lstrip().startswith("<"):
                return body  # 오류 본문도 XML이면 파서가 사유를 뽑는다
            last = ApiError(f"HTTP {e.code}: {body[:200]}")
        except OSError as e:
            last = ApiError(f"네트워크 오류: {e}")
        time.sleep(1.5 * (attempt + 1))
    raise last


def fetch_month(key, lawd, ym, http_get=_http_get):
    """한 시군구의 한 달치 전체(페이지 포함)."""
    key_q = key if "%" in key else urllib.parse.quote(key, safe="")
    out, page = [], 1
    while True:
        url = (f"{API_URL}?serviceKey={key_q}&LAWD_CD={lawd}&DEAL_YMD={ym}"
               f"&pageNo={page}&numOfRows=1000")
        total, trades = parse_response(http_get(url))
        out += trades
        if not trades or page * 1000 >= total:
            return out
        page += 1


# ---------- 캐시 ----------
_write_lock = threading.Lock()


@contextlib.contextmanager
def db():
    """with db() as con: 끝나면 커밋하고 연결을 닫는다."""
    con = _connect()
    try:
        yield con
        con.commit()
    finally:
        con.close()


def _connect():
    DB_PATH.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.executescript("""
        CREATE TABLE IF NOT EXISTS trades(
            lawd TEXT, ym INT, day INT, cid TEXT, apt TEXT, dong TEXT,
            area REAL, floor INT, price INT, build INT, canceled INT);
        CREATE INDEX IF NOT EXISTS ix_trades ON trades(lawd, cid);
        CREATE TABLE IF NOT EXISTS months(
            lawd TEXT, ym INT, fetched_at REAL, PRIMARY KEY(lawd, ym));
    """)
    return con


def store_month(lawd, ym, trades):
    with _write_lock, db() as con:
        con.execute("DELETE FROM trades WHERE lawd=? AND ym=?", (lawd, ym))
        con.executemany(
            "INSERT INTO trades VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            [(lawd, ym, t["day"], t["cid"], t["apt"], t["dong"], t["area"],
              t["floor"], t["price"], t["build"], t["canceled"]) for t in trades])
        con.execute("INSERT OR REPLACE INTO months VALUES(?,?,?)", (lawd, ym, time.time()))


def month_list(today=None, n=MONTHS):
    """최근 n개월의 YYYYMM 목록(과거 -> 현재)."""
    today = today or date.today()
    mi = today.year * 12 + today.month - 1
    return [(m // 12) * 100 + m % 12 + 1 for m in range(mi - n + 1, mi + 1)]


def months_to_fetch(lawd, force=False):
    yms = month_list()
    if force:
        return yms
    with db() as con:
        got = {r["ym"]: r["fetched_at"] for r in
               con.execute("SELECT ym, fetched_at FROM months WHERE lawd=?", (lawd,))}
    recent, now = set(yms[-RECENT_MONTHS:]), time.time()
    return [ym for ym in yms
            if ym not in got or (ym in recent and now - got[ym] > RECENT_TTL)]


# ---------- 백그라운드 수집 작업 ----------
def _empty_error(lawd):
    """폐지된 시군구 코드는 오류 없이 0건만 돌려준다(실제 확인). 그대로 두면 빈 화면이 된다."""
    with db() as con:
        if con.execute("SELECT 1 FROM trades WHERE lawd=? LIMIT 1", (lawd,)).fetchone():
            return None
    return ("이 지역 코드로는 10년간 거래가 한 건도 없습니다. 행정구역 개편으로 코드가 바뀌었을 수 "
            "있으니 regions.json 의 코드를 확인하세요.")


jobs = {}
_jobs_lock = threading.Lock()


def start_load(key, lawd, force=False):
    with _jobs_lock:
        job = jobs.get(lawd)
        if job and job["running"]:
            return job
        todo = months_to_fetch(lawd, force)
        job = jobs[lawd] = {"total": len(todo), "done": 0,
                            "error": None if todo else _empty_error(lawd),
                            "running": bool(todo)}
    if todo:
        threading.Thread(target=_run, args=(key, lawd, todo, job), daemon=True).start()
    return job


def _run(key, lawd, todo, job):
    def one(ym):
        if job["error"]:
            return
        try:
            store_month(lawd, ym, fetch_month(key, lawd, ym))
            job["done"] += 1
        except Exception as e:  # 한 달이 실패하면 나머지는 중단, 받은 달은 캐시에 남는다
            job["error"] = str(e)
    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(one, todo))
    job["error"] = job["error"] or _empty_error(lawd)
    job["running"] = False
