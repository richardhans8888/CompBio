"""
Join Taiwan weekly case counts to weekly weather and build lagged features.

Input   data/processed/taiwan_cases_long.csv   region, yearweek, year, week, cases
        data/raw/weather/weather-<region>.csv  NASA POWER daily point data
Output  data/processed/taiwan_model_table.csv  one row per region-week, model ready

Two things here are easy to get wrong and are handled explicitly:

1. EPIDEMIOLOGICAL WEEKS.  Taiwan NIDSS numbers weeks the MMWR way: weeks run
   Sunday to Saturday, and a week belongs to the year containing its Wednesday.
   Week 1 of 2003 therefore starts on 2002-12-29, which is what the NIDSS page
   reports. Using ISO weeks instead would shift some years by a week and put
   every lag out of step with the cases.

2. WIND DIRECTION IS CIRCULAR.  Averaging 350 degrees and 10 degrees
   arithmetically gives 180, pointing the opposite way. Direction is averaged
   as unit vectors and carried into the model as sin/cos components.
"""
import csv, math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "data" / "processed" / "taiwan_cases_long.csv"
WX    = ROOT / "data" / "raw" / "weather"
OUT   = ROOT / "data" / "processed" / "taiwan_model_table.csv"

MISSING = -999.0


# ---------------------------------------------------------------- epi weeks
def epi_year_week(d: date) -> tuple[int, int]:
    """MMWR epidemiological year and week for a date (weeks start Sunday)."""
    wday = (d.weekday() + 1) % 7              # Mon=0 -> 1 ... Sun=6 -> 0
    week_start = d - timedelta(days=wday)     # the Sunday
    year = (week_start + timedelta(days=3)).year   # year of the Wednesday

    jan1 = date(year, 1, 1)
    j_wday = (jan1.weekday() + 1) % 7
    first_start = jan1 - timedelta(days=j_wday)
    if (first_start + timedelta(days=3)).year < year:
        first_start += timedelta(days=7)

    week = (week_start - first_start).days // 7 + 1
    return year, week


def _self_test() -> None:
    assert epi_year_week(date(2002, 12, 29)) == (2003, 1), "week 1/2003 anchor"
    assert epi_year_week(date(2003, 1, 4))   == (2003, 1), "week 1/2003 end"
    assert epi_year_week(date(2003, 1, 5))   == (2003, 2), "week 2/2003 start"
    assert epi_year_week(date(2003, 12, 28)) == (2003, 53), "2003 has 53 weeks"


