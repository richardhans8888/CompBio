"""
Re-fetch SoilGrids at the nearest MAPPED cell, using curl rather than urllib.

Two separate problems are fixed here.

1. Masked cells. The first attempt reused the NASA POWER coordinates, which are
   centres of 0.5-degree weather cells. SoilGrids is a 250 m product with a mask
   over water, built-up land and bare rock, and returns "mean": null on a masked
   pixel. Kaoping 22.63/120.30 is central Kaohsiung; Mopti sits on the Niger
   inland delta; Ouagadougou is urban. So this searches a widening ring and takes
   the first properly mapped cell, recording the offset for the methods section.

2. urllib could not connect at all (URLError on every attempt) while curl
   downloaded the same URLs without trouble. That is the usual macOS system-Python
   situation: no CA bundle wired up, so every HTTPS call fails verification. Rather
   than patching SSL, this calls curl through subprocess - it already works on this
   machine, and it inherits any proxy settings correctly.

Points that already have complete data from the first download are reused, so
only the masked ones cost a request.

Resumable and cached. RUN IN YOUR OWN TERMINAL:
    python3 scripts/fix_soilgrids.py
"""
import json, csv, math, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "raw" / "soilgrids"
CACHE.mkdir(parents=True, exist_ok=True)
OUT = ROOT / "data" / "processed" / "soilgrids.csv"

if not shutil.which("curl"):
    sys.exit("curl not found on PATH - unexpected on macOS; tell Claude")

API = "https://rest.isric.org/soilgrids/v2.0/properties/query"
PROPS = ["phh2o", "clay", "sand", "silt", "soc", "bdod", "cec", "nitrogen"]
DEPTHS = ["0-5cm", "5-15cm", "15-30cm", "30-60cm", "60-100cm", "100-200cm"]
NCELLS = len(PROPS) * len(DEPTHS)

POINTS = {
    "kaoping": (22.63, 120.30), "southern": (23.10, 120.25),
    "central": (24.15, 120.68), "northern": (24.90, 121.10),
    "taipei": (25.03, 121.57),  "eastern": (23.40, 121.40),
    "koutiala": (12.39, -5.46), "sikasso": (11.32, -5.67),
    "bamako": (12.65, -8.00),   "segou": (13.43, -6.26),
    "mopti": (14.49, -4.20),    "bobo": (11.18, -4.30),
    "ouagadougou": (12.37, -1.52), "korhogo": (9.46, -5.63),
}
RINGS = [(0.0, 1), (0.05, 8), (0.10, 8), (0.20, 8), (0.35, 8), (0.50, 8)]


def candidates(lat, lon):
    seen = set()
    for off, n in RINGS:
        if off == 0:
            yield lat, lon, 0.0
            continue
        for k in range(n):
            a = 2 * math.pi * k / n
            dlat = off * math.cos(a)
            dlon = off * math.sin(a) / max(math.cos(math.radians(lat)), 0.2)
            key = (round(lat + dlat, 4), round(lon + dlon, 4))
            if key in seen:
                continue
            seen.add(key)
            yield key[0], key[1], 111.0 * math.hypot(
                dlat, dlon * math.cos(math.radians(lat)))


def fetch(lat, lon):
    """Returns (parsed_json, error_string). curl, not urllib - see module docstring."""
    url = (f"{API}?lon={lon}&lat={lat}&value=mean"
           + "".join(f"&property={p}" for p in PROPS)
           + "".join(f"&depth={d}" for d in DEPTHS))
    r = subprocess.run(
        ["curl", "-sS", "-m", "90", "--retry", "2", "--retry-delay", "5",
         "-w", "\n%{http_code}", "-A", "melioidosis-research/1.0", url],
        capture_output=True, text=True)
    if r.returncode != 0:
        return None, f"curl exit {r.returncode}: {r.stderr.strip()[:200]}"
    body, _, code = r.stdout.rpartition("\n")
    code = code.strip()
    if code == "429":
        return None, "RATE_LIMIT"
    if code != "200":
        return None, f"HTTP {code}: {body[:200]}"
    try:
        return json.loads(body), None
    except json.JSONDecodeError as e:
        return None, f"bad JSON ({e}): {body[:200]}"


def harvest(d):
    out = {}
    for layer in (d.get("properties") or {}).get("layers") or []:
        name = layer.get("name") or "?"
        sc = (layer.get("unit_measure") or {}).get("d_factor") or 1
        for dep in layer.get("depths", []):
            v = (dep.get("values") or {}).get("mean")
            if v is None:
                continue
            lab = dep.get("label") or "?"
            out[f"{name}_{lab.replace('-', '_')}"] = v / sc
    return out


