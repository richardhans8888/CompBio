"""
expP - the decisive comparison the ERA5-Land download makes possible.

The bucket model located the melioidosis case peak to 2.3 weeks on average
against rainfall's 6.0. But ERA5-Land now shows the bucket correlates only
r = 0.36-0.67 with real modelled soil moisture, which is weak. So the
question is simple and the answer is not predictable from that correlation:

  WHICH representation of soil water actually locates the case season best?

Candidates: rainfall, our 150 mm bucket, and ERA5-Land layers 1-4
(0-7, 7-28, 28-100, 100-255 cm). Same circular-peak estimator, same
bootstrap over years, as expL.
"""
import csv, math, sys
from datetime import date
from pathlib import Path
import numpy as np
sys.path.insert(0, "/home/claude/exp/v2")
from build_v2 import epi_year_week, REGION_NAME
rng = np.random.default_rng(31)

UP = Path("/mnt/user-data/uploads/Computation Bio 1")
TW = Path("/home/claude/exp/v2/taiwan_model_table_v2.csv")

cases, bucket, rain_b = {}, {}, {}
for r in csv.DictReader(TW.open()):
    k = (r["region"], int(r["year"]), int(r["week"]))
    cases[k] = int(r["cases"])
    bucket[k] = float(r["sm_mean_lag0"])
    rain_b[k] = float(r["rain_mm_lag0"])

LAYERS = ["sm_l1", "sm_l2", "sm_l3", "sm_l4"]
era = {}
for slug, region in REGION_NAME.items():
    p = UP / f"data/processed/soilmoisture-{slug}.csv"
    if not p.exists():
        continue
    wk = {}
    for r in csv.DictReader(p.open()):
        y, m, d = (int(x) for x in r["date"].split("-"))
        k = epi_year_week(date(y, m, d))
        try:
            vals = {c: float(r[c]) for c in LAYERS}
        except (ValueError, KeyError):
            continue
        wk.setdefault(k, []).append(vals)
    for k, days in wk.items():
        if len(days) != 7:
            continue
        era[(region, k[0], k[1])] = {c: float(np.mean([d[c] for d in days]))
                                     for c in LAYERS}

def circ_peak(prof):
    p = np.asarray(prof, float)
    p = p - np.nanmin(p)
    ang = 2 * np.pi * (np.arange(1, 53) - 0.5) / 52
    ok = ~np.isnan(p)
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

SERIES = ["rainfall", "bucket 150mm", "ERA5 0-7cm", "ERA5 7-28cm",
          "ERA5 28-100cm", "ERA5 100-255cm"]
REG = [r for r in REGION_NAME.values()
       if sum(v for (rr, _, _), v in cases.items() if rr == r) >= 50]
print("regions with >=50 cases:", REG)
print(f"\n{'region':10s} {'cases':>6s} {'peak wk':>8s} | " +
      " | ".join(f"{s:>14s}" for s in SERIES))

rows, errs = [], {s: [] for s in SERIES}
for region in REG:
    keys = [k for k in era if k[0] == region and k in cases]
    keys.sort(key=lambda k: (k[1], k[2]))
    weeks = [k[2] for k in keys]
    yrs = np.array([k[1] for k in keys])
    series = {
        "rainfall": [rain_b[k] for k in keys],
        "bucket 150mm": [bucket[k] for k in keys],
        "ERA5 0-7cm": [era[k]["sm_l1"] for k in keys],
        "ERA5 7-28cm": [era[k]["sm_l2"] for k in keys],
        "ERA5 28-100cm": [era[k]["sm_l3"] for k in keys],
        "ERA5 100-255cm": [era[k]["sm_l4"] for k in keys],
    }
    cs = [cases[k] for k in keys]
    pc = circ_peak(profile(weeks, cs))
    out = {}
    for s in SERIES:
        e = wk_diff(circ_peak(profile(weeks, series[s])), pc)
        out[s] = e; errs[s].append(abs(e))
    print(f"{region:10s} {sum(cs):6d} {pc:8.1f} | " +
          " | ".join(f"{out[s]:+14.1f}" for s in SERIES))
    rows.append(dict(region=region, cases=sum(cs), peak_cases_wk=pc,
                     n_weeks=len(keys), **{s: out[s] for s in SERIES}))

print(f"\n{'':10s} {'':>6s} {'mean |error|':>8s} | " +
      " | ".join(f"{np.mean(errs[s]):14.2f}" for s in SERIES))

# bootstrap over years, pooled across regions, for the two best candidates
print("\nBootstrap over years (resampling whole years, pooled over regions)")
print(f"{'series':16s} {'mean |err| wk':>14s} {'95% CI':>18s}")
boot = {s: [] for s in SERIES}
for _ in range(2000):
    acc = {s: [] for s in SERIES}
    for region in REG:
        keys = [k for k in era if k[0] == region and k in cases]
        keys.sort(key=lambda k: (k[1], k[2]))
        uy = sorted({k[1] for k in keys})
        pick = set(rng.choice(uy, len(uy), replace=True).tolist())
        kk = [k for k in keys if k[1] in pick]
        if len(kk) < 200:
            continue
        ww = [k[2] for k in kk]
        pc = circ_peak(profile(ww, [cases[k] for k in kk]))
        src = {
            "rainfall": [rain_b[k] for k in kk],
            "bucket 150mm": [bucket[k] for k in kk],
            "ERA5 0-7cm": [era[k]["sm_l1"] for k in kk],
            "ERA5 7-28cm": [era[k]["sm_l2"] for k in kk],
            "ERA5 28-100cm": [era[k]["sm_l3"] for k in kk],
            "ERA5 100-255cm": [era[k]["sm_l4"] for k in kk],
        }
        for s in SERIES:
            acc[s].append(abs(wk_diff(circ_peak(profile(ww, src[s])), pc)))
    for s in SERIES:
        if acc[s]:
            boot[s].append(np.mean(acc[s]))
for s in SERIES:
    b = np.array(boot[s])
    lo, hi = np.percentile(b, [2.5, 97.5])
    print(f"{s:16s} {np.mean(errs[s]):14.2f} {f'[{lo:.2f}, {hi:.2f}]':>18s}")

# paired: is the best ERA5 layer better than our bucket?
best = min(SERIES[2:], key=lambda s: np.mean(errs[s]))
d = np.array(boot[best]) - np.array(boot["bucket 150mm"])
lo, hi = np.percentile(d, [2.5, 97.5])
p = 2 * min((d <= 0).mean(), (d >= 0).mean())
print(f"\n{best} minus bucket: {d.mean():+.2f} weeks  "
      f"95% CI [{lo:+.2f}, {hi:+.2f}]  p = {p:.3f}")
print("(negative means ERA5 is closer to the case peak than our bucket)")

with open("/home/claude/exp/v2/expP_timing_comparison.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
