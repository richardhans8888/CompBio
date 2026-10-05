#!/usr/bin/env bash
# GLDAS groundwater storage + deep soil moisture, via NASA Hydrology Data Rods.
#
# THIS IS THE IMPORTANT ONE. Groundwater storage has months-to-years memory and
# responds to regional recharge and pumping, so unlike every soil-moisture
# product it is NOT a function of local rainfall. Our own test showed the
# bucket's features are 88-99% recoverable from rain and temperature; groundwater
# is the variable that escapes that. Kaestli/Currie found measured groundwater
# significant for melioidosis in Darwin (J Infect 2016); Hempenstall named its
# absence as Townsville's primary limitation (Environ Health Prev Med 2023).
#
# GLDAS-2.2 CLSM assimilates GRACE satellite gravity, so GWS_tavg is a real
# groundwater estimate, daily, 0.25 degrees, 2003-present.
#
# ---------------------------------------------------------------------------
# ONE-TIME SETUP (about 5 minutes, free)
#
# 1. Create a NASA Earthdata account:
#      https://urs.earthdata.nasa.gov/users/new
#
# 2. Authorise the GES DISC application. Log in, then visit:
#      https://urs.earthdata.nasa.gov/profile
#    -> Applications -> Authorized Apps -> Approve More Applications
#    -> find "NASA GESDISC DATA ARCHIVE" and approve it.
#    (Skipping this step is the most common cause of a 401.)
#
# 3. Store your credentials. Run these three lines, replacing USER and PASS:
#      echo "machine urs.earthdata.nasa.gov login USER password PASS" >> ~/.netrc
#      chmod 600 ~/.netrc
#      touch ~/.urs_cookies
#
# RUN THIS IN YOUR OWN TERMINAL, from the project folder:
#   bash scripts/download_groundwater.sh
# ---------------------------------------------------------------------------

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/data/raw/groundwater"
mkdir -p "$OUT"

START=2003-01-01T00
END=2026-09-30T00
BASE="https://hydro1.gesdisc.eosdis.nasa.gov/daac-bin/access/timeseries.cgi"

if [ ! -f "$HOME/.netrc" ] || ! grep -q "urs.earthdata.nasa.gov" "$HOME/.netrc" 2>/dev/null; then
  echo "ERROR: no Earthdata credentials found in ~/.netrc"
  echo "Follow the ONE-TIME SETUP block at the top of this script first."
  exit 1
fi

# variable  label
# GLDAS-2.2 CLSM is the GRACE-assimilating product - GWS_tavg is groundwater storage
VARS=(
  "GLDAS2:GLDAS_CLSM025_DA1_D_v2.2:GWS_tavg            gws"
  "GLDAS2:GLDAS_CLSM025_DA1_D_v2.2:SoilMoist_RZ_tavg   rootzone"
  "GLDAS2:GLDAS_CLSM025_DA1_D_v2.2:TWS_tavg            tws"
)

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

fail=0; ok=0
for v in "${VARS[@]}"; do
  read -r varid label <<< "$v"
  for p in "${POINTS[@]}"; do
    read -r name lat lon <<< "$p"
    f="$OUT/$label-$name.txt"
    if [ -s "$f" ] && [ "$(wc -l < "$f")" -gt 100 ]; then
      echo "skip   $label/$name"
      continue
    fi
    url="$BASE?variable=$varid&location=GEOM:POINT($lon,%20$lat)&startDate=$START&endDate=$END&type=asc2"
    echo -n "get    $label/$name ... "
    code=$(curl -sS -m 300 --retry 2 --retry-delay 10 \
      -b "$HOME/.urs_cookies" -c "$HOME/.urs_cookies" -L -n \
      -o "$f.tmp" -w "%{http_code}" "$url" 2>"$f.err")
    lines=$(wc -l < "$f.tmp" 2>/dev/null | tr -d ' ')
    if [ "$code" != "200" ] || [ "${lines:-0}" -lt 100 ]; then
      echo "HTTP $code, $lines lines"
      echo "       --- response head ---"; head -c 400 "$f.tmp" 2>/dev/null; echo
      echo "       --- curl error ---";    head -c 300 "$f.err" 2>/dev/null; echo
      rm -f "$f.tmp"; fail=$((fail+1)); continue
    fi
    mv "$f.tmp" "$f"; rm -f "$f.err"
    echo "ok  $lines lines"
    ok=$((ok+1))
    sleep 3
  done
done

echo
echo "downloaded $ok series, $fail failed"
ls -la "$OUT" 2>/dev/null | tail -n +2
if [ "$fail" -gt 0 ]; then
  cat <<'MSG'

Common causes, in order of likelihood:
  401 / "Unauthorized"  -> GES DISC app not authorised in your Earthdata profile
                           (step 2 of the setup block). This is almost always it.
  404 / empty           -> the product or variable ID has changed. Check the
                           current list at:
                           https://disc.gsfc.nasa.gov/information/tools?title=Hydrology%20Data%20Rods
  short file            -> the point fell on a GLDAS water/ocean cell. Nudge the
                           coordinate 0.25 degrees inland and retry that point.
Send the error block to Claude rather than guessing at the variable name.
MSG
  exit 1
fi
echo
echo "Done. Now run:  python3 scripts/groundwater_to_csv.py"