# reuse anything already complete from the first download, to save requests
for site in POINTS:
    res = CACHE / f"resolved-{site}.json"
    old = CACHE / f"soil-{site}.json"
    if res.exists() or not old.exists():
        continue
    try:
        vals = harvest(json.loads(old.read_text()))
    except Exception:
        continue
    if len(vals) >= NCELLS * 0.75:
        lat, lon = POINTS[site]
        res.write_text(json.dumps({"values": vals, "offset_km": 0.0,
                                   "lat": lat, "lon": lon}))

rows, allcols, notes = [], set(), []
for site, (lat0, lon0) in POINTS.items():
    res = CACHE / f"resolved-{site}.json"
    if res.exists():
        c = json.loads(res.read_text())
        rows.append({"site": site, **c["values"]})
        allcols.update(c["values"])
        notes.append((site, len(c["values"]), c["offset_km"], c["lat"], c["lon"]))
        print(f"have    {site:14s} {len(c['values']):2d} values, "
              f"{c['offset_km']:.0f} km offset")
        continue

    got, errs = None, []
    for lat, lon, km in candidates(lat0, lon0):
        d, err = fetch(lat, lon)
        if err == "RATE_LIMIT":
            print(f"\nRATE LIMITED at {site}. Everything so far is cached - "
                  f"re-run this script in a few minutes and it resumes.")
            sys.exit(2)
        if err:
            errs.append(f"  {lat:.3f},{lon:.3f}  {err}")
            if len(errs) == 3:
                # three identical connection failures means it is not the data
                print(f"\n{site}: the first three requests all failed. "
                      f"This is a connection problem, not masked cells:")
                for e in errs:
                    print(e)
                print("\nStopping rather than retrying 30 more times. "
                      "Send the lines above to Claude.")
                sys.exit(1)
            time.sleep(4)
            continue
        vals = harvest(d)
        time.sleep(4)                       # SoilGrids rate-limits hard
        if len(vals) >= NCELLS * 0.75:
            got = (vals, km, lat, lon)
            break
        if vals:
            print(f"  {site}: only {len(vals)}/{NCELLS} values at "
                  f"{lat:.3f},{lon:.3f} ({km:.0f} km), widening")

    if got is None:
        print(f"FAILED  {site:14s} no mapped cell within 55 km")
        rows.append({"site": site})
        notes.append((site, 0, float("nan"), lat0, lon0))
        continue
    vals, km, lat, lon = got
    res.write_text(json.dumps({"values": vals, "offset_km": km,
                               "lat": lat, "lon": lon}))
    rows.append({"site": site, **vals})
    allcols.update(vals)
    notes.append((site, len(vals), km, lat, lon))
    print(f"ok      {site:14s} {len(vals):2d} values at {lat:.3f},{lon:.3f} "
          f"({km:.0f} km from the weather point)")

cols = ["site", "soil_lat", "soil_lon", "offset_km"] + sorted(allcols)
bykey = {n[0]: n for n in notes}
for r in rows:
    _, _, km, la, lo = bykey[r["site"]]
    r.update({"soil_lat": la, "soil_lon": lo,
              "offset_km": "" if km != km else round(km, 1)})
with OUT.open("w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
    w.writeheader(); w.writerows(rows)
print(f"\nwrote {OUT}")

good = [n for n in notes if n[1] > 0]
print(f"{len(good)} / {len(POINTS)} points resolved")
if good:
    offs = sorted(n[2] for n in good)
    print(f"offset from the weather point: median {offs[len(offs)//2]:.0f} km, "
          f"max {offs[-1]:.0f} km  <- report this in the methods section")

KEY = [c for c in cols if c.startswith(("phh2o_0_5", "phh2o_30_60", "clay_0_5",
                                        "sand_0_5", "soc_0_5"))]
if KEY and good:
    print(f"\n{'site':14s} {'km':>5s} " + " ".join(f"{c:>15s}" for c in KEY))
    for r in rows:
        km = r.get("offset_km")
        print(f"{r['site']:14s} {km if km != '' else '  -':>5} " +
              " ".join(f"{r.get(c, float('nan')):15.1f}" for c in KEY))
    print("""
pH first: Palasatien et al. 2008 found pH 5.0-6.0 the major determinant of
B. pseudomallei presence. A sharp Taiwan/West Africa difference here is a
concrete, physical limit on transferability that weather features cannot see -
exactly what expD and expG2 measured but could not name.
""")
