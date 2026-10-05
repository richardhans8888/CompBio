"""Same mechanistic features for the eight West African sites. No case labels exist there."""
import sys, csv, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_features_v2 import (read_power, add_daily_mechanics, weekly, epi_year_week,
                      BASE, LAGS, ROLL)

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "weather_africa"
OUT = ROOT / "data" / "processed" / "africa_model_table_v2.csv"

SITES = {"koutiala": (12.39, "Mali"), "sikasso": (11.32, "Mali"),
         "bamako": (12.65, "Mali"), "segou": (13.43, "Mali"),
         "mopti": (14.49, "Mali"), "bobo": (11.18, "Burkina Faso"),
         "ouagadougou": (12.37, "Burkina Faso"), "korhogo": (9.46, "Cote d'Ivoire")}

header = None
out = []
for slug, (lat, country) in SITES.items():
    rows = add_daily_mechanics(read_power(RAW / f"weather-{slug}.csv"), lat)
    wk = weekly(rows)
    order = sorted(wk.keys())
    pos = {k: i for i, k in enumerate(order)}
    ann = {}
    for k in order:
        ann.setdefault(k[0], []).append(wk[k]["rain_mm"])
    for k in order:
        i = pos[k]
        feats, ok = {}, True
        for name in BASE:
            for lag in range(LAGS[name] + 1):
                j = i - lag
                if j < 0:
                    ok = False; break
                feats[f"{name}_lag{lag}"] = wk[order[j]][name]
            if not ok: break
        if not ok: continue
        for name, windows in ROLL.items():
            for w in windows:
                if i - w + 1 < 0:
                    ok = False; break
                feats[f"{name}_roll{w}"] = sum(wk[order[i - d]][name] for d in range(w))
            if not ok: break
        if not ok: continue
        y, w_ = k
        feats["week_sin"] = math.sin(2 * math.pi * w_ / 52.0)
        feats["week_cos"] = math.cos(2 * math.pi * w_ / 52.0)
        rec = {"site": slug, "country": country, "lat": lat,
               "year": y, "week": w_, "yearweek": f"{y}-{w_:02d}"}
        rec.update(feats)
        if header is None: header = list(rec.keys())
        out.append(rec)

out.sort(key=lambda r: (r["year"], r["week"], r["site"]))
with OUT.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=header); w.writeheader(); w.writerows(out)

print("wrote", OUT, "rows", len(out), "sites", len({r['site'] for r in out}))
print("years", min(r["year"] for r in out), "-", max(r["year"] for r in out))
# annual rainfall per site, a basic sanity check against published climatology
import statistics
by = {}
for r in out:
    by.setdefault(r["site"], {}).setdefault(r["year"], 0.0)
    by[r["site"]][r["year"]] += r["rain_mm_lag0"]
print(f"\n{'site':14s} {'mean annual rain mm':>20s} {'mean soil sat':>14s} {'sat weeks/yr':>13s}")
for s in SITES:
    yrs = [v for k, v in by[s].items() if 2004 <= k <= 2025]
    sm = statistics.mean(r["sm_mean_lag0"] for r in out if r["site"] == s)
    satw = sum(1 for r in out if r["site"] == s and r["sm_mean_lag0"] >= 0.8) / 22
    print(f"{s:14s} {statistics.mean(yrs):20.0f} {sm:14.3f} {satw:13.1f}")
