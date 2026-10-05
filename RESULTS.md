# Results

Every number below is measured output from code in this repository. Where I
previously reported a different figure, the correction and its reason are stated.
Nothing here is a target, an estimate or a value taken from another paper.

**Research question.** Can a climate-based melioidosis risk model trained on Taiwanese
surveillance data predict burden in West Africa, where surveillance barely exists?

**Short answer.** No, and the reason turned out to be more interesting than the
question. The model never learned a climate relationship in the first place. A
mechanistic soil-water model, with no fitted parameters and no case data, does
transfer — but only as a climatology, not as a forecast.

---

## 1. Data

| | |
|---|---|
| Cases | Taiwan NIDSS, notifiable disease 025, 2003–2026, six regions |
| Total cases | 925 (Kaoping 647, Southern 133, Central 97, Taipei 26, Northern 17, Eastern 5) |
| Weather | NASA POWER daily, one point per region (and eight West African points) |
| Modelling table | 7,362 region-weeks × 185 predictors, 921 cases, 8.3% of weeks positive |
| Week definition | MMWR epidemiological weeks, Sunday start, week belongs to the year containing its Wednesday |

**Why accuracy is never reported.** 91.7% of region-weeks have zero cases. A model
that always predicts "no case" scores 91.7% accuracy and is useless. Metrics used
throughout: ROC-AUC, average precision, AP lift over the base rate, Brier score,
calibration slope.

**One data defect found and fixed.** NASA POWER `WD10M` (wind direction) is corrupt
from 2012-12-31 onward at these points — 5,025 of 8,677 rows fall outside 0–360°,
with values such as −8,908 and −76,340. Including it silently truncated the dataset
to 2003–2013 and dropped 4,728 rows. The field is excluded.

---

## 2. Feature engineering

Two feature sets are compared throughout.

**Classic (46 columns).** Rainfall, temperature, humidity and wind at weekly lags 0–6,
plus 4/8/12-week rolling rainfall and two seasonal harmonics. This is what the
published literature uses.

**Mechanistic (141 columns).** Built because rain does not cause infection — saturated
soil does. A daily bucket model (150 mm capacity, Hargreaves–Samani PET from
temperature alone, so it is computable anywhere on Earth) tracks soil saturation, from
which: saturated days, saturation excess (standing water), antecedent precipitation
indices at three memory lengths, vapour pressure deficit, diurnal temperature range,
dry-spell length, rain concentration (Gini), days above 10 mm and 25 mm, wetting
events (≥10 mm after a ≥10-day dry spell), and an aerosolisation index (maximum wind
speed × soil saturation).

Built by `scripts/build_features_v2.py` and `scripts/build_features_africa_v2.py`.

---

## 3. Model benchmark (notebook 04)

Rolling-origin cross-validation: train on all years before year Y, test on year Y.
14 folds, 2012–2025. No random splits anywhere.

| model | classic AUC | mechanistic AUC | full AUC | full AP | full Brier |
|---|---|---|---|---|---|
| extra trees | **0.823** ± 0.036 | 0.818 ± 0.032 | 0.823 ± 0.026 | **0.394** | 0.067 |
| random forest | 0.820 ± 0.032 | 0.817 ± 0.029 | **0.826** ± 0.024 | 0.391 | 0.067 |
| logistic L1 | 0.808 ± 0.036 | 0.803 ± 0.043 | 0.808 ± 0.040 | 0.336 | 0.161 |
| logistic L2 | 0.804 ± 0.035 | 0.794 ± 0.042 | 0.801 ± 0.037 | 0.316 | 0.160 |
| XGBoost | 0.799 ± 0.041 | 0.796 ± 0.048 | 0.802 ± 0.048 | 0.348 | 0.079 |
| hist gradient boosting | 0.794 ± 0.041 | 0.798 ± 0.033 | 0.803 ± 0.039 | 0.346 | 0.072 |
| LightGBM | 0.789 ± 0.034 | 0.792 ± 0.042 | 0.796 ± 0.032 | 0.332 | 0.077 |
| MLP (TabNet stand-in) | 0.760 ± 0.064 | 0.785 ± 0.050 | 0.786 ± 0.048 | 0.335 | 0.071 |

