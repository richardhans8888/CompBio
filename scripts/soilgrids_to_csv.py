"""
Flatten the SoilGrids JSON into one row per point.

Rewritten to be robust: SoilGrids does not always return the same depth labels
or the same scaling field for every point, and the first version silently
produced NaN whenever it hit a variant. This version tries every known shape,
counts what it found, and tells you per-site how many values it recovered
instead of quietly writing blanks.
"""
import json, csv, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "raw" / "soilgrids"
OUT = ROOT / "data" / "processed" / "soilgrids.csv"

files = sorted(SRC.glob("soil-*.json"))
if not files:
    sys.exit(f"nothing in {SRC} - run scripts/download_soilgrids.sh first")

def depth_label(dep):
    """SoilGrids has used 'label', and nested range dicts, across versions."""
    if isinstance(dep.get("label"), str):
        return dep["label"]
    rng = dep.get("range") or {}
    top, bot = rng.get("top_depth"), rng.get("bottom_depth")
    unit = rng.get("unit_depth", "cm")
    if top is not None and bot is not None:
        return f"{top}-{bot}{unit}"
    return dep.get("name") or "unknown"

def mean_value(dep):
    """The mean can sit under values.mean, or values.Q0.5, or straight on dep."""
    v = dep.get("values")
    if isinstance(v, dict):
        for k in ("mean", "Q0.5", "Q0_5", "median"):
            if v.get(k) is not None:
                return float(v[k])
    if dep.get("mean") is not None:
        return float(dep["mean"])
    return None

def scale_of(layer):
    """d_factor divides the stored integer; absent or zero means no scaling."""
    um = layer.get("unit_measure") or {}
    for k in ("d_factor", "conversion_factor", "factor"):
        f = um.get(k)
        if isinstance(f, (int, float)) and f not in (0, None):
            return float(f)
    return 1.0

rows, allcols, report = [], set(), []
for f in files:
    site = f.stem.replace("soil-", "")
    try:
        d = json.loads(f.read_text())
    except json.JSONDecodeError as e:
        report.append((site, 0, 0, f"bad JSON: {e}")); continue
    layers = (d.get("properties") or {}).get("layers") or []
    if not layers:
        snippet = json.dumps(d)[:160]
        report.append((site, 0, 0, f"no layers; response begins {snippet}"))
        rows.append({"site": site}); continue
    rec, total, filled = {"site": site}, 0, 0
    for layer in layers:
        name = layer.get("name") or "unnamed"
        sc = scale_of(layer)
        for dep in layer.get("depths", []):
            total += 1
            v = mean_value(dep)
            if v is None:
                continue
            col = f"{name}_{depth_label(dep).replace('-', '_')}"
            rec[col] = v / sc
            allcols.add(col); filled += 1
    rows.append(rec)
    report.append((site, filled, total, "" if filled else "all values were null"))

cols = ["site"] + sorted(allcols)
with OUT.open("w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
    w.writeheader(); w.writerows(rows)

print(f"wrote {OUT}")
print(f"\n{'site':14s} {'values found':>13s} {'cells':>7s}  note")
bad = 0
for site, filled, total, note in report:
    if filled == 0:
        bad += 1
    print(f"{site:14s} {filled:13d} {total:7d}  {note}")

if bad:
    print(f"\n{bad} site(s) still produced nothing. Run:")
    print("    python3 scripts/diagnose_soilgrids.py")
    print("and send Claude the output - the JSON shape differs from what this")
    print("parser expects and guessing further would risk silent wrong values.")
    sys.exit(1)

KEY = [c for c in cols if c.startswith(("phh2o_0_5", "phh2o_30_60", "clay_0_5",
                                        "sand_0_5", "soc_0_5"))]
if KEY:
    print(f"\n{'site':14s} " + " ".join(f"{c:>16s}" for c in KEY))
    for r in rows:
        print(f"{r['site']:14s} " +
              " ".join(f"{r.get(c, float('nan')):16.1f}" for c in KEY))
    print("""
Palasatien et al. 2008 found pH 5.0-6.0 the major determinant of
B. pseudomallei presence, and the SE Asia MaxEnt study found Acrisols
(acidic, clay-rich) favourable. Compare the Taiwan rows against the West
African rows: a sharp difference is a concrete limit on transferability that
weather features cannot see - exactly what expD and expG2 measured but could
not explain.
""")
