"""
Parse the Data Rods output, then run the two tests that matter.

TEST 1 - REPLICATION. ERA5-Land said soil water at 28-100 cm locates the
melioidosis season (3.08 weeks error) while surface water barely beats rainfall
(5.58 vs 6.04). GLDAS-NOAH is an independent land-surface model with its own
four layers. If the same depth pattern appears, the finding is a property of
the soil, not of one reanalysis. If it does not, we report that.

TEST 2 - INFORMATION. Is groundwater recoverable from rainfall and temperature?
Our bucket's soil saturation scored R2 = 0.875 on this test, which is why
elaborating weather features could not help. Groundwater is the candidate that
escapes it.

Run:  python3 scripts/earthdata_to_csv.py
"""
import csv, math, sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "raw" / "earthdata"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "scripts"))
from build_features_v2 import epi_year_week, REGION_NAME

try:
    import numpy as np
except ImportError:
    sys.exit("pip3 install numpy scikit-learn")

files = sorted(SRC.glob("*.txt"))
if not files:
    sys.exit(f"nothing in {SRC} - run scripts/download_earthdata.sh first")

def parse(path):
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line[0] not in "0123456789":
            continue
        parts = line.replace("\t", " ").split()
        if len(parts) < 2:
            continue
        try:
            d = datetime.fromisoformat(parts[0].replace("Z", "")).date()
            v = float(parts[1])
        except ValueError:
            continue
        if v < -9000:
            continue
        rows.append((d, v))
    return rows

series = {}
for f in files:
    label, _, site = f.stem.rpartition("-")
    rows = parse(f)
    if len(rows) < 10:
        print(f"!! {f.name}: only {len(rows)} usable rows")
        continue
    series.setdefault(site, {})[label] = dict(rows)
    print(f"parsed {f.name:34s} {len(rows):6d} rows  {rows[0][0]} .. {rows[-1][0]}")

for site, byvar in sorted(series.items()):
    labels = sorted(byvar)
    days = sorted(set().union(*[set(byvar[l]) for l in labels]))
    p = OUT / f"earthdata-{site}.csv"
    with p.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date"] + labels)
        for d in days:
            w.writerow([d.isoformat()] + [byvar[l].get(d, "") for l in labels])
    print(f"wrote  {p.name}  {len(days)} dates, {len(labels)} variables")

# ---------------------------------------------------------------- shared setup
TW = OUT / "taiwan_model_table_v2.csv"
if not TW.exists():
    sys.exit("\nbuild taiwan_model_table_v2.csv first (scripts/build_features_v2.py)")

cases, bucket, rain = {}, {}, {}
trows = list(csv.DictReader(TW.open()))
for r in trows:
    k = (r["region"], int(r["year"]), int(r["week"]))
    cases[k] = int(r["cases"]); bucket[k] = float(r["sm_mean_lag0"])
    rain[k] = float(r["rain_mm_lag0"])

def circ_peak(prof):
    p = np.asarray(prof, float); p = p - np.nanmin(p)
    ang = 2 * np.pi * (np.arange(1, 53) - 0.5) / 52
    ok = ~np.isnan(p)
    if ok.sum() < 20:
        return float("nan")
    w = (math.atan2((p[ok] * np.sin(ang[ok])).sum(),
                    (p[ok] * np.cos(ang[ok])).sum()) / (2 * np.pi) * 52) % 52
    return w + 0.5

def wk_diff(a, b):
    d = (a - b) % 52
    return d if d <= 26 else d - 52

def profile(weeks, vals):
    return np.array([np.mean([v for v, w in zip(vals, weeks) if w == t])
                     if any(w == t for w in weeks) else np.nan
                     for t in range(1, 53)])

def weekly(site, label):
    """Weekly mean of a Data Rods series, keyed by (year, week)."""
    if site not in series or label not in series[site]:
        return None
    wk = {}
    for d, v in series[site][label].items():
        wk.setdefault(epi_year_week(d), []).append(v)
    return {k: float(np.mean(v)) for k, v in wk.items()}

BIG = [r for r in REGION_NAME.values()
       if sum(v for (rr, _, _), v in cases.items() if rr == r) >= 50]
SLUG = {v: k for k, v in REGION_NAME.items()}

# ==================================================== TEST 1: depth replication
DEPTHS = [("noah_sm_000_010", "GLDAS 0-10cm"), ("noah_sm_010_040", "GLDAS 10-40cm"),
          ("noah_sm_040_100", "GLDAS 40-100cm"), ("noah_sm_100_200", "GLDAS 100-200cm"),
          ("clsm_rootzone", "GLDAS root zone"), ("clsm_groundwater", "GLDAS groundwater")]

