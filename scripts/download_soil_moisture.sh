#!/usr/bin/env bash
# ERA5-Land soil moisture at four depths, via the Open-Meteo archive API.
# No account, no API key, no registration. Free for non-commercial use.
#
# Four layers: 0-7cm, 7-28cm, 28-100cm, 100-255cm (m3/m3, volumetric).
# The deep layers are the point: Ribolzi 2022 found B. pseudomallei peaking at
# 170 cm, which our 150 mm surface bucket cannot represent at all.
#
# RUN THIS IN YOUR OWN TERMINAL, from the project folder:
#   bash scripts/download_soil_moisture.sh
#
# Resumable: already-downloaded files are skipped. Safe to re-run.

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/data/raw/soilmoisture"
mkdir -p "$OUT"

START=2003-01-01
END=2026-09-30
API="https://archive-api.open-meteo.com/v1/archive"

DAILY="soil_moisture_0_to_7cm_mean,soil_moisture_7_to_28cm_mean,soil_moisture_28_to_100cm_mean,soil_moisture_100_to_255cm_mean,et0_fao_evapotranspiration,precipitation_sum,temperature_2m_mean"

# name lat lon   -- identical points to the NASA POWER files already in the project
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
  f="$OUT/sm-$name.json"
  if [ -s "$f" ] && grep -q '"daily"' "$f" 2>/dev/null; then
    echo "skip   $name  (already have $(basename "$f"))"
    continue
  fi
  url="$API?latitude=$lat&longitude=$lon&start_date=$START&end_date=$END&daily=$DAILY&timezone=UTC"
  echo -n "get    $name ... "
  code=$(curl -sS -m 180 --retry 3 --retry-delay 5 -o "$f.tmp" -w "%{http_code}" "$url" 2>"$f.err")
  if [ "$code" != "200" ]; then
    echo "HTTP $code"
    echo "       --- response ---"; head -c 400 "$f.tmp" 2>/dev/null; echo
    echo "       --- curl error ---"; head -c 300 "$f.err" 2>/dev/null; echo
    rm -f "$f.tmp"; fail=$((fail+1)); continue
  fi
  if ! grep -q '"soil_moisture_0_to_7cm_mean"' "$f.tmp"; then
    echo "BAD RESPONSE - the variable names may have changed"
    echo "       --- first 500 chars, send this to Claude ---"
    head -c 500 "$f.tmp"; echo
    mv "$f.tmp" "$f.rejected"; fail=$((fail+1)); continue
  fi
  mv "$f.tmp" "$f"; rm -f "$f.err"
  n=$(grep -o '"time":\[' "$f" | wc -l | tr -d ' ')
  echo "ok  $(du -h "$f" | cut -f1)"
  sleep 2          # be polite to a free API
done

echo
echo "files in $OUT:"
ls -la "$OUT" 2>/dev/null | tail -n +2
if [ "$fail" -gt 0 ]; then
  echo
  echo "$fail point(s) failed. Send the error block above to Claude - do not"
  echo "edit the URL by guessing, the variable names are version-specific."
  exit 1
fi
echo
echo "Done. Now run:  python3 scripts/soil_moisture_to_csv.py"
