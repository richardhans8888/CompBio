# What makes this Q1, and what to do next

## The question your lecturer is asking

"Why do research when you are just finding out?" — she wants a measurable
improvement over what exists, not a description. Here is the honest inventory of
what this project improves, with numbers, and what it does not.

### Improvement 1 — 2.6x better seasonal timing than the published approach

The standard predictor in every melioidosis climate paper is rainfall. Measured
against the week cases actually peak, averaged over three Taiwanese regions and
23 years:

| predictor | mean absolute timing error |
|---|---|
| rainfall (what the literature uses) | **6.0 weeks** |
| soil saturation (this work) | **2.3 weeks** |

In Central and Southern Taiwan rainfall peaks in week 24 and cases in week 34 —
rainfall is wrong by ten weeks, because the June plum rains fall on soil dry
enough to absorb them. Soil saturation peaks in week 32–33 and is unbiased
(95% CI contains zero) in two of three regions. The result holds at every value
of the one free parameter, and the value chosen a priori (150 mm) *understates*
it, so it is conservative.

This is a real accuracy improvement at the quantity that matters for a country
with no surveillance: when is the season.

### Improvement 2 — a predictor nobody has used

Verified by literature search: **no published melioidosis study uses soil
moisture as a state variable.** Rainfall, humidity, dew point, wind, land-surface
temperature, NDVI/NDWI and soil *type* have all been used. Soil water balance,
or any satellite soil-moisture product (SMAP, ESA CCI, ERA5-Land, GLDAS), has
not.

And two independent groups have pointed straight at the gap:
- Kaestli/Currie, Darwin, 23-year series: used locally measured **groundwater
  level** and found it significant (*J Infect* 2016).
- Hempenstall, Townsville: names the absence of **groundwater data** as the
  study's *primary* limitation (*Environ Health Prev Med* 2023).

The mechanism also now has direct experimental support: Chen et al. 2025 sampled
Taiwanese croplands at 0–10, 30 and 60 cm, found baseline detection highest at
60 cm, and showed PCR-positive detection rising significantly at 30 cm and at the
surface after rain (p < 0.01 each) and falling again after sunny spells
(*PLoS Negl Trop Dis* 19:e0013640).

### Improvement 3 — the first external validation in this disease

Of eleven melioidosis prediction papers found: **zero** validated externally in a
different region or country. **Zero** used a temporal or rolling-origin split.
**None** of the environmental/climate models compared against any baseline —
not climatology, not seasonal-naive, not intercept-only.

### Improvement 4 — a reporting standard, with the diagnostics that find the problem

Three checks, five lines of code each, that this literature does not run:
1. within-region AUC, not pooled AUC
2. a climatology baseline (P(case) by place x week of year)
3. outcome labels permuted within place

### Improvement 5 — V-REx repairs inverted transfer (new, expO)

Zero-shot into a held-out region, trained on the other five, mean AUC over three
targets:

| training method | mean AUC | Central (the inverted case) |
|---|---|---|
| target region's own climatology | **0.683** | 0.687 |
| V-REx (variance across environments) | 0.606 | **0.563** |
| GroupDRO (worst-region loss) | 0.572 | 0.515 |
| IRMv1 (invariant risk) | 0.567 | 0.475 |
| ERM (ordinary training) | 0.552 | **0.465 (below chance)** |

Ordinary training is *inverted* in Central Taiwan. Penalising the variance of
loss across regions lifts it back above chance (+0.098) and is the best domain
generalisation method overall (+0.054 over ERM). That is a genuine, novel,
positive methodological result — invariance penalties remove a harmful
region-identification shortcut in a real epidemiological transfer task.

**But none of them beats the target region's own seasonal lookup table.**

---

## What this project does NOT have, stated plainly

**A better AUC.** It cannot be honestly produced, and here is everything that has
been tried:

| attempt | result |
|---|---|
| 8 classical learners (logistic L1/L2, RF, extra trees, HistGB, XGBoost, LightGBM, MLP) | best 0.826 pooled; 0.643 within-region |
| 3 feature sets (46 classic, 141 mechanistic, 185 combined) | all within one SD of each other |
| new target: annual case count (within-region anomaly) | **skill -0.14 to -0.25** vs "average year" |
| new target: onset week anomaly | **skill -0.06 to -0.33** vs "usual week" |
| new target: in-season forecast at weeks 12/20/24/28/32 | **skill -0.06 to -0.21** at every cutoff |
| 4 domain-generalisation methods (ERM, GroupDRO, IRMv1, V-REx) | best 0.606 vs climatology 0.683 |

Negative skill means worse than doing nothing. Three different prediction targets,
at three aggregation levels, all lose to the baseline. The permutation control on
the annual target gives -0.276 against the real -0.245 — indistinguishable.

The ceiling is not a modelling failure. There are 925 cases over 23 years with
70% in one region, and the year-to-year climate anomaly does not carry
information about melioidosis risk at that sample size. Producing a higher number
by searching methods would be the exact practice this paper criticises.

---

## The honest path to a stronger paper: more data

