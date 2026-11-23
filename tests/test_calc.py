import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import build, demo  # noqa: E402


def tiny_db(higher, score, cuts=(50, 60, 70, 80)):
    conn = build.create_db(":memory:")
    data = {
        "contracts": [("H1", "Test", "MA-PD")],
        "measures": [("M1", "Test measure", "HEDIS", "C", 1.0, 1 if higher else 0, None, None, None, None)],
        "scores": [("H1", "M1", score, None)],
        "cutpoints": [(2026, "M1", *cuts)],
        "summary": [("H1", 3.0)],
        "meta": {"source": "test", "year": "2026", "cutpoint_source": "test"},
    }
    build.load_tables(conn, data)
    return conn


def calc_star(conn):
    return conn.execute("SELECT calc_star FROM calc").fetchone()[0]


def test_higher_is_better_boundaries():
    for score, expect in [(49.9, 1), (50, 2), (59.9, 2), (60, 3), (70, 4), (79.9, 4), (80, 5), (95, 5)]:
        assert calc_star(tiny_db(True, score)) == expect, score


def test_lower_is_better_boundaries():
    cuts = (0.8, 0.6, 0.4, 0.2)  # t2..t5, falling
    for score, expect in [(0.1, 5), (0.2, 4), (0.39, 4), (0.4, 3), (0.6, 2), (0.79, 2), (0.8, 1), (1.5, 1)]:
        assert calc_star(tiny_db(False, score, cuts)) == expect, score


def test_gap_to_next_star():
    conn = tiny_db(True, 63)
    gap, nxt = conn.execute("SELECT gap, next_cut FROM gap_to_next").fetchone()
    assert nxt == 70 and abs(gap - 7) < 1e-9
    conn = tiny_db(False, 0.5, (0.8, 0.6, 0.4, 0.2))
    gap, nxt = conn.execute("SELECT gap, next_cut FROM gap_to_next").fetchone()
    assert nxt == 0.4 and abs(gap - 0.1) < 1e-9


def test_five_star_has_no_gap():
    conn = tiny_db(True, 90)
    assert conn.execute("SELECT gap FROM gap_to_next").fetchone()[0] is None


def test_demo_build_matches_cms_stars(tmp_path):
    out = build.build(demo.generate(), db_path=":memory:", out_path=tmp_path / "data.json")
    assert out["meta"]["match_rate"] == 100.0
    assert len(out["contracts"]) == 140
    assert all(c["status"] != "fail" for c in out["checks"])


def test_mismatch_is_detected():
    conn = tiny_db(True, 63)
    conn.execute("UPDATE scores SET cms_star = 5")
    checks, rate, compared, mism = build.run_checks(conn)
    assert mism == 1 and rate == 0.0
    assert any(c["name"].startswith("Rebuilt") and c["status"] == "fail" for c in checks)


def test_bad_cutpoint_order_is_flagged():
    conn = tiny_db(True, 63, cuts=(70, 60, 50, 40))
    checks, *_ = build.run_checks(conn)
    assert any(c["name"] == "Cut points in the right order" and c["status"] == "fail" for c in checks)
