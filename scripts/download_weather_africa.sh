#!/usr/bin/env bash
# West African weather points, for the transfer test.
#
# SAME SOURCE AND SAME VARIABLES as the Taiwan download, deliberately. If Taiwan
# used NASA POWER and West Africa used something else, a drop in performance
# after transfer could not be separated from a difference in measurement.
#
# Points span the Sahel rainfall gradient, wet south to dry north, mirroring the
# north-south gradient that carries the signal in Taiwan. Koutiala is the site of
# the 2025 Lancet Global Health study that estimated ~3,178 annual cases in Mali
# against the ~580 predicted by the 2016 global model.
#
# Wind direction is excluded: NASA POWER's WD10M is corrupt from 2012-12-31 in
# this record (see scripts/build_dataset.py).
#
# Run:  bash scripts/download_weather_africa.sh

set -u
OUT="$(cd "$(dirname "$0")/.." && pwd)/data/raw/weather_africa"
mkdir -p "$OUT"

START=20030101
END=20261003
PARAMS="PRECTOTCORR,T2M,T2M_MAX,T2M_MIN,RH2M,WS10M,WS10M_MAX"

POINTS="
Koutiala 12.39 -5.46 Mali-study-site
Sikasso 11.32 -5.67 Mali-wet-south
Bamako 12.65 -8.00 Mali-capital
Segou 13.43 -6.26 Mali-central
Mopti 14.49 -4.20 Mali-dry-Sahel
Bobo 11.18 -4.30 BurkinaFaso-south
Ouagadougou 12.37 -1.52 BurkinaFaso-central
Korhogo 9.46 -5.63 CoteDIvoire-north
"

echo "$POINTS" | while read -r site lat lon note; do
  [ -z "${site:-}" ] && continue
  f="$OUT/weather-$(echo "$site" | tr '[:upper:]' '[:lower:]').csv"
  if [ -s "$f" ]; then echo "skip   $site"; continue; fi
  url="https://power.larc.nasa.gov/api/temporal/daily/point?parameters=$PARAMS&community=AG"
  url="$url&longitude=$lon&latitude=$lat&start=$START&end=$END&format=CSV"
  printf "fetch  %-14s %7s,%7s  %-22s ... " "$site" "$lat" "$lon" "$note"
  code=$(curl -sS --max-time 180 -o "$f" -w "%{http_code}" "$url" || echo 000)
  size=$( [ -f "$f" ] && wc -c < "$f" || echo 0 )
  if [ "$code" = "200" ] && [ "$size" -gt 5000 ]; then echo "ok (${size}b)"
  else echo "FAILED (http $code)"; rm -f "$f"; fi
done
echo
echo "files:"
ls -1sh "$OUT" 2>/dev/null
