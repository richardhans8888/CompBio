"""
Parse the Hydrology Data Rods ASCII output into CSVs, then run the test that
decides whether groundwater is worth a place in the paper:

  is groundwater recoverable from rainfall and temperature?

If R2 is low, groundwater carries information that no soil-moisture product and
no bucket model can supply, and the hypothesis "melioidosis timing tracks the
water table, not the rain" becomes testable. If R2 is high, groundwater is just
slow rainfall and we say so.
"""
import csv, sys
from pathlib import Path
from datetime import date, datetime

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "raw" / "groundwater"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

def parse(path):
    """Data Rods asc2: a header block, then 'YYYY-MM-DDTHH:MM:SS<tab>value' lines."""
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "Date", "ime")):
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

files = sorted(SRC.glob("*.txt"))
if not files:
    sys.exit(f"nothing in {SRC} - run scripts/download_groundwater.sh first")

series = {}
for f in files:
    label, name = f.stem.split("-", 1)
    rows = parse(f)
    if len(rows) < 100:
        print(f"!! {f.name}: only {len(rows)} usable rows")
        print("   first lines were:")
        for l in f.read_text().splitlines()[:6]:
            print("   ", l[:110])
        continue
    series.setdefault(name, {})[label] = dict(rows)
    print(f"parsed {f.name:28s} {len(rows):6d} days  "
          f"{rows[0][0]} to {rows[-1][0]}")

for name, byvar in series.items():
    labels = sorted(byvar)
    days = sorted(set().union(*[set(byvar[l]) for l in labels]))
    p = OUT / f"groundwater-{name}.csv"
    with p.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date"] + labels)
        for d in days:
            w.writerow([d.isoformat()] + [byvar[l].get(d, "") for l in labels])
    print(f"wrote  {p.name}  {len(days)} days, columns {labels}")

# ---- is groundwater just slow rainfall? --------------------------------
try:
    import numpy as np
    from sklearn.ensemble import ExtraTreesRegressor
    from sklearn.metrics import r2_score
except ImportError:
    sys.exit("\ninstall scikit-learn to run the information test:  pip install scikit-learn")

tw = OUT / "taiwan_model_table_v2.csv"
if not tw.exists():
    sys.exit("\n(build taiwan_model_table_v2.csv first to run the information test)")

sys.path.insert(0, str(ROOT / "scripts"))
from build_features_v2 import epi_year_week, REGION_NAME

rows = list(csv.DictReader(tw.open()))
feats = [c for c in rows[0] if c not in
         {"region", "year", "week", "yearweek", "cases"}]
RAIN_T = [i for i, f in enumerate(feats)
          if f.startswith(("rain_mm_lag", "rain_max_lag", "t_mean_lag",
                           "t_max_lag", "rain_mm_roll"))]
X = np.array([[float(r[c]) for c in feats] for r in rows])
key = [(r["region"], int(r["year"]), int(r["week"])) for r in rows]
yr = np.array([int(r["year"]) for r in rows])

print("\nIs groundwater recoverable from rainfall and temperature?")
print("(our bucket's soil saturation scored R2 = 0.875 on this test)")
print(f"\n{'region':10s} {'variable':10s} {'R2 from rain+temp':>18s} {'n weeks':>8s}")
for slug, region in REGION_NAME.items():
    p = OUT / f"groundwater-{slug}.csv"
    if not p.exists():
        continue
    recs = list(csv.DictReader(p.open()))
    cols = [c for c in recs[0] if c != "date"]
    wk = {}
    for r in recs:
        y, m, dd = (int(x) for x in r["date"].split("-"))
        wk.setdefault(epi_year_week(date(y, m, dd)), []).append(r)
    for col in cols:
        tgt, idx = [], []
        for i, k in enumerate(key):
            if k[0] != region or (k[1], k[2]) not in wk:
                continue
            vals = [float(x[col]) for x in wk[(k[1], k[2])] if x[col] not in ("", None)]
            if len(vals) < 5:
                continue
            tgt.append(float(np.mean(vals))); idx.append(i)
        if len(idx) < 300:
            print(f"{region:10s} {col:10s} {'too few weeks':>18s} {len(idx):8d}")
            continue
        idx = np.array(idx); tgt = np.array(tgt)
        tr = yr[idx] < 2018; te = ~tr
        if tr.sum() < 100 or te.sum() < 50:
            continue
        m_ = ExtraTreesRegressor(n_estimators=300, min_samples_leaf=2,
                                 n_jobs=-1, random_state=0)
        m_.fit(X[np.ix_(idx[tr], RAIN_T)], tgt[tr])
        r2 = r2_score(tgt[te], m_.predict(X[np.ix_(idx[te], RAIN_T)]))
        print(f"{region:10s} {col:10s} {r2:18.3f} {len(idx):8d}")

print("""
How to read this:
  R2 well below 0.875  -> groundwater carries information our weather features
      do not have. This is the result that makes the hypothesis worth testing,
      and it is the one thing in the data plan that could turn the core negative
      result positive.
  R2 near or above 0.875 -> groundwater here is slow rainfall. Report that
      honestly; it still strengthens the paper, because it closes off the most
      obvious "but you did not try X" objection.
""")
