"""
Merge the NIDSS regional melioidosis downloads into one long-format table.

Input   data/raw/cases/melioidosis-<region>-*.csv   (one file per region,
        weekly confirmed case counts, 2003-2026, from Taiwan NIDSS)
Output  data/processed/taiwan_cases_long.csv
        columns: region, yearweek, year, week, cases

Run from anywhere:  python3 scripts/build_cases.py
"""
import csv, glob
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW  = ROOT / "data" / "raw" / "cases"
OUT  = ROOT / "data" / "processed" / "taiwan_cases_long.csv"

REGION = {"central": "Central", "eastern": "Eastern", "kaoping": "Kaoping",
          "northern": "Northern", "southern": "Southern", "taipei": "Taipei"}


def load() -> list[dict]:
    rows = []
    for path in sorted(RAW.glob("melioidosis-*.csv")):
        key = next((k for k in REGION if k in path.name.lower()), None)
        if key is None:                      # skips the nationwide file
            continue
        text = path.read_text(encoding="utf-8-sig")
        for r in csv.reader(text.splitlines()):
            if r and r[0].strip() and r[0].strip()[0].isdigit():
                yw = r[0].strip()
                rows.append({"region": REGION[key], "yearweek": yw,
                             "year": int(yw[:4]), "week": int(yw[4:]),
                             "cases": int(r[1])})
    return rows


def main() -> None:
    rows = load()
    if not rows:
        raise SystemExit(f"No case files found in {RAW}")
    rows.sort(key=lambda d: (d["region"], d["year"], d["week"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["region", "yearweek", "year", "week", "cases"])
        w.writeheader()
        w.writerows(rows)

    total = sum(d["cases"] for d in rows)
    zero  = sum(1 for d in rows if d["cases"] == 0)
    regions = sorted({d["region"] for d in rows})
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  {len(rows)} rows · {len(regions)} regions · {total} cases")
    print(f"  zero-case region-weeks: {zero}/{len(rows)} = {100*zero/len(rows):.1f}%")


if __name__ == "__main__":
    main()
