"""
Turn the Open-Meteo JSON into one tidy CSV per point, in the same shape as the
NASA POWER files, so the feature builders can read either.

Also prints the check that actually matters: does ERA5-Land soil moisture agree
with our 150 mm bucket model? If it does, the bucket is defensible. If it does
not, ERA5-Land replaces it.
"""
import json, csv, sys
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "raw" / "soilmoisture"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

COLS = ["soil_moisture_0_to_7cm_mean", "soil_moisture_7_to_28cm_mean",
        "soil_moisture_28_to_100cm_mean", "soil_moisture_100_to_255cm_mean",
        "et0_fao_evapotranspiration", "precipitation_sum", "temperature_2m_mean"]
SHORT = {"soil_moisture_0_to_7cm_mean": "sm_l1", "soil_moisture_7_to_28cm_mean": "sm_l2",
         "soil_moisture_28_to_100cm_mean": "sm_l3",
         "soil_moisture_100_to_255cm_mean": "sm_l4",
         "et0_fao_evapotranspiration": "et0", "precipitation_sum": "rain",
         "temperature_2m_mean": "t_mean"}

files = sorted(SRC.glob("sm-*.json"))
if not files:
    sys.exit(f"no JSON files in {SRC} - run scripts/download_soil_moisture.sh first")

rows_all = []
for f in files:
    name = f.stem.replace("sm-", "")
    d = json.loads(f.read_text())
    if "daily" not in d:
        print(f"!! {f.name} has no 'daily' block - keys present: {list(d)[:8]}")
        continue
    day = d["daily"]
    t = day["time"]
    missing = [c for c in COLS if c not in day]
    if missing:
        print(f"!! {f.name} missing columns: {missing}")
    out = OUT / f"soilmoisture-{name}.csv"
    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date"] + [SHORT[c] for c in COLS if c in day])
        for i, ts in enumerate(t):
            w.writerow([ts] + [day[c][i] for c in COLS if c in day])
    nn = sum(1 for v in day.get(COLS[0], []) if v is not None)
    print(f"wrote {out.name:34s} {len(t):6d} days, {nn} non-missing surface values")
    rows_all.append((name, day))

# ---- the check that matters: ERA5-Land vs our bucket -------------------
try:
    import numpy as np
except ImportError:
    sys.exit("\ninstall numpy to run the bucket comparison:  pip install numpy")

tw = OUT / "taiwan_model_table_v2.csv"
if not tw.exists():
    print("\n(skipping bucket comparison - build taiwan_model_table_v2.csv first)")
    sys.exit(0)

sys.path.insert(0, str(ROOT / "scripts"))
from build_features_v2 import epi_year_week, REGION_NAME

print("\nDoes ERA5-Land soil moisture agree with our 150 mm bucket?")
print(f"{'region':10s} {'r vs layer1':>12s} {'r vs layer2':>12s} "
      f"{'r vs layer3':>12s} {'r vs layer4':>12s}")

bucket = {}
for r in csv.DictReader(tw.open()):
    bucket[(r["region"], int(r["year"]), int(r["week"]))] = float(r["sm_mean_lag0"])

for slug, region in REGION_NAME.items():
    p = OUT / f"soilmoisture-{slug}.csv"
    if not p.exists():
        continue
    wk = {}
    for r in csv.DictReader(p.open()):
        y, m, dd = (int(x) for x in r["date"].split("-"))
        k = epi_year_week(date(y, m, dd))
        wk.setdefault(k, []).append(r)
    cols = ["sm_l1", "sm_l2", "sm_l3", "sm_l4"]
    series = {c: [] for c in cols}
    buck = []
    for k, recs in sorted(wk.items()):
        if len(recs) != 7 or (region, k[0], k[1]) not in bucket:
            continue
        try:
            vals = {c: np.mean([float(x[c]) for x in recs]) for c in cols}
        except (ValueError, KeyError):
            continue
        if any(np.isnan(v) for v in vals.values()):
            continue
        for c in cols:
            series[c].append(vals[c])
        buck.append(bucket[(region, k[0], k[1])])
    if len(buck) < 100:
        print(f"{region:10s} too few overlapping weeks ({len(buck)})")
        continue
    rs = [np.corrcoef(series[c], buck)[0, 1] for c in cols]
    print(f"{region:10s} " + " ".join(f"{v:12.3f}" for v in rs) + f"   n={len(buck)}")

print("""
How to read this:
  high r with layer 1 or 2  -> our bucket is a fair surface model, keep it
  low r everywhere          -> replace the bucket with ERA5-Land
  layer 3 / 4 behave differently from layer 1 / 2 -> the deep reservoir is a
      genuinely separate variable, which is the Ribolzi 2022 result and the
      reason this download was worth doing
""")