**Finding 3.1 — the mechanistic features add nothing.** 0.823 → 0.818 replacing, 0.823
→ 0.826 adding. All within one standard deviation. 141 biologically motivated features
bought nothing.

**Finding 3.2 — XGBoost does not win.** It is 0.024 AUC behind extra trees and
statistically tied with L1 logistic regression. Extra trees beats logistic regression
by +0.023 AUC, 95% CI [+0.012, +0.035], bootstrap p < 0.001, winning 12 of 14 folds.
For context, Wongbutdee 2025 reports TabNet 0.950 vs XGBoost 0.892 as a meaningful
advance. Here the algorithm choice is worth ≈0.02 AUC; the evaluation choice (§5) is
worth ≈0.18.

**Finding 3.3 — ranking and calibration are different problems.** Logistic regression
ranks within 0.02 AUC of the trees with a Brier score 2.4× worse. A surveillance alert
needs both.

---

## 4. Negative controls (notebook 05)

Each control destroys one candidate source of skill. Extra trees, full feature set,
same 14 folds.

| control | AUC | AP lift | expected |
|---|---|---|---|
| none (reference) | 0.824 | 4.67× | — |
| **case labels shuffled within region** | **0.812** | 3.63× | **≈0.500** |
| weather shifted +26 weeks | 0.821 | 4.08× | collapse |
| weather → climatological mean | 0.803 | 4.04× | collapse |
| weather from the wrong region | 0.799 | 3.50× | collapse |
| week of year only | 0.628 | 1.73× | seasonality floor |

**Finding 4.1.** Randomising the outcome variable — destroying every link between a
week's weather and that week's cases, while preserving each region's base rate — costs
0.012 AUC. The model loses 1% of its performance from having its labels shuffled.

No region identifier exists in the feature table. But each region's climate signature
identifies it uniquely, so the model recognises the region from its weather and applies
that region's base rate. Kaoping is 32.3% positive weeks; Eastern is 0.3%.

---

## 5. Decomposition and within-region evaluation (notebook 05)

Out-of-fold predictions pooled across all 14 folds.

| predictor | pooled AUC | **within-region AUC** | 95% CI |
|---|---|---|---|
| climatology, P(case) by region × week | 0.844 | **0.662** | [0.630, 0.696] |
| season only (two harmonics) | 0.632 | 0.656 | [0.623, 0.688] |
| raw weather, 185 features | 0.825 | 0.643 | [0.609, 0.676] |
| weather anomalies (climatology removed) | 0.777 | 0.620 | [0.586, 0.654] |
| anomalies + season | 0.767 | 0.611 | [0.577, 0.645] |
| region base rate alone, no weather | 0.817 | 0.478 | [0.444, 0.512] |

Paired bootstrap, anomalies+season minus climatology baseline, within region:
**−0.051, 95% CI [−0.081, −0.021], p = 0.001.**

Per-region, full model, out-of-fold:

| region | positives | within-region AUC | base rate |
|---|---|---|---|
| Taipei | 18 | 0.655 | 2.5% |
| Central | 61 | 0.651 | 8.3% |
| Kaoping | 236 | 0.649 | 32.3% |
| Southern | 54 | 0.625 | 7.4% |
| Northern | 11 | 0.539 | 1.5% |
| Eastern | 2 | too few | 0.3% |
| weighted mean | | **0.643** | |

**Finding 5.1 — the headline.** A constant per region, with no weather and no
calendar, reaches 0.817 pooled AUC against the full model's 0.825. The entire weather
apparatus adds 0.008.

**Finding 5.2.** 56% of the pooled skill above chance is between-region. The honest
within-region figure is 0.643, not 0.825.

**Finding 5.3.** The best predictor of all is a 6 × 52 lookup table of historical
case frequency that uses no weather data. Every machine learning model is worse, and
the model restricted to genuine weather anomalies is *significantly* worse (p = 0.001).

