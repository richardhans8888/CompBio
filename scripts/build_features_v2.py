"""
Build a mechanistic feature table for melioidosis risk.

Beyond rainfall lags: a soil water-balance bucket, saturation duration,
wetting events, aerosolisation potential, vapour pressure deficit and
antecedent precipitation indices. Each feature has a stated mechanism.
"""
from pathlib import Path
from datetime import date, timedelta
import math
import csv

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

# latitude of each NASA POWER point, needed for extraterrestrial radiation
LAT = {"kaoping": 22.63, "southern": 23.10, "central": 24.15,
       "northern": 24.90, "taipei": 25.03, "eastern": 23.40}
REGION_NAME = {"kaoping": "Kaoping", "southern": "Southern", "central": "Central",
               "northern": "Northern", "taipei": "Taipei", "eastern": "Eastern"}

SOIL_CAP = 150.0      # mm, plausible rooting-zone capacity for a rice soil
SAT_THRESHOLD = 0.80  # saturation fraction above which the soil counts as saturated


# ---------------------------------------------------------------- MMWR weeks
def epi_year_week(d: date) -> tuple[int, int]:
    """MMWR epidemiological year and week (weeks start Sunday)."""
    wday = (d.weekday() + 1) % 7
    week_start = d - timedelta(days=wday)
    year = (week_start + timedelta(days=3)).year
    jan1 = date(year, 1, 1)
    j_wday = (jan1.weekday() + 1) % 7
    first_start = jan1 - timedelta(days=j_wday)
    if (first_start + timedelta(days=3)).year < year:
        first_start += timedelta(days=7)
    week = (week_start - first_start).days // 7 + 1
    return year, week


assert epi_year_week(date(2003, 1, 1)) == (2003, 1)
assert epi_year_week(date(2002, 12, 29)) == (2003, 1)


# ------------------------------------------------------------------- physics
def ra_mm(lat_deg: float, doy: int) -> float:
    """Extraterrestrial radiation in mm/day equivalent (FAO-56 eq. 21)."""
    phi = math.radians(lat_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)
    delta = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
    x = -math.tan(phi) * math.tan(delta)
    x = max(-1.0, min(1.0, x))
    ws = math.acos(x)
    return (24 * 60 / math.pi) * 0.0820 * dr * (
        ws * math.sin(phi) * math.sin(delta)
        + math.cos(phi) * math.cos(delta) * math.sin(ws)
    ) * 0.408  # MJ/m2/day -> mm/day


def pet_hargreaves(ra, tmean, tmax, tmin):
    """Reference evapotranspiration, Hargreaves-Samani. Needs no radiation data."""
    rng = max(tmax - tmin, 0.0)
    return max(0.0023 * ra * (tmean + 17.8) * math.sqrt(rng), 0.0)


def vpd_kpa(tmean, rh):
    """Vapour pressure deficit. High VPD dries the top soil and suppresses release."""
    es = 0.6108 * math.exp(17.27 * tmean / (tmean + 237.3))
    return max(es * (1 - rh / 100.0), 0.0)


# ----------------------------------------------------------- read daily file
def read_power(path: Path):
    rows = []
    with path.open() as f:
        lines = f.read().splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("YEAR,DOY")) + 1
    hdr = lines[start - 1].split(",")
    idx = {name: i for i, name in enumerate(hdr)}
    for line in lines[start:]:
        if not line.strip():
            continue
        p = line.split(",")
        try:
            yr, doy = int(p[idx["YEAR"]]), int(p[idx["DOY"]])
            rec = {k: float(p[idx[k]]) for k in
                   ("PRECTOTCORR", "T2M", "T2M_MAX", "T2M_MIN", "RH2M", "WS10M", "WS10M_MAX")}
        except (ValueError, KeyError):
            continue
        if any(v <= -900 for v in rec.values()):
            continue
        rec["date"] = date(yr, 1, 1) + timedelta(days=doy - 1)
        rec["doy"] = doy
        rows.append(rec)
    rows.sort(key=lambda r: r["date"])
    return rows


