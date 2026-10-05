#!/usr/bin/env bash
# SoilGrids 2.0 soil properties at each study point. Free, no account, no key.
#
# These are STATIC properties, so they cannot predict timing - but expD and expG2
# showed the region-transfer penalty is region-specific and invisible to weather
# features. Soil type is the leading candidate for what those features are
# missing. Palasatien et al. 2008 found pH 5.0-6.0 the major determinant of
# B. pseudomallei presence, so phh2o is the first variable to look at.
#
# RUN THIS IN YOUR OWN TERMINAL:  bash scripts/download_soilgrids.sh

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/data/raw/soilgrids"
mkdir -p "$OUT"
API="https://rest.isric.org/soilgrids/v2.0/properties/query"

PROPS="property=phh2o&property=clay&property=sand&property=silt&property=soc&property=bdod&property=cec&property=nitrogen"
DEPTHS="depth=0-5cm&depth=5-15cm&depth=15-30cm&depth=30-60cm&depth=60-100cm&depth=100-200cm"

POINTS=(
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

fail=0
for p in "${POINTS[@]}"; do
  read -r name lat lon <<< "$p"
  f="$OUT/soil-$name.json"
  if [ -s "$f" ] && grep -q '"layers"' "$f" 2>/dev/null; then
    echo "skip   $name"; continue
  fi
  echo -n "get    $name ... "
  code=$(curl -sS -m 120 --retry 3 --retry-delay 8 \
    -o "$f.tmp" -w "%{http_code}" \
    "$API?lon=$lon&lat=$lat&$PROPS&$DEPTHS&value=mean" 2>"$f.err")
  if [ "$code" != "200" ] || ! grep -q '"layers"' "$f.tmp"; then
    echo "HTTP $code"
    head -c 350 "$f.tmp" 2>/dev/null; echo
    head -c 200 "$f.err" 2>/dev/null; echo
    rm -f "$f.tmp"; fail=$((fail+1)); continue
  fi
  mv "$f.tmp" "$f"; rm -f "$f.err"
  echo "ok"
  sleep 4      # SoilGrids rate-limits fairly aggressively
done

echo; ls -la "$OUT" | tail -n +2
[ "$fail" -gt 0 ] && { echo; echo "$fail failed - send the error output to Claude."; exit 1; }
echo; echo "Done. Now run:  python3 scripts/soilgrids_to_csv.py"
