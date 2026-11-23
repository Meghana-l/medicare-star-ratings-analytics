"""Load the public CMS Part C & D Star Ratings data tables into the normalized tables.

Drop the downloaded ZIP (or the CSV files inside it) into data/raw/. The loader looks for
three files by name: "Measure Data" (raw scores), "Measure Stars" (CMS's published measure
stars) and "Summary Rating" (published overall ratings). Run with --inspect to see what it found.

Reference files in data/reference/ (optional but recommended):
  measure_meta.csv       measure_id,name,source,part,weight,higher_is_better,definition,numerator,denominator,exclusions
  cutpoints_<year>.csv   measure_id,t2,t3,t4,t5      (copied from the Technical Notes)
"""
import csv
import io
import re
import zipfile
from pathlib import Path

import pandas as pd

MEASURE_LABEL = re.compile(r"^\s*([CD]\d{2})\s*[:\-]\s*(.+?)\s*$")
BAD_TEXT = ("not ", "no data", "plan too", "n/a", "nr", "*")


# --------------------------------------------------------------------------- reading
def collect_files(raw_dir):
    """Return {filename: bytes} for every CSV in raw_dir, including CSVs inside ZIPs."""
    out = {}
    for p in sorted(Path(raw_dir).rglob("*")):
        if p.suffix.lower() == ".csv":
            out[p.name] = p.read_bytes()
        elif p.suffix.lower() == ".zip":
            with zipfile.ZipFile(p) as z:
                for n in z.namelist():
                    if n.lower().endswith(".csv"):
                        out[Path(n).name] = z.read(n)
    return out


def _decode(b):
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("latin-1", errors="replace")


def read_table(raw):
    """Read a CMS CSV whose real header row is not the first row."""
    rows = list(csv.reader(io.StringIO(_decode(raw))))
    width = max((len(r) for r in rows), default=0)
    df = pd.DataFrame([r + [""] * (width - len(r)) for r in rows], dtype=str)
    header_idx = None
    for i in range(min(12, len(df))):
        cells = [str(c).strip().lower() for c in df.iloc[i].tolist()]
        if any(c in ("contract number", "contract id", "contract") for c in cells):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("Could not find a 'Contract Number' header row in a CMS file.")
    header = [str(c).strip() for c in df.iloc[header_idx].tolist()]
    n_measure = sum(1 for h in header if MEASURE_LABEL.match(h))
    start = header_idx + 1
    if n_measure < 3 and header_idx + 1 < len(df):  # IDs and names may be on two rows
        nxt = [str(c).strip() for c in df.iloc[header_idx + 1].tolist()]
        merged = [f"{a}: {b}" if re.match(r"^[CD]\d{2}$", a) and b else a for a, b in zip(header, nxt)]
        if sum(1 for h in merged if MEASURE_LABEL.match(h)) > n_measure:
            header, start = merged, header_idx + 2
    body = df.iloc[start:].copy()
    body.columns = header
    return body.reset_index(drop=True)


def to_num(x):
    t = str(x).strip()
    if not t:
        return None
    low = t.lower()
    if any(low.startswith(b) or low == b for b in BAD_TEXT):
        return None
    t = t.replace("%", "").replace(",", "").replace("$", "")
    try:
        return float(t)
    except ValueError:
        return None


def _find(files, key):
    for name, raw in files.items():
        if key in name.lower():
            return name, raw
    return None, None


def _id_col(df):
    for c in df.columns:
        if str(c).strip().lower() in ("contract number", "contract id", "contract"):
            return c
    raise ValueError("No contract id column found.")


def _name_col(df, *keys):
    for k in keys:
        for c in df.columns:
            if k in str(c).lower():
                return c
    return None


# --------------------------------------------------------------------------- classification
def guess_source(mid, name):
    n = name.lower()
    if any(k in n for k in ("improving or maintaining", "reducing the risk of falling", "monitoring physical activity")):
        return "HOS"
    if any(k in n for k in ("getting needed", "getting appointments", "customer service", "care coordination",
                            "rating of", "flu vaccine")):
        return "CAHPS"
    if any(k in n for k in ("complaints", "choosing to leave", "appeals", "call center", "timely", "quality improvement",
                            "plan makes", "tty", "special needs plan", "price accuracy")):
        return "Admin"
    if mid.startswith("D"):
        return "Part D"
    return "HEDIS"


def guess_higher_is_better(name):
    n = name.lower()
    return 0 if any(k in n for k in ("complaints", "choosing to leave", "readmission", "potentially preventable")) else 1


def load_measure_meta(measures, ref_dir):
    """measures: {id: name}. Returns rows for the measures table and a list of warnings."""
    ref = Path(ref_dir) / "measure_meta.csv"
    warnings, given = [], {}
    if ref.exists():
        for _, r in pd.read_csv(ref, dtype=str, keep_default_na=False).iterrows():
            given[r["measure_id"].strip()] = r
    rows, template = [], []
    for mid, name in measures.items():
        r = given.get(mid)
        src = (r["source"] if r is not None and r["source"] else guess_source(mid, name))
        hib = (int(float(r["higher_is_better"])) if r is not None and r["higher_is_better"] != "" else guess_higher_is_better(name))
        w = (float(r["weight"]) if r is not None and r["weight"] != "" else None)
        if w is None:
            warnings.append(f"{mid}: weight not set, using 1")
            w = 1.0
        get = lambda k: (r[k] if r is not None and k in r and r[k] != "" else None)
        rows.append((mid, name, src, mid[0], w, hib, get("definition"), get("numerator"), get("denominator"), get("exclusions")))
        template.append({"measure_id": mid, "name": name, "source": src, "part": mid[0], "weight": "" if r is None else (r["weight"]),
                         "higher_is_better": hib, "definition": get("definition") or "", "numerator": get("numerator") or "",
                         "denominator": get("denominator") or "", "exclusions": get("exclusions") or ""})
    if not ref.exists():
        ref.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(template).to_csv(ref, index=False)
        warnings.append(f"Wrote a template to {ref}. Fill in weight, source and the spec text from the Technical Notes.")
    return rows, warnings