> **Within a region, the year-to-year weather anomaly carries no usable information
> about whether a given week will produce a melioidosis case. The predictive skill of
> climate-based melioidosis models is the seasonal climatology plus the region's base
> rate, and nothing else.**

---

## 6. SHAP attribution

XGBoost on the full feature set, TreeExplainer, all 7,362 rows.

| mechanism family | share of total |mean SHAP| |
|---|---|
| wind / aerosolisation | 21.3% |
| dryness (VPD, diurnal range, dry spells) | 20.8% |
| rainfall | 13.7% |
| soil saturation | 12.1% |
| water balance / PET | 11.4% |
| temperature | 11.0% |
| antecedent memory | 4.4% |
| season | 1.1% |
| **wetting events** | **0.0%** |

Highest-attribution single feature: `dtr_mean_lag2`, the mean day-to-night temperature
range two weeks prior (mean |SHAP| 0.290, next highest 0.183).

**Finding 6.1.** Diurnal temperature range is a geography variable — it encodes
cloudiness and distance from the coast. The model's top predictor is the feature it
uses to identify the region, which is independent confirmation of §4 and §5 from a
completely different method.

**Finding 6.2.** The mechanism most cited in the melioidosis literature — heavy rain
breaking a dry spell — receives 0.0% of attribution.

---

## 7. Transfer between regions (notebook 06)

Same target weeks scored twice: trained on the target region's own earlier years, or
on the other five regions' earlier years. Four split years (2014, 2017, 2020, 2023),
three seeds averaged per cell, 12 scorable cells per feature set.

| features | cells | mean own | mean other | mean gap | 95% CI | gap > 0 |
|---|---|---|---|---|---|---|
| classic | 12 | 0.668 | 0.599 | **+0.069** | [+0.041, +0.098] | 11/12 |
| mechanistic | 12 | 0.625 | 0.538 | +0.087 | [+0.039, +0.140] | 10/12 |
| full | 12 | 0.638 | 0.551 | +0.088 | [+0.036, +0.141] | 9/12 |

Paired within (split year, target region): mechanistic vs classic changes the gap by
+0.019, 95% CI [−0.010, +0.050], p = 0.224. Full vs classic: +0.019,
95% CI [−0.011, +0.050], p = 0.240.

**Central Taiwan, every split, full feature set:**

| split year | own past | trained on other five regions |
|---|---|---|
| 2014 | 0.675 | **0.481** |
| 2017 | 0.666 | **0.487** |
| 2020 | 0.683 | **0.432** |
| 2023 | 0.719 | **0.514** |

**Finding 7.1.** Changing region within one country costs ≈0.069 AUC, about 40% of
the within-region skill available.

**Finding 7.2.** Mechanistic features do not improve transfer. The prediction made
from the earlier region-effect experiment was wrong and is retracted.

**Finding 7.3.** Across four splits and three feature sets, a model trained on the
rest of Taiwan never exceeds 0.514 AUC on Central and twice falls clearly below
chance, while Central's own past reaches 0.67–0.72. The borrowed model is not useless
there, it is **inverted**. Southern's gap hovers near zero, so the penalty is
region-specific rather than a uniform law — consistent with §5, since a
region-recognition shortcut has no reason to point the right way somewhere new.

---

## 8. How much local data would a new region need? (notebook 06)

Train on five regions, add K weeks of the target region's own recent history
(weighted 5×), test on post-2018 target weeks.

Kaoping:

| local weeks | local cases | AUC | Brier | calibration slope |
|---|---|---|---|---|
| 0 | 0 | 0.638 | 0.282 | 0.55 |
| 26 | 13 | 0.677 | 0.204 | 0.63 |
| 52 | 20 | 0.653 | 0.206 | 0.75 |
| 104 | 45 | 0.689 | 0.198 | 0.87 |
| 208 | 78 | 0.662 | 0.205 | 0.78 |
| 416 | 147 | 0.651 | 0.209 | 0.84 |

**Finding 8.1.** Local data buys calibration, not ranking. AUC has no defensible
trend; Brier improves 29% and the calibration slope moves from 0.55 to ≈0.87. A slope
of 0.55 means the borrowed model's probabilities were roughly twice as extreme as
reality.