# -------------------------------------------------- daily mechanistic series
def add_daily_mechanics(rows, lat):
    """Soil bucket, wetting events, aerosol index. Mutates rows in place."""
    storage = SOIL_CAP * 0.3          # arbitrary start; first year is burn-in
    dry_run = 0
    for r in rows:
        ra = ra_mm(lat, r["doy"])
        pet = pet_hargreaves(ra, r["T2M"], r["T2M_MAX"], r["T2M_MIN"])
        p = r["PRECTOTCORR"]

        # bucket: evaporative demand scales with how wet the soil already is
        frac = storage / SOIL_CAP
        actual_et = min(pet * frac, storage)
        storage = storage + p - actual_et
        excess = max(storage - SOIL_CAP, 0.0)   # saturation excess / standing water
        storage = min(storage, SOIL_CAP)
        sat = storage / SOIL_CAP

        # a dry spell broken by heavy rain is the classic mobilisation event
        wet = p >= 1.0
        event = 1 if (p >= 10.0 and dry_run >= 10) else 0
        dry_run = 0 if wet else dry_run + 1

        r["pet"] = pet
        r["wb"] = p - pet
        r["sm"] = sat
        r["excess"] = excess
        r["vpd"] = vpd_kpa(r["T2M"], r["RH2M"])
        r["dtr"] = r["T2M_MAX"] - r["T2M_MIN"]
        r["aerosol"] = r["WS10M_MAX"] * sat      # wind over wet ground
        r["wet"] = 1 if wet else 0
        r["event"] = event
        r["dry_run"] = dry_run

    # antecedent precipitation indices with three memory lengths
    for k, name in ((0.85, "api85"), (0.95, "api95"), (0.98, "api98")):
        acc = 0.0
        for r in rows:
            acc = acc * k + r["PRECTOTCORR"]
            r[name] = acc
    return rows


def gini(vals):
    v = sorted(x for x in vals if x >= 0)
    n = len(v)
    s = sum(v)
    if n == 0 or s == 0:
        return 0.0
    cum = sum((i + 1) * x for i, x in enumerate(v))
    return (2 * cum) / (n * s) - (n + 1) / n


# ----------------------------------------------------- weekly aggregation
def weekly(rows):
    buckets = {}
    for r in rows:
        buckets.setdefault(epi_year_week(r["date"]), []).append(r)
    out = {}
    for key, days in buckets.items():
        if len(days) != 7:            # drop partial weeks at the file edges
            continue
        rain = [d["PRECTOTCORR"] for d in days]
        out[key] = {
            "rain_mm": sum(rain),
            "rain_max": max(rain),
            "rain_gini": gini(rain),
            "days_gt10": sum(1 for x in rain if x >= 10),
            "days_gt25": sum(1 for x in rain if x >= 25),
            "wet_days": sum(d["wet"] for d in days),
            "t_mean": sum(d["T2M"] for d in days) / 7,
            "t_max": max(d["T2M_MAX"] for d in days),
            "dtr_mean": sum(d["dtr"] for d in days) / 7,
            "rh_mean": sum(d["RH2M"] for d in days) / 7,
            "ws_mean": sum(d["WS10M"] for d in days) / 7,
            "ws_max": max(d["WS10M_MAX"] for d in days),
            "pet_sum": sum(d["pet"] for d in days),
            "wb_sum": sum(d["wb"] for d in days),
            "vpd_mean": sum(d["vpd"] for d in days) / 7,
            "vpd_min": min(d["vpd"] for d in days),
            "sm_mean": sum(d["sm"] for d in days) / 7,
            "sm_max": max(d["sm"] for d in days),
            "sm_min": min(d["sm"] for d in days),
            "sat_days": sum(1 for d in days if d["sm"] >= SAT_THRESHOLD),
            "excess_mm": sum(d["excess"] for d in days),
            "aerosol_mean": sum(d["aerosol"] for d in days) / 7,
            "aerosol_max": max(d["aerosol"] for d in days),
            "events": sum(d["event"] for d in days),
            "dry_run_max": max(d["dry_run"] for d in days),
            "api85": days[-1]["api85"],
            "api95": days[-1]["api95"],
            "api98": days[-1]["api98"],
        }
    return out


