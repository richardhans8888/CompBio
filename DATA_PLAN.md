# Data acquisition plan, ranked by information content

Every candidate dataset is ranked by one question: **does it carry information that
is not already in the rainfall and temperature we have?** That matters more than
how modern or how high-resolution it is.

## The test that produced this ranking

Out-of-sample R2 for reconstructing each of our mechanistic features from 26
rainfall and temperature lags alone (extra trees, train < 2018, test >= 2018):

| our feature | R2 from rain + temperature only |
|---|---|
| water balance (rain - PET) | **0.995** |
| antecedent precipitation index | **0.976** |
| saturation excess / standing water | **0.980** |
| soil saturation | **0.875** |
| saturated days per week | 0.701 |

**Interpretation.** Our soil model is 70-99.5% a rearrangement of rainfall and
temperature. This is why 141 mechanistic features added nothing to the Taiwan
model (expE: 0.823 -> 0.826): they were not new information, they were the same
information in better coordinates. Better coordinates help *interpretation* and
*timing* (the 6.0 -> 2.3 week improvement is real) but cannot create year-to-year
predictive signal that was never in the weather.

This immediately splits the candidate datasets.

---

## TIER 1 — genuinely new information. Could change the core result.

### 1.1 Taiwan groundwater monitoring wells  ← HIGHEST PRIORITY

**Why it is different.** Aquifer storage has months-to-years memory, responds to
regional recharge and to pumping, and is **not** recoverable from local rainfall.
It is the only variable on the list that is independent of what we already have.

**Why Taiwan specifically.** The Pingtung Plain sits inside the Kaoping region,
which holds **647 of our 925 cases (70%)**. Taiwan operates a dense groundwater
observation network there and in the Choushui River alluvial fan (Central region).
So the one place in the world with a long open weekly melioidosis series also has
dense groundwater monitoring over the same period.

**The hypothesis this tests.** *Does melioidosis timing track the water table
rather than the rain?* Supporting evidence already assembled:
- Kaestli/Currie, Darwin, 23-year series: measured groundwater level was a
  significant factor (*J Infect* 2016;72:687-697)
- Hempenstall, Townsville: absence of groundwater data named as the study's
  primary limitation (*Environ Health Prev Med* 2023;28:35)
- Ribolzi et al. 2022: concentration maximum at **170 cm**, 100% groundwater
  persistence below 110 cm (*Sci Rep* 12:8674)
- Chen et al. 2025: detection rises significantly at 30 cm and the surface after
  rain, falls after sunny spells (*PLoS Negl Trop Dis* 19:e0013640)
- This project: peak rainfall is 8-9 weeks before peak cases in Central and
  Southern Taiwan; a surface soil bucket closes most but not all of that gap

If groundwater beats both rainfall and our bucket, that is a first-of-its-kind
mechanistic result with a clear precedent and a clear mechanism — the strongest
available version of this paper.

**Where to look.** I could not verify any endpoint (all outbound hosts are blocked
from this session), so treat these as leads:
- Water Resources Agency, MOEA — hydrological yearbooks and groundwater
  observation network data
- Taiwan government open data portal (data.gov.tw) — search groundwater level /
  地下水位
- Central Geological Survey — Pingtung Plain and Choushui fan groundwater studies
  will name the specific well IDs to request
- Academic route: papers on Pingtung Plain groundwater will cite the data source
  and often the authors will share

**What to request:** daily or weekly water-table depth, 2003-2026, for wells in
Pingtung County and Kaohsiung (Kaoping), Yunlin/Changhua (Central), Tainan
(Southern). Even monthly is usable. Even one well per region is usable.

### 1.2 GRACE / GRACE-FO groundwater storage anomaly

Global, monthly, 2002-present, ~300 km. Coarse, but genuinely independent of local
weather and it covers West Africa too — which matters, because it is the only
Tier 1 variable obtainable for Mali.

- NASA GRACE Tellus, and GLDAS-2.2 (which assimilates GRACE) via NASA GES DISC
- Needs a free NASA Earthdata login
- Variable: groundwater storage anomaly; also terrestrial water storage anomaly

**Caveat to state in the paper:** at 300 km one pixel covers most of southern
Taiwan, so it cannot resolve between-region differences. Use it for *timing*, not
for spatial contrast.

### 1.3 Soil type and texture — explains the between-region gap

expD and expG2 showed the transfer penalty is region-specific and that weather
features cannot see it. Static soil properties are the obvious candidate for what
they are missing, and they are independent of weather by construction.

- SoilGrids 2.0, 250 m: clay, sand, silt, pH, organic carbon, bulk density,
  cation exchange capacity — soilgrids.org