**Practical implication.** A surveillance-poor region does not need local data to know
*which weeks* to watch — the seasonal pattern does that, and seasons are not secret.
It needs local data to know *what the numbers mean*. Roughly two years and 45
confirmed cases suffices.

---

## 9. Applicability domain for West Africa

Taiwan 1st–99th percentile per feature, applied to 9,816 West African site-weeks.

| | |
|---|---|
| West African weeks entirely inside Taiwan's range | **7.7%** |
| median share of features inside, per week | 61.6% |
| median share inside across the 30 highest-attribution features | **43.3%** |

| site | % features in domain | % weeks fully in |
|---|---|---|
| Korhogo | 77.4 | 11.8 |
| Bobo-Dioulasso | 72.8 | 15.8 |
| Sikasso | 69.8 | 12.8 |
| Koutiala | 66.5 | 7.4 |
| Bamako | 65.9 | 4.3 |
| Ouagadougou | 64.9 | 3.2 |
| Ségou | 61.0 | 5.4 |
| Mopti | 57.9 | 0.5 |

**Finding 9.1.** The model extrapolates on most of the features it relies on. Any
West African prediction from the fitted model is an extrapolation.

---

## 10. The mechanism: soil saturation timing (notebook 07)

No case data enters this calculation. Physics plus one capacity parameter chosen a
priori. Peaks estimated by resultant-vector circular mean over the full 52-week
profile; bootstrap resamples whole years.

| region | cases | peak cases | peak rainfall | rain error | 95% CI | peak soil | soil error | 95% CI |
|---|---|---|---|---|---|---|---|---|
| Kaoping | 646 | wk 35.1 | wk 29.9 | −5.2 | [−6.4, −4.5] | wk 34.6 | **−0.5** | [−1.9, +0.5] |
| Southern | 131 | wk 33.6 | wk 29.3 | −4.3 | [−6.1, −2.6] | wk 33.0 | **−0.6** | [−2.5, +1.2] |
| Central | 97 | wk 35.4 | wk 26.9 | −8.5 | [−10.6, −6.8] | wk 29.6 | −5.8 | [−8.1, −3.8] |

Mean absolute timing error: **rainfall 6.0 weeks, soil saturation 2.3 weeks.**

**Correction.** An earlier version of this result used the single highest week (argmax)
as the peak estimator and reported soil saturation as accurate to 1–2 weeks in all
three regions. The argmax is unstable on broad or two-humped profiles. With the robust
estimator, soil saturation is unbiased in Kaoping and Southern (CIs contain zero) but
5.8 weeks early in Central (CI excludes zero). It still beats rainfall in Central
(5.8 vs 8.5 weeks). The defensible claim is a 2.6× reduction in timing error overall,
unbiased in two of three regions.

### Year-to-year: a null result

| region | usable years | r(soil peak, case peak) | 95% CI | r(rain peak, case peak) |
|---|---|---|---|---|
| Kaoping | 22 | +0.21 | [−0.28, +0.66] | +0.59 |
| Southern | 10 | −0.27 | [−0.71, +0.45] | −0.02 |
| Central | 6 | −0.15 | [−0.86, +0.60] | −0.25 |

**Finding 10.1.** The soil model explains the average seasonal shape and carries no
information about which individual year will run early or late. This agrees with §5
from an independent direction. **The mechanism supports a climatological claim, not a
forecast.** The literature routinely conflates the two.

### Parameter sensitivity

| capacity | Kaoping | Southern | Central | mean abs error |
|---|---|---|---|---|
| 50 mm | −2.8 | −3.1 | −8.2 | 4.7 wk |
| 100 mm | −1.4 | −1.7 | −7.0 | 3.3 wk |
| **150 mm (chosen a priori)** | −0.5 | −0.6 | −5.8 | **2.3 wk** |
| 250 mm | +0.4 | +0.8 | −4.1 | 1.8 wk |

**Finding 10.2.** Soil saturation beats rainfall at every capacity. 150 mm is not
optimal — 250 mm is better — so the pre-chosen value understates the mechanism.

