"""Synthetic demo data so the site works before real CMS files are loaded.

Everything here is made up. The site shows a DEMO banner while this data is loaded.
"""
import random

MEASURES = [
    # id, name, source, part, weight, higher_is_better, definition
    ("M01", "Breast Cancer Screening", "HEDIS", "C", 1, 1, "Share of eligible women who had a recent mammogram."),
    ("M02", "Colorectal Cancer Screening", "HEDIS", "C", 1, 1, "Share of eligible members up to date on colorectal screening."),
    ("M03", "Controlling Blood Pressure", "HEDIS", "C", 3, 1, "Share of members with hypertension whose blood pressure is controlled."),
    ("M04", "Diabetes Eye Exam", "HEDIS", "C", 1, 1, "Share of members with diabetes who had an eye exam."),
    ("M05", "Diabetes Blood Sugar Control", "HEDIS", "C", 3, 1, "Share of members with diabetes whose blood sugar is controlled."),
    ("M06", "Statin Therapy for Cardiovascular Disease", "HEDIS", "C", 1, 1, "Share of members with heart disease who are on a statin."),
    ("M07", "Follow-up After Emergency Visit", "HEDIS", "C", 1, 1, "Share of ER visits followed by outpatient follow-up."),
    ("M08", "Plan All-Cause Readmissions", "HEDIS", "C", 3, 0, "Ratio of actual to expected hospital readmissions (lower is better)."),
    ("M09", "Getting Needed Care", "CAHPS", "C", 4, 1, "Survey: members report getting care and specialist visits when needed."),
    ("M10", "Getting Appointments Quickly", "CAHPS", "C", 4, 1, "Survey: members report timely appointments."),
    ("M11", "Customer Service", "CAHPS", "C", 4, 1, "Survey: members rate the plan's customer service."),
    ("M12", "Care Coordination", "CAHPS", "C", 4, 1, "Survey: members report their care is well coordinated."),
    ("M13", "Rating of Health Plan", "CAHPS", "C", 4, 1, "Survey: overall member rating of the plan."),
    ("M14", "Improving or Maintaining Physical Health", "HOS", "C", 3, 1, "Share of members whose physical health stayed the same or improved."),
    ("M15", "Improving or Maintaining Mental Health", "HOS", "C", 3, 1, "Share of members whose mental health stayed the same or improved."),
    ("M16", "Reducing the Risk of Falling", "HOS", "C", 1, 1, "Share of members who discussed and acted on fall risk."),
    ("M17", "Call Center: Interpreter Availability", "Admin", "C", 1, 1, "Share of test calls where an interpreter was available."),
    ("M18", "Complaints About the Plan", "Admin", "C", 4, 0, "Complaints per 1,000 members (lower is better)."),
    ("M19", "Members Choosing to Leave the Plan", "Admin", "C", 4, 0, "Voluntary disenrollment rate (lower is better)."),
    ("M20", "Timely Decisions About Appeals", "Admin", "C", 1, 1, "Share of appeals decided on time."),
    ("M21", "Medication Adherence: Diabetes", "Part D", "D", 3, 1, "Share of members taking diabetes medicine as prescribed."),
    ("M22", "Medication Adherence: Hypertension", "Part D", "D", 3, 1, "Share of members taking blood pressure medicine as prescribed."),
    ("M23", "Medication Adherence: Cholesterol", "Part D", "D", 3, 1, "Share of members taking statins as prescribed."),
    ("M24", "Medication Therapy Management Review", "Part D", "D", 1, 1, "Share of eligible members who got a comprehensive medication review."),
]

# mean, spread for the raw scores (percent-style except M08, M18, M19)
PARAMS = {
    "M08": (1.0, 0.12), "M18": (0.35, 0.18), "M19": (14.0, 5.0),
}
YEARS = [2024, 2025, 2026]


def _stable(text):
    return sum(ord(c) * (i + 1) for i, c in enumerate(text))


def _score(mid, q, rng):
    mu, sd = PARAMS.get(mid, (None, None))
    if mu is None:
        base = 55 + (_stable(mid) % 25)
        mu, sd = base, 9.0
    sign = -1 if mid in PARAMS else 1
    val = mu + sign * sd * (0.9 * q + 0.5 * rng.gauss(0, 1))
    if mid not in PARAMS:
        val = max(5.0, min(99.5, val))
    else:
        val = max(0.02, val)
    return round(val, 3)


def _quantile(vals, p):
    vals = sorted(vals)
    i = p * (len(vals) - 1)
    lo, hi = int(i), min(int(i) + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (i - lo)


def star(score, cut, higher):
    t2, t3, t4, t5 = cut
    if score is None:
        return None
    if higher:
        return 5 if score >= t5 else 4 if score >= t4 else 3 if score >= t3 else 2 if score >= t2 else 1
    return 5 if score < t5 else 4 if score < t4 else 3 if score < t3 else 2 if score < t2 else 1


def generate(n_contracts=140, seed=7):
    rng = random.Random(seed)
    contracts = [(f"D{1000 + i}", f"Demo Plan {i + 1:03d}", "MA-PD") for i in range(n_contracts)]
    latent = {c[0]: rng.gauss(0, 1) for c in contracts}

    raw = {}
    for cid, _, _ in contracts:
        for mid, *_ in MEASURES:
            raw[(cid, mid)] = None if rng.random() < 0.03 else _score(mid, latent[cid], rng)

    cutpoints, cut_latest = [], {}
    for mid, _, _, _, _, higher, _ in MEASURES:
        vals = [raw[(c[0], mid)] for c in contracts if raw[(c[0], mid)] is not None]
        qs = [_quantile(vals, p) for p in (0.2, 0.4, 0.6, 0.8)]
        t2, t3, t4, t5 = qs if higher else qs[::-1]  # lower-is-better: t5 is the smallest
        for y in YEARS:
            drift = (YEARS[-1] - y) * (0.6 if higher else -0.01 * abs(t2))
            if mid in PARAMS:
                f = [round(t - drift, 3) for t in (t2, t3, t4, t5)]
            else:
                f = [round(t - drift, 2) for t in (t2, t3, t4, t5)]
            cutpoints.append((y, mid, *f))
            if y == YEARS[-1]:
                cut_latest[mid] = f

    scores = []
    for cid, _, _ in contracts:
        for mid, _, _, _, _, higher, _ in MEASURES:
            s = raw[(cid, mid)]
            scores.append((cid, mid, s, star(s, cut_latest[mid], higher)))

    wmap = {m[0]: m[4] for m in MEASURES}
    summary = []
    for cid, _, _ in contracts:
        num = den = 0
        for c, mid, s, st in scores:
            if c == cid and st is not None:
                num += st * wmap[mid]
                den += wmap[mid]
        summary.append((cid, round(num * 2 / den) / 2))

    measures = [(m[0], m[1], m[2], m[3], m[4], m[5], m[6], None, None, None) for m in MEASURES]
    return {
        "contracts": contracts, "measures": measures, "scores": scores,
        "cutpoints": cutpoints, "summary": summary,
        "meta": {"source": "demo", "year": str(YEARS[-1]), "cutpoint_source": "synthetic"},
    }
