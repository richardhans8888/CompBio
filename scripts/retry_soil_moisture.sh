#!/usr/bin/env bash
# Retry ONLY the soil-moisture points that failed, in 6-year chunks.
#
# Why the first attempt failed:
#   "Unexpected error while streaming data: timeoutReached"  -> Open-Meteo gave up
#       building a 23-year, 7-variable response in one request. Not a variable-name
#       problem; my original script's error message was wrong about that.
#   "Hourly API request limit exceeded"  -> each 23-year request is billed as many
#       calls, so twelve of them exhausted the free hourly allowance.
#
# Both are fixed by asking for 6 years at a time and pausing between requests.
# The chunks are merged back into the same single-file format the converter
# already expects, so nothing downstream changes.
#
# RUN IN YOUR OWN TERMINAL:  bash scripts/retry_soil_moisture.sh

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/data/raw/soilmoisture"
TMP="$OUT/.chunks"
mkdir -p "$TMP"
API="https://archive-api.open-meteo.com/v1/archive"
DAILY="soil_moisture_0_to_7cm_mean,soil_moisture_7_to_28cm_mean,soil_moisture_28_to_100cm_mean,soil_moisture_100_to_255cm_mean,et0_fao_evapotranspiration,precipitation_sum,temperature_2m_mean"

ALL=(
  "kaoping      22.63  120.30"
  "southern     23.10  120.25"
  "central      24.15  120.68"
  "northern     24.90  121.10"
  "taipei       25.03  121.57"
  "eastern      23.40  121.40"
  "koutiala     12.39   -5.46"
  "sikasso      11.32   -5.67"
  "bamako       12.65   -8.00"
  "segou        13.43   -6.26"
  "mopti        14.49   -4.20"
  "bobo         11.18   -4.30"
  "ouagadougou  12.37   -1.52"
  "korhogo       9.46   -5.63"
)
CHUNKS=("2003-01-01 2008-12-31" "2009-01-01 2014-12-31" \
        "2015-01-01 2020-12-31" "2021-01-01 2026-09-30")

# clear the misleading leftovers from the failed run
rm -f "$OUT"/*.rejected "$OUT"/*.err "$OUT"/*.tmp

todo=()
for p in "${ALL[@]}"; do
  read -r name _ _ <<< "$p"
  if [ -s "$OUT/sm-$name.json" ] && grep -q '"soil_moisture_0_to_7cm_mean"' "$OUT/sm-$name.json" 2>/dev/null; then
    echo "have   $name"
  else
    todo+=("$p")
  fi
done

if [ "${#todo[@]}" -eq 0 ]; then
  echo; echo "All 14 points already present. Nothing to do."
  exit 0
fi
echo; echo "need to fetch: ${#todo[@]} point(s)"; echo

fail=0
for p in "${todo[@]}"; do
  read -r name lat lon <<< "$p"
  echo "=== $name"
  okall=1
  for i in "${!CHUNKS[@]}"; do
    read -r s e <<< "${CHUNKS[$i]}"
    cf="$TMP/$name.$i.json"
    if [ -s "$cf" ] && grep -q '"soil_moisture_0_to_7cm_mean"' "$cf" 2>/dev/null; then
      echo "    have chunk $i  ($s)"; continue
    fi
    echo -n "    chunk $i  $s .. $e  "
    for attempt in 1 2 3 4 5; do
      code=$(curl -sS -m 150 -o "$cf.tmp" -w "%{http_code}" \
        "$API?latitude=$lat&longitude=$lon&start_date=$s&end_date=$e&daily=$DAILY&timezone=UTC" 2>/dev/null)
      if [ "$code" = "200" ] && grep -q '"soil_moisture_0_to_7cm_mean"' "$cf.tmp"; then
        mv "$cf.tmp" "$cf"; echo "ok"; break
      fi
      body=$(head -c 160 "$cf.tmp" 2>/dev/null)
      if echo "$body" | grep -qi "limit exceeded"; then
        echo ""
        echo "    HOURLY LIMIT REACHED. Progress is saved - just run this script"
        echo "    again in about an hour and it will resume from here."
        rm -f "$cf.tmp"; exit 2
      fi
      if [ "$attempt" -eq 5 ]; then
        echo "FAILED after 5 tries (HTTP $code): $body"
        rm -f "$cf.tmp"; okall=0; fail=$((fail+1))
      else
        echo -n "retry($code) "; sleep $((attempt * 15))
      fi
    done
    sleep 12      # keep well under the free-tier rate
  done
  [ "$okall" -eq 1 ] && echo "    all chunks present for $name"
done

echo; echo "merging chunks ..."
python3 - "$OUT" "$TMP" <<'PYEOF'
import json, sys, glob, os, re
out_dir, tmp_dir = sys.argv[1], sys.argv[2]
names = sorted({re.match(r"(.+)\.\d+\.json$", os.path.basename(p)).group(1)
                for p in glob.glob(os.path.join(tmp_dir, "*.json"))})
for name in names:
    parts = sorted(glob.glob(os.path.join(tmp_dir, f"{name}.*.json")),
                   key=lambda p: int(re.match(r".+\.(\d+)\.json$", p).group(1)))
    merged, keys = None, None
    for p in parts:
        d = json.load(open(p))
        if "daily" not in d:
            print(f"  !! {os.path.basename(p)} has no daily block, skipped"); continue
        if merged is None:
            merged = d; keys = list(d["daily"].keys()); continue
        for k in keys:
            merged["daily"][k].extend(d["daily"][k])
    if merged is None:
        print(f"  !! {name}: no usable chunks"); continue
    # drop any duplicate days at chunk boundaries, keeping order
    t = merged["daily"]["time"]
    seen, keep = set(), []
    for i, ts in enumerate(t):
        if ts not in seen:
            seen.add(ts); keep.append(i)
    for k in keys:
        merged["daily"][k] = [merged["daily"][k][i] for i in keep]
    dest = os.path.join(out_dir, f"sm-{name}.json")
    json.dump(merged, open(dest, "w"))
    print(f"  wrote {os.path.basename(dest)}  {len(keep)} days "
          f"({t[0][:10]} to {t[-1][:10]})")
PYEOF

echo
n=$(ls "$OUT"/sm-*.json 2>/dev/null | wc -l | tr -d ' ')
echo "soil-moisture points now present: $n / 14"
[ "$fail" -gt 0 ] && { echo "$fail chunk(s) failed - send the output to Claude."; exit 1; }
echo "Done. Now run:  python3 scripts/soil_moisture_to_csv.py"
