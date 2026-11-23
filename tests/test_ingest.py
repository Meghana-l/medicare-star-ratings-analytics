"""Checks the CMS loader against a small file that imitates the layout of the public data tables
(a title row above the header row, 'C01: Name' measure columns, text for missing values)."""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import build, ingest_cms  # noqa: E402

HEAD = ["Contract Number", "Organization Type", "Contract Name", "Organization Marketing Name", "Parent Organization"]


def write(path, title, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([title])
        w.writerows(rows)


def fixture(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    cols = ["C01: Breast Cancer Screening", "C02: Complaints about the Health Plan"]
    pre = lambda cid: [cid, "Local CCP", f"Plan {cid}", f"Plan {cid}", "Parent"]
    data = [HEAD + cols,
            pre("H0001") + ["85%", "0.10"], pre("H0002") + ["75%", "0.30"],
            pre("H0003") + ["65%", "0.60"], pre("H0004") + ["Not enough data available", "0.90"],
            pre("H0005") + ["55%", "1.20"]]
    stars = [HEAD + cols,
             pre("H0001") + ["5", "5"], pre("H0002") + ["4", "4"], pre("H0003") + ["3", "3"],
             pre("H0004") + ["Plan too new to be measured", "2"], pre("H0005") + ["2", "1"]]
    summary = [HEAD + ["2026 Overall Rating"], pre("H0001") + ["4.5"], pre("H0002") + ["4"],
               pre("H0003") + ["3"], pre("H0004") + ["Not enough data"], pre("H0005") + ["2"]]
    write(raw / "2026 Star Ratings Data Table - Measure Data (Oct 9 2025).csv", "Measure Data", data)
    write(raw / "2026 Star Ratings Data Table - Measure Stars (Oct 9 2025).csv", "Measure Stars", stars)
    write(raw / "2026 Star Ratings Data Table - Summary Rating (Oct 9 2025).csv", "Summary", summary)
    ref = tmp_path / "ref"
    ref.mkdir()
    return raw, ref


def test_loader_reads_cms_style_tables(tmp_path):
    raw, ref = fixture(tmp_path)
    d = ingest_cms.load(raw, ref, 2026)
    assert len(d["contracts"]) == 5
    assert {m[0] for m in d["measures"]} == {"C01", "C02"}
    by = {(c, m): (s, st) for c, m, s, st in d["scores"]}
    assert by[("H0001", "C01")] == (85.0, 5.0)
    assert by[("H0004", "C01")] == (None, None)          # text values become missing
    assert dict(d["summary"])["H0001"] == 4.5
    assert dict(d["summary"])["H0004"] is None
    # direction guess: complaints are lower-is-better
    hib = {m[0]: m[5] for m in d["measures"]}
    assert hib == {"C01": 1, "C02": 0}
    assert (ref / "measure_meta.csv").exists()            # template written for the user to fill in


def test_loader_then_build_flags_estimated_cutpoints(tmp_path):
    raw, ref = fixture(tmp_path)
    d = ingest_cms.load(raw, ref, 2026)
    out = build.build(d, db_path=":memory:", out_path=tmp_path / "data.json")
    assert out["meta"]["cutpoint_source"].startswith("estimated")
    assert out["meta"]["source"] == "cms"
    assert any("ESTIMATED" in c["detail"] for c in out["checks"])


def test_official_cutpoints_are_used_when_provided(tmp_path):
    raw, ref = fixture(tmp_path)
    (ref / "cutpoints_2026.csv").write_text("measure_id,t2,t3,t4,t5\nC01,55,65,75,85\nC02,1.2,0.9,0.6,0.3\n")
    d = ingest_cms.load(raw, ref, 2026)
    out = build.build(d, db_path=":memory:", out_path=tmp_path / "data.json")
    assert out["meta"]["cutpoint_source"] == "CMS Technical Notes"
    assert out["meta"]["match_rate"] == 100.0
