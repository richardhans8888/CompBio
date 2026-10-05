"""
Find out why 10 of 14 SoilGrids files produced NaN. The downloads succeeded -
all 14 files are ~6.1 KB - so this is a parsing problem on my side, not yours.

Run:  python3 scripts/diagnose_soilgrids.py
and send me the output.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "raw" / "soilgrids"

WORKED = ["eastern", "koutiala", "northern", "southern"]
FAILED = ["kaoping", "central", "taipei", "bamako"]

def describe(name):
    p = SRC / f"soil-{name}.json"
    if not p.exists():
        print(f"  {name}: FILE MISSING"); return
    d = json.loads(p.read_text())
    print(f"\n--- {name}  ({p.stat().st_size} bytes)")
    print(f"    top-level keys: {list(d)}")
    props = d.get("properties", {})
    print(f"    properties keys: {list(props)}")
    layers = props.get("layers", [])
    print(f"    number of layers: {len(layers)}")
    if not layers:
        # the whole response, if it is small enough to be an error payload
        print("    NO LAYERS. Full response:")
        print("    " + json.dumps(d)[:900])
        return
    L = layers[0]
    print(f"    layer[0] keys: {list(L)}")
    print(f"    layer[0] name: {L.get('name')}")
    print(f"    layer[0] unit_measure: {L.get('unit_measure')}")
    deps = L.get("depths", [])
    print(f"    layer[0] depths: {len(deps)}")
    if deps:
        print(f"    depth[0] raw: {json.dumps(deps[0])}")
    # count how many (property, depth) cells actually carry a number
    total = filled = 0
    for lay in layers:
        for dep in lay.get("depths", []):
            total += 1
            v = dep.get("values", {}).get("mean")
            if v is not None:
                filled += 1
    print(f"    cells with a numeric mean: {filled} / {total}")

print("=" * 70)
print("FILES THAT PARSED CORRECTLY")
print("=" * 70)
for n in WORKED:
    describe(n)

print()
print("=" * 70)
print("FILES THAT CAME OUT AS NaN")
print("=" * 70)
for n in FAILED:
    describe(n)

print()
print("=" * 70)
print("Send everything above to Claude.")
print("=" * 70)