print("\n" + "=" * 74)
print("TEST 1 - does an independent model reproduce the depth pattern?")
print("ERA5-Land gave: rainfall 6.04 | 0-7cm 5.58 | 7-28cm 4.94 | 28-100cm 3.08 |")
print("                100-255cm 3.90 | our bucket 2.32   (mean |weeks| error)")
print("=" * 74)
print(f"\n{'series':20s} " + " ".join(f"{r[:9]:>10s}" for r in BIG) + f" {'mean|err|':>10s}")

results = []
for label, pretty in [("__rain", "rainfall"), ("__bucket", "our bucket 150mm")] + DEPTHS:
    errs, cells = [], []
    for region in BIG:
        keys = [k for k in cases if k[0] == region]
        if label == "__rain":
            src = {k: rain[k] for k in keys}
        elif label == "__bucket":
            src = {k: bucket[k] for k in keys}
        else:
            w = weekly(SLUG[region], label)
            if w is None:
                cells.append(float("nan")); continue
            src = {k: w[(k[1], k[2])] for k in keys if (k[1], k[2]) in w}
        kk = [k for k in keys if k in src]
        if len(kk) < 200:
            cells.append(float("nan")); continue
        weeks = [k[2] for k in kk]
        pc = circ_peak(profile(weeks, [cases[k] for k in kk]))
        pv = circ_peak(profile(weeks, [src[k] for k in kk]))
        e = wk_diff(pv, pc)
        cells.append(e); errs.append(abs(e))
    m = np.mean(errs) if errs else float("nan")
    print(f"{pretty:20s} " + " ".join(f"{c:+10.1f}" for c in cells) + f" {m:10.2f}")
    results.append(dict(series=pretty, mean_abs_err_wk=m,
                        **{r: c for r, c in zip(BIG, cells)}))

with (OUT.parent / "outputs" / "earthdata_depth_replication.csv").open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(results[0])); w.writeheader(); w.writerows(results)

print("""
How to read it: if the GLDAS rows improve with depth the way the ERA5 rows did,
two independent land-surface models agree that melioidosis timing is set by soil
water WELL BELOW the surface. That is a mechanistic claim, not a correlation,
and it is testable anywhere on Earth from free data.
""")

# ================================================== TEST 2: information content
print("=" * 74)
print("TEST 2 - is groundwater just slow rainfall?")
print("(our bucket's soil saturation was 87.5% recoverable from rain+temperature)")
print("=" * 74)
try:
    from sklearn.ensemble import ExtraTreesRegressor
    from sklearn.metrics import r2_score
except ImportError:
    sys.exit("pip3 install scikit-learn")

feats = [c for c in trows[0] if c not in
         {"region", "year", "week", "yearweek", "cases"}]
X = np.array([[float(r[c]) for c in feats] for r in trows])
RAIN_T = [i for i, f in enumerate(feats)
          if f.startswith(("rain_mm_lag", "rain_max_lag", "t_mean_lag",
                           "t_max_lag", "rain_mm_roll"))]
key = [(r["region"], int(r["year"]), int(r["week"])) for r in trows]
yr = np.array([int(r["year"]) for r in trows])

print(f"\n{'region':10s} {'variable':20s} {'R2 from rain+temp':>18s} {'n weeks':>8s}")
info = []
for region in BIG:
    for label, pretty in DEPTHS:
        w = weekly(SLUG[region], label)
        if w is None:
            continue
        idx = [i for i, k in enumerate(key)
               if k[0] == region and (k[1], k[2]) in w]
        if len(idx) < 300:
            continue
        idx = np.array(idx)
        tgt = np.array([w[(key[i][1], key[i][2])] for i in idx])
        tr = yr[idx] < 2018; te = ~tr
        if tr.sum() < 100 or te.sum() < 50:
            continue
        m = ExtraTreesRegressor(n_estimators=300, min_samples_leaf=2,
                                n_jobs=-1, random_state=0)
        m.fit(X[np.ix_(idx[tr], RAIN_T)], tgt[tr])
        r2 = r2_score(tgt[te], m.predict(X[np.ix_(idx[te], RAIN_T)]))
        print(f"{region:10s} {pretty:20s} {r2:18.3f} {len(idx):8d}")
        info.append(dict(region=region, variable=pretty, r2_from_weather=r2,
                         n_weeks=len(idx)))

if info:
    with (OUT.parent / "outputs" / "earthdata_information.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(info[0])); w.writeheader(); w.writerows(info)
    gw = [r["r2_from_weather"] for r in info if "groundwater" in r["variable"]]
    if gw:
        print(f"\ngroundwater mean R2 = {np.mean(gw):.3f}  (bucket was 0.875)")
        if np.mean(gw) < 0.7:
            print("""
BELOW 0.7 - groundwater carries information the weather features do not have.
This is the result that makes "melioidosis timing tracks the water table, not
the rain" a testable hypothesis rather than a guess, and it is the one addition
in the data plan that could turn the core negative result positive.""")
        else:
            print("""
Close to the bucket's 0.875 - groundwater here is largely slow rainfall. Report
it plainly; it still strengthens the paper by closing the most obvious
"but you did not try X" objection.""")