# ---------------------------------------------------------------- weather
def read_weather(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    start = next(i for i, l in enumerate(lines) if "-END HEADER-" in l) + 1
    rdr = csv.DictReader(lines[start:])
    out = []
    for r in rdr:
        if not r.get("YEAR"):
            continue
        d = date(int(r["YEAR"]), 1, 1) + timedelta(days=int(r["DOY"]) - 1)
        rec = {"date": d}
        for k, v in r.items():
            if k in ("YEAR", "DOY"):
                continue
            try:
                f = float(v)
            except (TypeError, ValueError):
                f = None
            rec[k] = None if f is None or f <= MISSING else f
        out.append(rec)
    return out


def weekly(daily: list[dict]) -> dict:
    """Aggregate days into epi weeks. Rain sums, temperature averages, wind peaks."""
    buckets = defaultdict(list)
    for rec in daily:
        buckets[epi_year_week(rec["date"])].append(rec)

    def vals(rows, key):
        return [r[key] for r in rows if r.get(key) is not None]

    out = {}
    for yw, rows in buckets.items():
        if len(rows) < 4:          # partial week at either end of the record
            continue
        rain = vals(rows, "PRECTOTCORR")
        t    = vals(rows, "T2M")
        tmx  = vals(rows, "T2M_MAX")
        tmn  = vals(rows, "T2M_MIN")
        rh   = vals(rows, "RH2M")
        ws   = vals(rows, "WS10M")
        wsx  = vals(rows, "WS10M_MAX")
        wd   = vals(rows, "WD10M")

        # circular mean of wind direction, weighted by nothing (unit vectors)
        if wd:
            sx = sum(math.sin(math.radians(a)) for a in wd) / len(wd)
            cx = sum(math.cos(math.radians(a)) for a in wd) / len(wd)
        else:
            sx = cx = None

        out[yw] = {
            "rain_mm":   round(sum(rain), 2) if rain else None,
            "rain_max":  round(max(rain), 2) if rain else None,
            "t_mean":    round(sum(t) / len(t), 2) if t else None,
            "t_max":     round(max(tmx), 2) if tmx else None,
            "t_min":     round(min(tmn), 2) if tmn else None,
            "rh_mean":   round(sum(rh) / len(rh), 2) if rh else None,
            "ws_mean":   round(sum(ws) / len(ws), 2) if ws else None,
            "ws_max":    round(max(wsx), 2) if wsx else None,
            "wd_sin":    round(sx, 4) if sx is not None else None,
            "wd_cos":    round(cx, 4) if cx is not None else None,
            "n_days":    len(rows),
        }
    return out


# ---------------------------------------------------------------- assembly
# Wind DIRECTION is deliberately excluded. NASA POWER's WD10M field is corrupt
# for this record from 2012-12-31 onward: 5,025 of 8,677 days carry values far
# outside 0-360 (e.g. -8908, -76340) rather than a bearing. Keeping it would
# have silently discarded 717 of 1,240 weeks per region. Wind SPEED is intact
# and is the wind variable the literature actually reports as significant.
LAGS = {"rain_mm": range(0, 7), "rain_max": range(0, 4), "t_mean": range(0, 5),
        "t_max": range(0, 3), "rh_mean": range(0, 5), "ws_mean": range(0, 5),
        "ws_max": range(0, 5)}
ROLLING = [4, 8, 12]          # cumulative rainfall windows, in weeks


def main() -> None:
    _self_test()

    cases = defaultdict(dict)
    for r in csv.DictReader(CASES.open()):
        cases[r["region"]][(int(r["year"]), int(r["week"]))] = int(r["cases"])

    rows, skipped = [], 0
    for region in sorted(cases):
        path = WX / f"weather-{region.lower()}.csv"
        if not path.exists():
            print(f"  ! no weather file for {region}, skipped")
            continue
        wx = weekly(read_weather(path))

        # chronological list of this region's weeks, so lags are positional
        weeks = sorted(cases[region])
        for i, yw in enumerate(weeks):
            if yw not in wx:
                skipped += 1
                continue
            row = {"region": region, "year": yw[0], "week": yw[1],
                   "yearweek": f"{yw[0]}{yw[1]:02d}", "cases": cases[region][yw]}

            ok = True
            for var, lagrange in LAGS.items():
                for L in lagrange:
                    j = i - L
                    v = wx.get(weeks[j])[var] if j >= 0 and weeks[j] in wx else None
                    if v is None:
                        ok = False
                    row[f"{var}_lag{L}"] = v
            for w in ROLLING:
                vs = [wx[weeks[j]]["rain_mm"] for j in range(i - w + 1, i + 1)
                      if j >= 0 and weeks[j] in wx and wx[weeks[j]]["rain_mm"] is not None]
                row[f"rain_sum{w}w"] = round(sum(vs), 2) if len(vs) == w else None
                if len(vs) != w:
                    ok = False

            # seasonal position, as a smooth pair rather than a raw week number
            ang = 2 * math.pi * yw[1] / 52.0
            row["week_sin"] = round(math.sin(ang), 4)
            row["week_cos"] = round(math.cos(ang), 4)

            if ok:
                rows.append(row)
            else:
                skipped += 1

    if not rows:
        raise SystemExit("no complete rows produced")

    rows.sort(key=lambda r: (r["region"], r["year"], r["week"]))
    cols = list(rows[0].keys())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    total = sum(r["cases"] for r in rows)
    zero = sum(1 for r in rows if r["cases"] == 0)
    yrs = sorted({r["year"] for r in rows})
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  {len(rows)} rows x {len(cols)} columns")
    print(f"  {yrs[0]}-{yrs[-1]}, {total} cases, {zero} zero-weeks ({100*zero/len(rows):.1f}%)")
    print(f"  dropped {skipped} region-weeks lacking full lag history")
    print(f"  features: {len(cols)-5} predictors")


if __name__ == "__main__":
    main()