BASE = ["rain_mm", "rain_max", "rain_gini", "days_gt10", "days_gt25", "wet_days",
        "t_mean", "t_max", "dtr_mean", "rh_mean", "ws_mean", "ws_max",
        "pet_sum", "wb_sum", "vpd_mean", "vpd_min",
        "sm_mean", "sm_max", "sm_min", "sat_days", "excess_mm",
        "aerosol_mean", "aerosol_max", "events", "dry_run_max",
        "api85", "api95", "api98"]

# how far back each feature is allowed to reach, in weeks
LAGS = {
    "rain_mm": 7, "rain_max": 4, "rain_gini": 3, "days_gt10": 5, "days_gt25": 4,
    "wet_days": 4, "t_mean": 5, "t_max": 3, "dtr_mean": 3, "rh_mean": 5,
    "ws_mean": 5, "ws_max": 5, "pet_sum": 4, "wb_sum": 7, "vpd_mean": 5,
    "vpd_min": 3, "sm_mean": 7, "sm_max": 5, "sm_min": 4, "sat_days": 7,
    "excess_mm": 6, "aerosol_mean": 6, "aerosol_max": 5, "events": 7,
    "dry_run_max": 4, "api85": 3, "api95": 4, "api98": 5,
}
ROLL = {"rain_mm": [4, 8, 12], "sm_mean": [4, 8, 12], "sat_days": [4, 8, 12],
        "excess_mm": [4, 8, 12], "events": [4, 8, 12], "wb_sum": [4, 8, 12],
        "aerosol_mean": [4, 8]}


def week_order(keys):
    return sorted(keys)


def main():
    # cases
    cases = {}
    with (OUT / "taiwan_cases_long.csv").open() as f:
        for row in csv.DictReader(f):
            cases[(row["region"], int(row["year"]), int(row["week"]))] = int(row["cases"])

    header = None
    out_rows = []
    for slug, lat in LAT.items():
        rows = add_daily_mechanics(read_power(RAW / "weather" / f"weather-{slug}.csv"), lat)
        wk = weekly(rows)
        order = week_order(wk.keys())
        pos = {k: i for i, k in enumerate(order)}
        region = REGION_NAME[slug]

        for k in order:
            i = pos[k]
            feats = {}
            ok = True
            for name in BASE:
                for lag in range(LAGS[name] + 1):
                    j = i - lag
                    if j < 0:
                        ok = False
                        break
                    feats[f"{name}_lag{lag}"] = wk[order[j]][name]
                if not ok:
                    break
            if not ok:
                continue
            for name, windows in ROLL.items():
                for w in windows:
                    if i - w + 1 < 0:
                        ok = False
                        break
                    vals = [wk[order[i - d]][name] for d in range(w)]
                    feats[f"{name}_roll{w}"] = sum(vals)
                if not ok:
                    break
            if not ok:
                continue

            y, w_ = k
            if (region, y, w_) not in cases:
                continue
            feats["week_sin"] = math.sin(2 * math.pi * w_ / 52.0)
            feats["week_cos"] = math.cos(2 * math.pi * w_ / 52.0)
            rec = {"region": region, "year": y, "week": w_,
                   "yearweek": f"{y}-{w_:02d}", "cases": cases[(region, y, w_)]}
            rec.update(feats)
            if header is None:
                header = list(rec.keys())
            out_rows.append(rec)

    out_rows.sort(key=lambda r: (r["year"], r["week"], r["region"]))
    path = OUT / "taiwan_model_table_v2.csv"
    with path.open("w", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=header)
        wtr.writeheader()
        wtr.writerows(out_rows)

    npred = len(header) - 5
    tot = sum(r["cases"] for r in out_rows)
    print(f"wrote {path}")
    print(f"rows {len(out_rows)}  predictors {npred}  cases {tot}")
    print(f"weeks with >=1 case: {sum(1 for r in out_rows if r['cases'] > 0)} "
          f"({100*sum(1 for r in out_rows if r['cases']>0)/len(out_rows):.1f}%)")
    print("years", min(r["year"] for r in out_rows), "-", max(r["year"] for r in out_rows))


if __name__ == "__main__":
    main()