**Why rainfall fails.** Central and Southern receive their heaviest rain in the June
plum rains, onto soil dry enough to absorb it. The soil does not saturate until the
typhoon season two months later, which is when cases occur. Rainfall is a flux; soil
saturation is a stock. This is why the published lag estimates range from two weeks
to four months — there is no single lag because rainfall is the wrong variable.

---

## 11. The West Africa prediction (notebook 07)

Same soil model, eight sites, no case data.

| site | peak soil saturation | 95% CI | peak saturation | annual rain |
|---|---|---|---|---|
| Bobo-Dioulasso | wk 33.4 | [33.2, 33.7] | 0.992 | 1,177 mm |
| Korhogo | wk 33.6 | [33.3, 34.0] | 0.953 | 999 mm |
| Koutiala | wk 33.9 | [33.6, 34.3] | 0.952 | 928 mm |
| Sikasso | wk 33.9 | [33.6, 34.2] | 0.965 | 1,045 mm |
| Ouagadougou | wk 34.1 | [33.8, 34.4] | 0.982 | 870 mm |
| Bamako | wk 34.2 | [33.8, 34.6] | 0.935 | 1,023 mm |
| Ségou | wk 34.7 | [34.4, 35.0] | 0.898 | 681 mm |
| Mopti | wk 34.9 | [34.7, 35.2] | 0.884 | 561 mm |

> **Pre-registered prediction: melioidosis onset in southern Mali, Burkina Faso and
> northern Côte d'Ivoire peaks in epidemiological weeks 34–37 — late August to
> mid-September.**

All eight sites reach 0.88–0.99 saturation, so the environment supports release across
the whole study area, not only the wettest sites.

**The competing prediction.** The Taiwan-trained machine learning model, applied to the
same sites, places the peak at weeks 26–30 (June–July) — six to nine weeks earlier and
outside the mechanistic window.

**The test.** Month-of-onset distribution of the 31 confirmed Koutiala cases
(Lancet Global Health). August–September clustering validates the mechanistic route;
June–July clustering validates the extrapolation and refutes the mechanism.

**A note on an earlier error.** With raw rainfall features the transfer model ranked
Mopti (561 mm/yr, driest) as highest risk and Bobo-Dioulasso (1,177 mm, wettest) as
lowest. The soil model inverts this to the sensible ordering (Bobo 0.489 mean annual
saturation and 18.5 saturated weeks; Mopti 0.269 and 7.0). The mechanistic features
earn their place in the *transfer* model even though §3 shows they add nothing to the
Taiwan model.

---

## 12. What goes in the paper

**The contribution.** Not a better melioidosis model — a demonstration that the
standard evaluation in this literature cannot distinguish a climate signal from
region identity and seasonality, with three cheap checks that can, and a mechanistic
alternative that survives them.

**Recommended reporting standard.**

1. Report **within-region** AUC when data spans multiple places. Pooled AUC over
   regions with different base rates measures region identification.
2. Always include a **climatology baseline** (P(case) by place × week of year). A model
   that cannot beat a lookup table has not demonstrated a climate effect.
3. Always run the **shuffled-label control**, shuffling within place so base rates are
   preserved. Five lines of code; it would have caught this immediately.
4. Validate externally before deployment. Finding 7.3 shows a borrowed model can be
   actively inverted.
5. Separate climatological claims from forecasts. Finding 10.1 shows this data supports
   only the former.

**What this does not claim.** It does not show that published melioidosis models are
wrong, or that no climate signal exists. Published AUCs of 0.89–0.95 are *consistent
with* measuring region identity and seasonality; the standard evaluation cannot tell
the two apart, and these checks can. A real year-to-year climate signal may exist and
be undetectable at 925 cases over 23 years — that is a power statement, and §5's
confidence intervals bound it.

**Limitations.** Single country for training. 925 cases, with 70% in one region. Case
onset dates unavailable — notification weeks are used, which blurs timing by an unknown
amount. One weather grid point per region, which cannot represent within-region
heterogeneity. No soil type, land use, or agricultural calendar data. The West Africa
prediction is untested until the Koutiala onset distribution is obtained.
