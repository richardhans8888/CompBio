#!/usr/bin/env bash
# Everything available through NASA Hydrology Data Rods, in one pass.
#
# WHY THESE VARIABLES. Today's ERA5-Land result was that soil water at
# 28-100 cm locates the melioidosis season (3.08 weeks error) while surface
# soil water barely beats rainfall (5.58 vs 6.04). That is a single reanalysis.
# GLDAS-NOAH is a completely independent land-surface model with its own four
# soil layers, so it can REPLICATE or REFUTE that depth pattern - which is worth
# far more than one model's answer. And GLDAS-CLSM carries groundwater storage,
# which is the one variable that is not a function of local rainfall.
#
# Runs Taiwan first, so if it stops partway you still have the regions where
# the cases are.
#
# SETUP:  bash scripts/setup_earthdata.sh     (do this first, it tests the login)
# RUN IN YOUR OWN TERMINAL:  bash scripts/download_earthdata.sh

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/data/raw/earthdata"
mkdir -p "$OUT"
BASE="https://hydro1.gesdisc.eosdis.nasa.gov/daac-bin/access/timeseries.cgi"

if [ ! -f "$HOME/.netrc" ] || ! grep -q "urs.earthdata.nasa.gov" "$HOME/.netrc" 2>/dev/null; then
  echo "No Earthdata credentials. Run first:  bash scripts/setup_earthdata.sh"
  exit 1
fi

# label | variable id | start | end | chunked?
#   monthly NOAH soil layers - small, fast, and the independent depth replication
#   daily CLSM - groundwater and root zone, the main prize, chunked
SERIES=(
  "noah_sm_000_010|GLDAS2:GLDAS_NOAH025_M_v2.1:SoilMoi0_10cm_inst|2003-01-01T00|2026-09-30T00|0"
  "noah_sm_010_040|GLDAS2:GLDAS_NOAH025_M_v2.1:SoilMoi10_40cm_inst|2003-01-01T00|2026-09-30T00|0"
  "noah_sm_040_100|GLDAS2:GLDAS_NOAH025_M_v2.1:SoilMoi40_100cm_inst|2003-01-01T00|2026-09-30T00|0"
  "noah_sm_100_200|GLDAS2:GLDAS_NOAH025_M_v2.1:SoilMoi100_200cm_inst|2003-01-01T00|2026-09-30T00|0"
  "clsm_groundwater|GLDAS2:GLDAS_CLSM025_DA1_D_v2.2:GWS_tavg|2003-01-01T00|2026-09-30T00|1"
  "clsm_rootzone|GLDAS2:GLDAS_CLSM025_DA1_D_v2.2:SoilMoist_RZ_tavg|2003-01-01T00|2026-09-30T00|1"
  "clsm_totalwater|GLDAS2:GLDAS_CLSM025_DA1_D_v2.2:TWS_tavg|2003-01-01T00|2026-09-30T00|1"
)
CHUNKS=("2003-01-01T00 2010-12-31T00" "2011-01-01T00 2018-12-31T00" "2019-01-01T00 2026-09-30T00")

# Taiwan first - that is where the 925 cases are
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

fetch_one () {   # varid lat lon start end outfile
  local varid="$1" lat="$2" lon="$3" s="$4" e="$5" f="$6"
  local url="$BASE?variable=$varid&location=GEOM:POINT($lon,%20$lat)&startDate=$s&endDate=$e&type=asc2"
  local code
  code=$(curl -sS -m 300 --retry 2 --retry-delay 15 \
    -b "$HOME/.urs_cookies" -c "$HOME/.urs_cookies" -L -n \
    -o "$f.tmp" -w "%{http_code}" "$url" 2>"$f.err")
  local n; n=$(grep -cE '^[0-9]{4}-[0-9]{2}' "$f.tmp" 2>/dev/null || echo 0)
  if [ "$code" = "200" ] && [ "${n:-0}" -ge 10 ]; then
    mv "$f.tmp" "$f"; rm -f "$f.err"; echo "$n"; return 0
  fi
  echo "HTTP=$code rows=$n" > "$f.fail"
  head -c 400 "$f.tmp" >> "$f.fail" 2>/dev/null
  head -c 200 "$f.err" >> "$f.fail" 2>/dev/null
  rm -f "$f.tmp"; return 1
}

declare -a BADVARS=()
total_ok=0; total_fail=0
for sp in "${SERIES[@]}"; do
  IFS='|' read -r label varid s0 e0 chunked <<< "$sp"
  echo ""; echo "=============== $label"
  varfail=0
  for p in "${POINTS[@]}"; do
    read -r name lat lon <<< "$p"
    f="$OUT/$label-$name.txt"
    if [ -s "$f" ]; then echo "  skip $name"; continue; fi
    if [ "$chunked" = "0" ]; then
      echo -n "  $name ... "
      if n=$(fetch_one "$varid" "$lat" "$lon" "$s0" "$e0" "$f"); then
        echo "ok $n rows"; total_ok=$((total_ok+1))
      else
        echo "FAILED  ($(head -1 "$f.fail"))"; total_fail=$((total_fail+1)); varfail=$((varfail+1))
      fi
      sleep 3
    else
      echo "  $name"
      allok=1; parts=()
      for i in "${!CHUNKS[@]}"; do
        read -r cs ce <<< "${CHUNKS[$i]}"
        cf="$OUT/.$label-$name.$i"
        if [ -s "$cf" ]; then echo "      chunk $i cached"; parts+=("$cf"); continue; fi
        echo -n "      chunk $i ${cs%T*} .. ${ce%T*} ... "
        if n=$(fetch_one "$varid" "$lat" "$lon" "$cs" "$ce" "$cf"); then
          echo "ok $n rows"; parts+=("$cf")
        else
          echo "FAILED  ($(head -1 "$cf.fail"))"; allok=0
        fi
        sleep 4
      done
      if [ "$allok" = "1" ] && [ "${#parts[@]}" -gt 0 ]; then
        { grep -hE '^[0-9]{4}-[0-9]{2}' "${parts[@]}" | sort -u; } > "$f"
        echo "      merged -> $(wc -l < "$f" | tr -d ' ') rows"
        total_ok=$((total_ok+1))
      else
        total_fail=$((total_fail+1)); varfail=$((varfail+1))
      fi
    fi
  done
  # if a variable failed at EVERY point, the variable id is wrong, not the data
  if [ "$varfail" -ge "${#POINTS[@]}" ]; then
    BADVARS+=("$label ($varid)")
  fi
done

echo ""; echo "=============================================="
echo "series downloaded: $total_ok   failed: $total_fail"
ls "$OUT" 2>/dev/null | grep -v '^\.' | head -40

if [ "${#BADVARS[@]}" -gt 0 ]; then
  echo ""
  echo "These variables failed at EVERY point, which means the variable ID is"
  echo "wrong rather than the location being unmapped:"
  for v in "${BADVARS[@]}"; do echo "  - $v"; done
  echo ""
  echo "Current product list:"
  echo "  https://disc.gsfc.nasa.gov/information/tools?title=Hydrology%20Data%20Rods"
  echo "Send this output to Claude. Do not guess at variable names - a wrong one"
  echo "can return a valid-looking file holding the wrong quantity."
fi

if [ "$total_fail" -gt 0 ]; then
  echo ""; echo "Failure details are in $OUT/*.fail"
  echo "A single point failing usually means it fell on a water/ocean cell;"
  echo "nudge that coordinate 0.25 degrees inland and re-run."
fi
echo ""
echo "Next:  python3 scripts/earthdata_to_csv.py"
