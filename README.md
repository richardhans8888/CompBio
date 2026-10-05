# Melioidosis Risk Model Transfer — Taiwan to West Africa

Can a climate-based melioidosis risk model trained on Taiwan's surveillance
data predict disease burden in West Africa, where surveillance barely exists?

## Folder layout

    data/raw/cases/      Taiwan NIDSS weekly case counts, one file per region
    data/raw/weather/    NASA POWER daily weather, one file per region point
    data/processed/      merged, analysis-ready tables
    scripts/             data pipeline and modelling code
    outputs/             figures, model results, tables

## Data sources

Cases — Taiwan National Infectious Disease Statistics System (NIDSS),
melioidosis (disease id 025), Date of Onset, Indigenous and Imported,
weekly by region, 2003 to 2026.
https://nidss.cdc.gov.tw/en/nndss/disease?id=025

Weather — NASA POWER daily point data, 1981 to present, global coverage.
A global source is used deliberately so that the same variable definitions
apply in Taiwan and in West Africa; otherwise a drop in performance after
transfer could not be separated from a difference in measurement.
https://power.larc.nasa.gov

## Current state of the data

7,470 region-weeks, 925 confirmed cases, six regions.

    Kaoping     647   (72%)
    Southern    133   (15%)
    Central      97   (11%)
    Taipei       26
    Northern     17
    Eastern       5

Cases peak in weeks 29-36 (mid-July to early September) at roughly eight
times the May trough.

91.7% of region-weeks contain zero cases. Accuracy is therefore not a usable
metric — a model predicting no cases everywhere would score 91.7%. Report
AUC, precision-recall and calibration instead.

## Scripts

    python3 scripts/build_cases.py    merge regional case files -> long table

## Headline findings (see RESULTS.md for every number and its provenance)

The project changed direction once the controls were run. The original question was
whether a Taiwan-trained climate model predicts West African burden. The answer is no,
and the reason is that the model never learned a climate relationship at all.

1. **A model with pooled AUC 0.825 keeps 0.812 when its case labels are randomly
   shuffled within region.** It loses 1% of its performance from having the outcome
   variable destroyed.
2. **A single constant per region — its historical case rate, no weather, no calendar —
   scores 0.817.** The entire weather apparatus adds 0.008 AUC.
3. **Within-region AUC is 0.643, not 0.825.** 56% of the apparent skill above chance was
   between-region.
4. **The best predictor of all is a 6 x 52 lookup table of historical case frequency
   (within-region AUC 0.662), which uses no weather.** A model restricted to genuine
   weather anomalies is significantly *worse* (0.611, p = 0.001).
5. **Transfer between Taiwanese regions costs 0.069 AUC**, 95% CI [0.041, 0.098], and in
   Central Taiwan a borrowed model is *inverted* — 0.43 to 0.51 across four split years
   against 0.67-0.72 for its own past.
6. **141 mechanistically-motivated features added nothing** (0.823 -> 0.826), and SHAP
   shows the top feature is day-night temperature range, a geography variable.
7. **But the mechanism transfers.** A soil water-balance model with no case data and one
   a-priori parameter locates the seasonal case peak with a mean error of 2.3 weeks
   against rainfall's 6.0 weeks, unbiased in two of three regions. In Central and
   Southern Taiwan peak rainfall is ten weeks early and peak soil saturation is right.
8. **With a stated limit.** Year to year the mechanism carries no signal (all three
   correlations straddle zero). It supports a climatological claim, not a forecast.

**Pre-registered prediction.** Melioidosis onset in southern Mali, Burkina Faso and
northern Cote d'Ivoire peaks in epidemiological weeks 34-37 (late August to
mid-September). Soil saturation peaks at weeks 33.4-34.9 across all eight West African
sites, every one reaching 0.88-0.99 saturation. The Taiwan-trained ML model predicts
weeks 26-30 instead, so the two approaches are distinguishable by the month-of-onset
distribution of the 31 confirmed Koutiala cases.

## Notebooks

    01_taiwan_model.ipynb                  first model, classic rainfall lags
    02_what_transfers.ipynb                feature ablation
    03_west_africa_data.ipynb              West Africa weather, first look
    04_mechanistic_features.ipynb          soil water balance, 8 models x 3 feature sets
    05_what_the_model_really_learns.ipynb  negative controls, decomposition, within-region
    06_transfer_and_regions.ipynb          region transfer, local-data requirement
    07_soil_timing_and_west_africa.ipynb   the mechanism, and the prediction

Run order for the v2 work: scripts/build_features_v2.py and
scripts/build_features_africa_v2.py, then notebooks 04 to 07. Notebook 05 is the one
that matters most.
