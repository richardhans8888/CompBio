#!/usr/bin/env bash
# Set up NASA Earthdata credentials and TEST them before you waste time downloading.
#
# RUN IN YOUR OWN TERMINAL:  bash scripts/setup_earthdata.sh

set -uo pipefail

cat <<'INTRO'
---------------------------------------------------------------------------
NASA Earthdata setup

Before running this, you need two things done in a browser:

  1. An account:  https://urs.earthdata.nasa.gov/users/new

  2. The GES DISC application AUTHORISED. This is the step almost everyone
     skips, and it causes nearly every 401 error you will find online.
       - log in
       - go to https://urs.earthdata.nasa.gov/profile
       - Applications -> Authorized Apps -> Approve More Applications
       - find "NASA GESDISC DATA ARCHIVE" and approve it

Done both? Then enter your credentials below. They go into ~/.netrc with
permissions 600, which is the standard place curl looks for them.
---------------------------------------------------------------------------
INTRO

read -r -p "Earthdata username: " EDUSER
read -r -s -p "Earthdata password: " EDPASS; echo
if [ -z "$EDUSER" ] || [ -z "$EDPASS" ]; then
  echo "Both fields are required. Nothing written."; exit 1
fi

NETRC="$HOME/.netrc"
if [ -f "$NETRC" ] && grep -q "urs.earthdata.nasa.gov" "$NETRC"; then
  cp "$NETRC" "$NETRC.backup.$(date +%s)"
  echo "existing entry found - backed up, replacing it"
  grep -v "urs.earthdata.nasa.gov" "$NETRC" > "$NETRC.new" || true
  mv "$NETRC.new" "$NETRC"
fi
printf 'machine urs.earthdata.nasa.gov login %s password %s\n' "$EDUSER" "$EDPASS" >> "$NETRC"
chmod 600 "$NETRC"
touch "$HOME/.urs_cookies"
echo "wrote credentials to $NETRC (permissions 600)"

echo
echo "testing with one real request (Kaoping, 3 days of GLDAS groundwater) ..."
URL="https://hydro1.gesdisc.eosdis.nasa.gov/daac-bin/access/timeseries.cgi?variable=GLDAS2:GLDAS_CLSM025_DA1_D_v2.2:GWS_tavg&location=GEOM:POINT(120.30,%2022.63)&startDate=2020-01-01T00&endDate=2020-01-03T00&type=asc2"
code=$(curl -sS -m 90 -b "$HOME/.urs_cookies" -c "$HOME/.urs_cookies" -L -n \
  -o /tmp/ed_test.txt -w "%{http_code}" "$URL" 2>/tmp/ed_test.err)
lines=$(wc -l < /tmp/ed_test.txt 2>/dev/null | tr -d ' ')

echo "HTTP $code, $lines lines returned"
echo "--- response ---"
head -12 /tmp/ed_test.txt 2>/dev/null
echo "----------------"

if [ "$code" = "200" ] && [ "${lines:-0}" -ge 3 ]; then
  echo
  echo "WORKING. Next:  bash scripts/download_earthdata.sh"
  exit 0
fi

echo
case "$code" in
  401|403) cat <<'MSG'
AUTHENTICATION FAILED.

Most likely the GES DISC application is not authorised on your profile
(step 2 above). Check https://urs.earthdata.nasa.gov/profile -> Applications
-> Authorized Apps, and confirm "NASA GESDISC DATA ARCHIVE" is listed.

Second most likely: a typo in the password. Re-run this script.
MSG
  ;;
  404) echo "The product ID may have changed. Current list:"
       echo "  https://disc.gsfc.nasa.gov/information/tools?title=Hydrology%20Data%20Rods"
       echo "Send this output to Claude rather than guessing at variable names." ;;
  *)   echo "Unexpected result. curl said:"; head -c 400 /tmp/ed_test.err 2>/dev/null
       echo; echo "Send this output to Claude." ;;
esac
exit 1
