# How to download the new datasets

**Run everything in your own Terminal app, from the project folder.** Do not run
these through Claude — the Claude workspace proxy blocks all of these hosts, which
is also why none of these scripts has been tested end to end. They are written
defensively: every response is checked, and a failure prints the server's reply
instead of writing a corrupt file.

```bash
cd ~/Documents/Binus/"Semester 5"/"Computation Bio 1"
bash scripts/download_all.sh
```

That runs the three scriptable sources in priority order and converts each to CSV.
It writes a timestamped log to `outputs/`. **If anything fails, send me that log
rather than editing the URLs** — the variable names are version-specific and
guessing at them produces files that look fine and contain the wrong thing.

---

## What each one needs, and what it is for

| script | account needed | size | what it tests |
|---|---|---|---|
| `download_soil_moisture.sh` | **none** | ~40 MB | validates our bucket; adds deep layers to 255 cm |
| `download_soilgrids.sh` | **none** | <1 MB | explains the region-transfer gap |
| `download_groundwater.sh` | NASA Earthdata (free, 5 min) | ~10 MB | **the one that could change the result** |

Start with the first two. They need no setup and will run in a few minutes.

### Setting up NASA Earthdata (for the groundwater script)

1. Create an account: https://urs.earthdata.nasa.gov/users/new
2. **Authorise the GES DISC application** — this step is the one everybody skips
   and it causes almost every 401. Log in, go to
   https://urs.earthdata.nasa.gov/profile → Applications → Authorized Apps →
   Approve More Applications → find **NASA GESDISC DATA ARCHIVE** → approve.
3. Store the credentials:

```bash
echo "machine urs.earthdata.nasa.gov login YOUR_USERNAME password YOUR_PASSWORD" >> ~/.netrc
chmod 600 ~/.netrc
touch ~/.urs_cookies
```

`chmod 600` matters — curl refuses to use a `.netrc` that other users can read.

---

## What each converter prints, and why you should read it

### `soil_moisture_to_csv.py`
Correlates ERA5-Land's four soil layers against our 150 mm bucket, per region.

- High r with layer 1 or 2 → our bucket is a fair surface model, keep it, and now
  it has independent support
- Low r everywhere → ERA5-Land replaces the bucket
- Layers 3 and 4 behaving differently from 1 and 2 → the deep reservoir is a
  separate variable, which is the Ribolzi 2022 finding (maximum at 170 cm) and
  the reason this download is worth doing at all

### `groundwater_to_csv.py`
Asks the question that decides whether groundwater earns a place in the paper:
**is it recoverable from rainfall and temperature?** Our bucket's soil saturation
scored R² 0.875 on exactly this test.

- R² well below 0.875 → groundwater carries information no soil-moisture product
  and no bucket model can supply. This is the single result that could turn the
  core negative finding positive.
- R² near 0.875 → groundwater here is slow rainfall. Report it honestly; it still
  helps, because it closes the most obvious "but you didn't try X" objection.

### `soilgrids_to_csv.py`
Prints pH, clay, sand and organic carbon for all fourteen points side by side.
Palasatien et al. 2008 found pH 5.0–6.0 the major determinant of
*B. pseudomallei* presence. If Taiwan and West Africa differ sharply, that is a
concrete limit on transferability that weather features cannot see — which is
exactly what expD and expG2 measured but could not explain.

---

## The two I could not script

These are not APIs, so there is nothing to automate. Both need a human.

### Taiwan groundwater monitoring wells — highest value in the whole plan

The Pingtung Plain sits inside Kaoping, which holds **647 of our 925 cases**, and
Taiwan monitors groundwater there densely. GLDAS at 0.25° cannot resolve a plain;
actual well records can. With them, the hypothesis *"melioidosis timing tracks the
water table, not the rain"* becomes a direct test with 647 cases and 23 years —
the Darwin analysis, in a place with far more cases than Darwin.

I could not verify any endpoint because every outbound host is blocked from this
session, so these are leads, not links:

- **Water Resources Agency (經濟部水利署)** — hydrological yearbooks and the
  groundwater observation network
- **data.gov.tw** — search 地下水位 (groundwater level)
- **Central Geological Survey (中央地質調查所)** — Pingtung Plain and Choushui
  River alluvial fan groundwater reports. **Start here:** those reports name the
  specific well IDs, which is what you need before you can request anything.
- **Academic route** — published Pingtung Plain groundwater papers cite their data
  source, and authors often share on request. For a student project this is
  frequently faster than the official channel.

What to ask for: water-table depth, 2003–2026, any frequency down to monthly, for
wells in Pingtung/Kaohsiung (Kaoping), Yunlin/Changhua (Central), Tainan
(Southern). **Even one well per region is enough to run the test.** Do not wait
for a complete network.

### Thailand Report 506 — the power multiplier

77 provinces instead of our 6 regions. Every analysis in this project currently
rests on **three scorable regions**, and that is its biggest weakness.

- Bureau of Epidemiology, Ministry of Public Health: `doe.moph.go.th` /
  `boe.moph.go.th` — Report 506, melioidosis by province and month
- Backup: Wongbutdee 2024, *IJERPH* 21(5):614 describes 4,871 cases across 219
  subdistricts, 2013–2022. Emailing the authors for the aggregated monthly series
  is a legitimate and often successful route for a student project.
- You will also need provincial population denominators (Thai NESDC)

Why this one matters whichever way it goes: signal found in 77 provinces → you
have the positive paper. Null confirmed across 83 units in two countries → the
negative result becomes close to unarguable. **Both outcomes are publishable**,
which is the real answer to "what if the result isn't good enough".

---

## Likely failure points, so you recognise them

| symptom | cause | fix |
|---|---|---|
| `HTTP 401` on groundwater | GES DISC app not authorised | setup step 2 above |
| `HTTP 400` + "cannot parse" on soil moisture | Open-Meteo renamed a daily variable | send me the response; do not guess |
| groundwater file < 100 lines | the point landed on a water/ocean cell | nudge that coordinate 0.25° inland |
| `HTTP 429` on SoilGrids | rate limit | the script sleeps 4 s; re-run, it resumes |
| everything fails with 403 | you are running inside the Claude workspace | use your own Terminal |

Re-running any script is safe. Completed files are skipped, so a failed run picks
up where it stopped.