- Harmonized World Soil Database v2 (FAO) — Acrisols were the favourable soil in
  the SE Asia MaxEnt study
- Palasatien et al. 2008 found pH 5.0-6.0 the major determinant and moisture >10%
  significant, so pH is the specific variable to get first

**The test:** does adding region-level soil properties recover the 0.069 AUC
transfer gap? If yes, that identifies what transfers and what does not — a
positive mechanistic answer to the paper's own question.

### 1.4 Land use, irrigation, and host risk — also weather-independent

- Rice paddy extent and irrigated area: ESA WorldCover, MODIS land cover
- Diabetes prevalence by region (the dominant host risk factor): Taiwan NHIRD
  published figures, or IHME GBD subnational
- Population density and rural fraction (denominators and exposure)

---

## TIER 2 — validates and deepens the mechanism. Will NOT fix the null.

### 2.1 ERA5-Land volumetric soil water, four layers

Still worth doing, for two specific jobs:

1. **Validate the bucket.** Correlate our saturation against layer 2 (7-28 cm) and
   layer 3 (28-100 cm). Agreement makes our one-parameter toy defensible to a
   reviewer; disagreement replaces it.
2. **Deep compartment.** Layers 3 and 4 reach 289 cm. Our bucket is a 150 mm
   surface abstraction with no deep compartment, yet Ribolzi found the reservoir
   maximum at 170 cm. Deep soil water is a genuinely different variable from
   surface saturation, and no melioidosis paper has used it.

- Copernicus Climate Data Store, free account + `cdsapi`:
  cds.climate.copernicus.eu
- Dataset: `reanalysis-era5-land`, hourly or daily aggregated
- Variables: `volumetric_soil_water_layer_1` .. `_4`, `skin_temperature`,
  `total_precipitation`, `potential_evaporation`, `runoff`
- Same 6 Taiwan and 8 West Africa points as the NASA POWER files, 2003-2026

**Expect no AUC improvement.** Say so in advance in the paper; it is a stronger
position than discovering it afterwards.

### 2.2 SMAP L4 root-zone soil moisture

2015-present, 9 km, assimilates satellite observations into a land model. Higher
quality than ERA5-Land but only 11 years, which is too short for our
rolling-origin design. Use as an independent check on the bucket over the overlap
period, not as a primary predictor.

- NASA Earthdata, product SPL4SMGP

### 2.3 ESA CCI combined soil moisture

1978-present, satellite-only (so not just a model of rainfall) — this one is
slightly more independent than ERA5-Land. Surface layer only (~5 cm), with gaps
under dense vegetation and heavy rain, which unfortunately is exactly when we care.

- esa-soilmoisture-cci.org

---

## TIER 3 — more case data. The power multiplier.

Unchanged from NEXT_STEPS.md and still the single highest-value action overall,
because every analysis in this project currently rests on **three scorable
regions**.

1. **Thailand Report 506**, melioidosis by province and month — 77 provinces
   instead of 6 regions. doe.moph.go.th / boe.moph.go.th
2. **Australia NNDSS**, melioidosis by state and month —
   nindss.health.gov.au/pbi-dashboard/ ; and the NT is where measured groundwater
   is already known to matter, so Tier 1.1 and Tier 3 meet there
3. A site where rainfall and soil saturation **decouple**, to test the mechanism
   rather than confirm a coincidence (Koutiala has them 0 weeks apart; Central
   Taiwan has them 9 weeks apart). Screen candidates on weather data alone before
   looking at any case data: Cote d'Ivoire and southern Ghana (two wet seasons),
   Sri Lanka (two monsoons, two case peaks), Kerala/Karnataka (sharp monsoon onset)

---

## Order of work

1. **Taiwan groundwater wells.** Highest upside, and it is the only item that
   could turn the core result positive. Start with the Central Geological Survey
   Pingtung Plain literature to find well IDs, then request the series.
2. **Thailand Report 506.** Highest certainty of being useful either way.
3. **ERA5-Land.** Cheap, fast, validates the bucket and adds the deep layers.
4. **SoilGrids pH, clay, organic carbon** by region. Tests the transfer gap.
5. GRACE/GLDAS, for West Africa timing where nothing else is available.

## What to be careful about

Do not present Tier 2 additions as expected improvements in predictive accuracy.
The R2 table at the top of this document is the reason, and it is our own
measurement on our own data — a reviewer will reach it independently in about ten
minutes. Presenting ERA5-Land as "more data, better model" and then reporting no
improvement reads as a failed attempt. Presenting it as "we verified that
soil-moisture products are 88-99% recoverable from rainfall, which explains why
elaborating the weather features cannot help, and we therefore went looking for a
variable that is not a function of rainfall" reads as someone who understands
their own problem.