One dataset would change everything, and it is the highest-priority action.

### Priority 1 — Thailand. 77 provinces instead of 6 regions.

Thailand's Bureau of Epidemiology Report 506 publishes notifiable disease counts
by province and month. Melioidosis is notifiable (disease code 28). NE Thailand
is the global incidence maximum.

Why this is decisive: **the within-region analysis currently rests on 3 scorable
regions.** With 77 provinces it rests on dozens. If a modest climate signal
exists, 77 provinces x 10+ years can detect it where 6 regions cannot. And if
the null holds in a second country with 10x the units, the negative result
becomes close to unarguable — a two-country, 83-unit demonstration.

Either outcome is a result. That is the answer to "what if it isn't good enough":
with Thailand in, both outcomes are publishable.

- Report 506: http://doe.moph.go.th/surdata/  (and boe.moph.go.th mirrors)
- Also: Thai NESDC provincial population denominators
- Backup: the published Ubon Ratchathani series (4,871 cases, 219 subdistricts,
  2013–2022) is described in Wongbutdee 2024 IJERPH 21(5):614 — contact the
  authors for data, or extract what the figures allow

### Priority 2 — Australia Northern Territory

NNDSS publishes melioidosis by state and month, and the Darwin prospective study
is the longest clean series in existence. The NT is the one place with a
*measured* groundwater record that has already been shown significant — so it is
where the soil-moisture mechanism can be validated against real hydrology rather
than a bucket model.

- NNDSS: https://nindss.health.gov.au/pbi-dashboard/
- NT groundwater: https://www.ntg.gov.au (water data portal)

### Priority 3 — ERA5-Land soil moisture. Validate the bucket.

Our 150 mm bucket is a one-parameter toy. ERA5-Land provides modelled volumetric
soil water in four layers (0–7, 7–28, 28–100, 100–289 cm) hourly from 1950, free.
Two uses:
1. **Validate**: correlate our bucket's saturation against ERA5-Land layer 2/3.
   If they agree, the toy is defensible. If they disagree, ERA5-Land replaces it.
2. **Strengthen**: layer 3 and 4 (28–289 cm) are where the organism's reservoir
   actually lives (Ribolzi 2022: maximum at 170 cm; 100% groundwater persistence
   below 110 cm). No melioidosis paper has used deep-layer soil water. That is a
   second, deeper novelty than the bucket.

- Copernicus CDS: https://cds.climate.copernicus.eu  (free account, `cdsapi`)
- Variables: `volumetric_soil_water_layer_1..4`, `skin_temperature`,
  `total_precipitation`, `potential_evaporation`
- Also worth adding: SMAP L4 (2015–, 9 km, NASA Earthdata) and GRACE/GLDAS
  groundwater storage anomaly

### Priority 4 — a site where rain and soil DECOUPLE

This is the flaw in the current West Africa test. In Koutiala, peak rainfall and
peak soil saturation both fall in week 35 — **zero weeks apart**. So the Mali
confirmation cannot distinguish our mechanism from plain rainfall. Compare:

| site | peak rain week | peak soil week | separation |
|---|---|---|---|
| Koutiala, Mali | 35 | 35 | **0** |
| Kaoping | 35 | 32 | -3 |
| Central Taiwan | 24 | 33 | **+9** |
| Southern Taiwan | 24 | 32 | **+8** |

To test the mechanism rather than confirm a coincidence, find sites with a
bimodal or early-rain regime: Côte d'Ivoire and southern Ghana have two wet
seasons, Sri Lanka has two monsoons with two case peaks (Corea 2018 reports 67%
of cases in monsoonal periods), and Kerala/Karnataka have a sharp SW monsoon
onset. Screen candidates by computing the rain-peak-to-soil-peak separation from
NASA POWER before looking at any case data.

### Priority 5 — soil type and land use, as region-level covariates

expD and expG2 showed the transfer penalty is region-specific and that weather
features cannot see it. The obvious candidates for what they are missing:

- SoilGrids 2.0 (250 m): clay, sand, pH, organic carbon, bulk density —
  https://soilgrids.org
- Harmonized World Soil Database v2 (FAO) — Acrisols were the favourable soil in
  the SE Asia MaxEnt study
- ESA WorldCover / MODIS land cover: rice paddy extent, irrigated area
- Diabetes prevalence by region (the dominant host risk factor) — Taiwan NHIRD
  published figures, or IHME GBD subnational

If adding these recovers the region gap, that identifies what transfers and what
does not — which is a positive, mechanistic answer to the paper's own question.

---

## Modern methods: what fits, and what to call it

**Your instinct about zero-shot learning is right, and it is the correct name for
what this project already does.** Predicting in West Africa with no West African
case labels is zero-shot cross-domain transfer. Use that vocabulary — it is how
the ML community indexes this problem and it will help the paper find reviewers.

The relevant literature, and what each contributes:

