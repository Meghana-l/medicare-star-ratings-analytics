"""Build the site data.

    python -m pipeline.build --demo            # synthetic data, works out of the box
    python -m pipeline.build --year 2026       # real CMS files from data/raw/
    python -m pipeline.build --inspect         # show what the loader finds in data/raw/
"""
import argparse
import datetime
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "starscope.db"
OUT_PATH = ROOT / "web" / "data" / "data.json"


# --------------------------------------------------------------------------- database
def create_db(path):
    path = Path(path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript((ROOT / "sql" / "schema.sql").read_text())
    return conn


def load_tables(conn, d):
    conn.executemany("INSERT INTO contracts VALUES (?,?,?)", d["contracts"])
    conn.executemany("INSERT INTO measures VALUES (?,?,?,?,?,?,?,?,?,?)", d["measures"])
    conn.executemany("INSERT OR REPLACE INTO scores VALUES (?,?,?,?)", d["scores"])
    conn.executemany("INSERT OR REPLACE INTO cutpoints VALUES (?,?,?,?,?,?)", d["cutpoints"])
    conn.executemany("INSERT OR REPLACE INTO summary VALUES (?,?)", d["summary"])
    conn.executemany("INSERT INTO meta VALUES (?,?)", list(d["meta"].items()))
    conn.executescript((ROOT / "sql" / "views.sql").read_text())
    conn.commit()


# --------------------------------------------------------------------------- data checks
def one(conn, sql):
    return conn.execute(sql).fetchone()[0]


def run_checks(conn, warnings=()):
    checks = []

    def add(name, status, detail, count=None):
        checks.append({"name": name, "status": status, "detail": detail, "count": count})

    dup = one(conn, "SELECT COUNT(*) FROM (SELECT 1 FROM scores GROUP BY contract_id, measure_id HAVING COUNT(*) > 1)")
    add("Duplicate contract-measure rows", "pass" if dup == 0 else "fail", "Each contract should have one score per measure.", dup)

    total = one(conn, "SELECT COUNT(*) FROM scores")
    missing = one(conn, "SELECT COUNT(*) FROM scores WHERE score IS NULL")
    pct = round(100.0 * missing / total, 1) if total else 0
    add("Missing measure scores", "pass" if pct < 15 else "warn",
        f"{pct}% of contract-measure cells have no score (new plans or too little data are normal).", missing)

    no_cut = one(conn, """SELECT COUNT(*) FROM measures m WHERE NOT EXISTS (
        SELECT 1 FROM cutpoints c WHERE c.measure_id = m.measure_id
        AND c.year = (SELECT CAST(value AS INTEGER) FROM meta WHERE key='year'))""")
    add("Measures without cut points", "pass" if no_cut == 0 else "fail", "Every measure needs cut points for the rating year.", no_cut)

    bad_order = one(conn, """SELECT COUNT(*) FROM cutpoints c JOIN measures m USING(measure_id) WHERE
        (m.higher_is_better = 1 AND NOT (c.t2 <= c.t3 AND c.t3 <= c.t4 AND c.t4 <= c.t5)) OR
        (m.higher_is_better = 0 AND NOT (c.t2 >= c.t3 AND c.t3 >= c.t4 AND c.t4 >= c.t5))""")
    add("Cut points in the right order", "pass" if bad_order == 0 else "fail",
        "Higher-is-better cut points should rise with stars; lower-is-better should fall.", bad_order)

    neg = one(conn, "SELECT COUNT(*) FROM scores WHERE score < 0")
    add("Negative scores", "pass" if neg == 0 else "fail", "Measure scores should not be negative.", neg)

    no_overall = one(conn, "SELECT COUNT(*) FROM contracts c WHERE NOT EXISTS (SELECT 1 FROM summary s WHERE s.contract_id=c.contract_id AND s.cms_overall IS NOT NULL)")
    add("Contracts without a published overall rating", "pass" if no_overall == 0 else "warn",
        "New or low-enrollment contracts may not receive an overall rating.", no_overall)

    odd = one(conn, "SELECT COUNT(*) FROM scores WHERE score IS NULL AND cms_star IS NOT NULL")
    add("Star published but score missing", "pass" if odd == 0 else "warn", "A published star without a raw score cannot be rebuilt.", odd)

    compared = one(conn, "SELECT COUNT(*) FROM calc WHERE calc_star IS NOT NULL AND cms_star IS NOT NULL")
    mism = one(conn, "SELECT COUNT(*) FROM calc WHERE calc_star IS NOT NULL AND cms_star IS NOT NULL AND calc_star <> cms_star")
    rate = round(100.0 * (compared - mism) / compared, 2) if compared else None
    add("Rebuilt measure stars vs CMS stars", "pass" if mism == 0 else ("warn" if rate and rate >= 95 else "fail"),
        f"{compared - mism:,} of {compared:,} measure stars match ({rate}%).", mism)

    for w in warnings:
        add("Loader note", "warn", w)
    return checks, rate, compared, mism


# --------------------------------------------------------------------------- export
def r(x, n=4):
    return None if x is None else round(x, n)


def export(conn, checks, rate, compared, mism, out_path=OUT_PATH):
    meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
    year = int(meta["year"])
    cols = ["measure_id", "name", "source", "part", "weight", "higher_is_better", "definition", "numerator", "denominator", "exclusions"]
    measures = [dict(zip(cols, row)) for row in conn.execute("SELECT * FROM measures ORDER BY measure_id")]

    cut = {}
    for y, mid, t2, t3, t4, t5 in conn.execute("SELECT * FROM cutpoints ORDER BY year"):
        cut.setdefault(mid, {})[str(y)] = [r(t2), r(t3), r(t4), r(t5)]

    oc = {row[0]: row[1:] for row in conn.execute("SELECT contract_id, calc_overall, wavg, n_rated FROM overall_calc")}
    contracts = []
    for cid, name, org, cms in conn.execute(
            "SELECT c.contract_id, c.name, c.org_type, s.cms_overall FROM contracts c LEFT JOIN summary s USING(contract_id) ORDER BY c.contract_id"):
        calc_overall, wavg, n = oc.get(cid, (None, None, 0))
        contracts.append({"id": cid, "name": name, "org": org, "cms_overall": cms, "calc_overall": calc_overall,
                          "wavg": r(wavg, 3), "n_rated": n})

    scores = {}
    q = """SELECT contract_id, measure_id, score, cms_star, calc_star, next_cut, gap, band_span
           FROM gap_to_next ORDER BY contract_id, measure_id"""
    for cid, mid, score, cms, calc, nxt, gap, span in conn.execute(q):
        ng = (gap / span) if (gap is not None and span) else None
        scores.setdefault(cid, []).append([mid, r(score), cms, calc, r(nxt), r(gap), r(ng)])

    out = {
        "meta": {**meta, "generated": datetime.date.today().isoformat(), "match_rate": rate,
                 "compared": compared, "mismatches": mism},
        "measures": measures, "cutpoints": cut, "contracts": contracts, "scores": scores, "checks": checks,
    }
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, separators=(",", ":")))
    return out


def build(data, db_path=DB_PATH, out_path=OUT_PATH):
    conn = create_db(db_path)
    load_tables(conn, data)
    checks, rate, compared, mism = run_checks(conn, data.get("warnings", ()))
    out = export(conn, checks, rate, compared, mism, out_path)
    conn.close()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--inspect", action="store_true")
    a = ap.parse_args()

    from . import ingest_cms
    raw, ref = ROOT / "data" / "raw", ROOT / "data" / "reference"
    if a.inspect:
        ingest_cms.inspect(raw)
        return
    if a.demo:
        from . import demo
        data = demo.generate()
    else:
        data = ingest_cms.load(raw, ref, a.year)
    out = build(data)
    m = out["meta"]
    print(f"Built {len(out['contracts'])} contracts x {len(out['measures'])} measures ({m['source']}, {m['year']}).")
    print(f"Measure-star match vs CMS: {m['match_rate']}% ({m['compared'] - m['mismatches']:,}/{m['compared']:,}).")
    for w in data.get("warnings", []):
        print("  note:", w)


if __name__ == "__main__":
    main()