# --------------------------------------------------------------------------- cut points
def load_cutpoints(ref_dir, years):
    rows = []
    for y in years:
        f = Path(ref_dir) / f"cutpoints_{y}.csv"
        if f.exists():
            for _, r in pd.read_csv(f, dtype=str, keep_default_na=False).iterrows():
                vals = [to_num(r.get(k, "")) for k in ("t2", "t3", "t4", "t5")]
                rows.append((int(y), r["measure_id"].strip(), *vals))
    return rows


def estimate_cutpoints(year, measure_rows, scores):
    """Fallback when no cut point file exists: infer thresholds from CMS's published stars.
    NOT an independent check, since the thresholds come from the answer key. The site says so."""
    hib = {m[0]: m[5] for m in measure_rows}
    by = {}
    for cid, mid, s, st in scores:
        if s is not None and st is not None:
            by.setdefault(mid, {}).setdefault(int(st), []).append(s)
    BIG = 1e12
    out = []
    for mid, levels in by.items():
        t = {}
        for k in (2, 3, 4, 5):
            vals = levels.get(k)
            if hib.get(mid, 1):
                t[k] = min(vals) if vals else None
            else:
                t[k] = max(vals) if vals else None
        for k in (5, 4, 3, 2):  # fill gaps so the thresholds stay ordered
            if t[k] is None:
                nxt = t.get(k + 1) if k < 5 else None
                t[k] = nxt if nxt is not None else (BIG if hib.get(mid, 1) else -BIG)
        out.append((int(year), mid, t[2], t[3], t[4], t[5]))
    return out


# --------------------------------------------------------------------------- main loader
def load(raw_dir, ref_dir, year):
    files = collect_files(raw_dir)
    nm, data = _find(files, "measure data")
    ns, stars = _find(files, "measure stars")
    nu, summ = _find(files, "summary")
    if data is None or stars is None:
        raise FileNotFoundError(
            "Need 'Measure Data' and 'Measure Stars' CSVs in data/raw/. Found: " + (", ".join(files) or "nothing"))

    d, s = read_table(data), read_table(stars)
    cid_d, cid_s = _id_col(d), _id_col(s)
    name_c = _name_col(d, "marketing name", "contract name")
    type_c = _name_col(d, "organization type")

    labels = {}
    for c in d.columns:
        m = MEASURE_LABEL.match(str(c))
        if m:
            labels[c] = (m.group(1), m.group(2))
    measures = {mid: name for mid, name in labels.values()}
    star_cols = {MEASURE_LABEL.match(str(c)).group(1): c for c in s.columns if MEASURE_LABEL.match(str(c))}

    contracts, scores = [], []
    s_idx = s.set_index(cid_s)
    for _, r in d.iterrows():
        cid = str(r[cid_d]).strip()
        if not re.match(r"^[HRSE]\d{4}$", cid):
            continue
        contracts.append((cid, r[name_c].strip() if name_c else None, r[type_c].strip() if type_c else None))
        for col, (mid, _) in labels.items():
            st = None
            if cid in s_idx.index and mid in star_cols:
                v = s_idx.loc[cid, star_cols[mid]]
                st = to_num(v.iloc[0] if hasattr(v, "iloc") else v)
            scores.append((cid, mid, to_num(r[col]), st))

    summary = []
    if summ is not None:
        t = read_table(summ)
        cc = _id_col(t)
        oc = next((c for c in t.columns if "overall" in str(c).lower() and "rating" in str(c).lower()), None)
        if oc is not None:
            summary = [(str(r[cc]).strip(), to_num(r[oc])) for _, r in t.iterrows() if re.match(r"^[HRSE]\d{4}$", str(r[cc]).strip())]

    measure_rows, warnings = load_measure_meta(measures, ref_dir)
    cuts = load_cutpoints(ref_dir, range(int(year) - 4, int(year) + 1))
    cut_source = "CMS Technical Notes"
    if not any(c[0] == int(year) for c in cuts):
        cuts += estimate_cutpoints(year, measure_rows, scores)
        cut_source = "estimated from published stars"
        warnings.append(f"No data/reference/cutpoints_{year}.csv. Cut points were ESTIMATED from CMS's own stars.")

    return {
        "contracts": list(dict.fromkeys(contracts)), "measures": measure_rows, "scores": scores,
        "cutpoints": cuts, "summary": summary, "warnings": warnings,
        "meta": {"source": "cms", "year": str(year), "cutpoint_source": cut_source},
    }


def inspect(raw_dir):
    files = collect_files(raw_dir)
    print(f"{len(files)} CSV file(s) found in {raw_dir}")
    for n, raw in files.items():
        try:
            t = read_table(raw)
            mcols = sum(1 for c in t.columns if MEASURE_LABEL.match(str(c)))
            print(f"  {n}: {len(t)} rows, {len(t.columns)} columns, {mcols} measure columns")
        except Exception as e:  # noqa: BLE001
            print(f"  {n}: could not parse ({e})")