| method | what it does | status here |
|---|---|---|
| **V-REx** (Krueger et al., ICML 2021) | penalises variance of loss across environments | **run, best DG method, repairs inversion** |
| **IRMv1** (Arjovsky et al. 2019) | penalises features whose optimal predictor varies by environment | run |
| **GroupDRO** (Sagawa et al., ICLR 2020) | minimises worst-group loss | run |
| **TabPFN v2** (Hollmann et al., *Nature* 2025) | tabular foundation model, in-context learning — literally zero-shot/few-shot on tabular data, designed for n < 10k | **blocked by sandbox egress — run on your Mac, code below** |
| **Conformal prediction** | distribution-free prediction intervals with guaranteed coverage | worth adding; directly addresses the calibration finding |
| **Hierarchical Bayesian partial pooling** | the correct statistical treatment of 6 regions with wildly different base rates; borrows strength without the shortcut | **highest-value addition** — gives uncertainty and handles small regions properly |

### TabPFN, to run locally

```bash
pip install tabpfn
# accept terms at https://huggingface.co/Prior-Labs/tabpfn_3_5 then:
hf auth login
```

```python
import csv, numpy as np
from tabpfn import TabPFNClassifier
from sklearn.metrics import roc_auc_score, average_precision_score

rows  = list(csv.DictReader(open("data/processed/taiwan_model_table_v2.csv")))
META  = {"region","year","week","yearweek","cases"}
feats = [c for c in rows[0] if c not in META]
X  = np.array([[float(r[c]) for c in feats] for r in rows])
y  = np.array([1 if int(r["cases"])>0 else 0 for r in rows])
yr = np.array([int(r["year"]) for r in rows])
reg= np.array([r["region"] for r in rows])

# rolling origin, same protocol as notebook 04
for t in range(2012, 2026):
    tr, te = yr < t, yr == t
    clf = TabPFNClassifier(device="cpu", n_estimators=4, random_state=0)
    clf.fit(X[tr], y[tr])
    p = clf.predict_proba(X[te])[:, 1]
    print(t, f"{roc_auc_score(y[te], p):.3f}",
             f"{average_precision_score(y[te], p)/y[te].mean():.2f}x")

# and the number that matters - within region, against the lookup table
# (reuse the within_region() and climatological_risk() functions from notebook 05)
```

**Report its within-region AUC against the climatology baseline, not its pooled
AUC.** If TabPFN also fails to beat 0.662, the paper can say the 2025 tabular
state of the art does not rescue this either — which closes the obvious
reviewer objection ("you only tried old methods") permanently.

---

## Why a negative core result can still be Q1

What makes this publishable is not the sign of the result, it is that it is
*decisive and constructive*:

1. **It overturns a live literature.** A 2025 paper reports accuracy 0.950 for
   melioidosis prediction, pooled over 219 subdistricts with no baseline. On data
   that is ~92% zero-case, accuracy is not a measure of anything. We can
   demonstrate why with controls anyone can rerun.
2. **It is exhaustive.** 8 classical learners, 3 feature sets, 3 prediction
   targets, 4 domain-generalisation methods, 5 negative controls, and (with
   Thailand) 2 countries. A reviewer cannot say "you did not try hard enough" —
   that objection is pre-answered by the method table.
3. **It replaces what it removes.** Soil saturation timing, 2.6x better than
   rainfall, zero fitted parameters, a stated applicability domain, and a
   pre-registered forecast.
4. **It is honest about its own limits.** No year-to-year skill. Mali confirms
   but cannot discriminate. 925 cases is a power constraint, not proof of absence.

Be careful with the novelty claim. The pooled-versus-within-cluster point is
**established** in clinical prediction methodology (van Klaveren et al. 2014;
TRIPOD-Cluster 2023), in species distribution modelling (Roberts et al. 2017;
Ploton et al. 2020), and in disease forecasting (Johansson et al. 2016 for
dengue). Zech et al. (*PLoS Med* 2018) report that pooling chest radiographs
across hospitals with different disease prevalence means "merely sorting by
hospital system achieved an AUC of 0.861" — our 0.817, eight years earlier.

So the claim is: **standard clustered-data and spatial-validation diagnostics,
never applied to melioidosis climate-risk models, overturn that literature's
reported performance — and a mechanistic alternative survives them.** Cite Zech,
Ploton, van Klaveren, Roberts and Johansson as the provenance of each diagnostic.
Claim a new statistical insight and peer review will remove it.

Also avoid the word "inflated". The pooled AUC is not biased; it is an unbiased
estimate of a nearly useless *estimand* (between-region discrimination) when the
decision is within-region. That framing is both more correct and harder to argue
with.

---

## Order of work

1. Download Thailand Report 506 provincial melioidosis counts. Everything else
   is secondary to this.
2. Set up a Copernicus CDS account and pull ERA5-Land soil water for the Taiwan
   and West Africa points. Validate the bucket against layer 2/3.
3. Run TabPFN locally on the existing table; report within-region AUC.
4. Screen candidate sites for rain/soil decoupling using NASA POWER only.
5. Fit a hierarchical Bayesian model with partial pooling across regions.
6. Add SoilGrids and land cover as region-level covariates; test whether they
   recover the region gap.
