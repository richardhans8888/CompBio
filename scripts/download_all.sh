#!/usr/bin/env bash
# Runs every scriptable download in priority order, then the converters.
# Each step is independent - if one fails the rest still run.
#
# RUN IN YOUR OWN TERMINAL from the project folder:  bash scripts/download_all.sh

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
log="$ROOT/outputs/download_log_$(date +%Y%m%d_%H%M).txt"
mkdir -p "$ROOT/outputs"

run () {
  echo ""; echo "=============================================================="
  echo ">>> $1"; echo "=============================================================="
  bash "$2"; echo "    exit=$?"
}

{
  echo "download run started $(date)"
  run "ERA5-Land soil moisture, 4 depths (no account needed)" scripts/download_soil_moisture.sh
  run "SoilGrids soil properties (no account needed)"         scripts/download_soilgrids.sh
  run "GLDAS groundwater (needs Earthdata login - see script header)" scripts/download_groundwater.sh

  echo ""; echo ">>> converting to CSV"
  for s in soil_moisture_to_csv soilgrids_to_csv groundwater_to_csv; do
    echo "--- $s"; python3 "scripts/$s.py"; echo "    exit=$?"
  done
  echo ""; echo "finished $(date)"
} 2>&1 | tee "$log"

echo ""
echo "full log saved to: $log"
echo "If anything failed, send that log to Claude."
