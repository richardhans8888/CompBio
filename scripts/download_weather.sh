#!/usr/bin/env bash
# Download daily weather for one representative point per Taiwan NIDSS region.
#
# Source: NASA POWER daily point API (free, no key, global coverage 1981-present).
# A GLOBAL source is used on purpose: the same variable definitions must apply
# in Taiwan and in West Africa, otherwise a performance drop after transfer
# cannot be separated from a difference in how the data was measured.
#
# NASA POWER is served on a ~0.5 degree grid, so these centroids need only be
# roughly right - sub-degree precision would make no difference to the result.
#
# Run:  bash scripts/download_weather.sh

set -u
OUT="$(cd "$(dirname "$0")/.." && pwd)/data/raw/weather"
mkdir -p "$OUT"

START=20030101
END=20261003

# rainfall, mean/max/min temperature, humidity, wind speed, wind gust, wind direction
PARAMS="PRECTOTCORR,T2M,T2M_MAX,T2M_MIN,RH2M,WS10M,WS10M_MAX,WD10M"

# region        lat      lon      anchor city
POINTS="
Kaoping        22.63    120.30   Kaohsiung
Southern       23.10    120.25   Tainan-Chiayi
Central        24.15    120.68   Taichung
Northern       24.90    121.10   Taoyuan-Hsinchu
Taipei         25.03    121.57   Taipei
Eastern        23.40    121.40   Hualien-Taitung
"

echo "$POINTS" | while read -r region lat lon anchor; do
  [ -z "${region:-}" ] && continue
  f="$OUT/weather-$(echo "$region" | tr '[:upper:]' '[:lower:]').csv"
  if [ -s "$f" ]; then
    echo "skip   $region (already have $(basename "$f"))"
    continue
  fi
  url="https://power.larc.nasa.gov/api/temporal/daily/point"
  url="$url?parameters=$PARAMS&community=AG"
  url="$url&longitude=$lon&latitude=$lat&start=$START&end=$END&format=CSV"
  printf "fetch  %-10s %s,%s (%s) ... " "$region" "$lat" "$lon" "$anchor"
  code=$(curl -sS --max-time 180 -o "$f" -w "%{http_code}" "$url" || echo 000)
  size=$( [ -f "$f" ] && wc -c < "$f" || echo 0 )
  if [ "$code" = "200" ] && [ "$size" -gt 5000 ]; then
    echo "ok (${size} bytes)"
  else
    echo "FAILED (http $code, ${size} bytes)"
    rm -f "$f"
  fi
done

echo
echo "files in data/raw/weather:"
ls -1sh "$OUT" 2>/dev/null || echo "  (none)"
