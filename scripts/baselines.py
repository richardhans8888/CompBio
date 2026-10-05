"""
Baseline models for Taiwan melioidosis weekly counts.

Every machine learning model must beat these. They are deliberately simple and,
just as importantly, they can all be rebuilt in West Africa — which is the point.
Comparing against a published accuracy figure from another country would tell us
nothing, because that number cannot travel either.

Split is TEMPORAL, never random: train on 2003-2018, test on 2019-2026. A random
split would let the model see future weeks while predicting past ones, and on
seasonal data that inflates scores badly.

Baselines
  zero            always predict no cases - exists to show why accuracy is useless
  region_mean     that region's average weekly count, from training years only
  climatology     average for that region AND week-of-year, training years only
  seasonal_naive  what actually happened the same week last year
  rain_rule       flag the week if recent rainfall crossed a threshold

Output  outputs/baseline_results.csv   metrics per model
        outputs/baseline_predictions.csv   per-row predictions, for later comparison
"""
import csv, math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABLE = ROOT / "data" / "processed" / "taiwan_model_table.csv"
OUTD = ROOT / "outputs"

TRAIN_END = 2018          # train <= this year, test after


def load():
    rows = []
    for r in csv.DictReader(TABLE.open()):
        rows.append({
            "region": r["region"], "year": int(r["year"]), "week": int(r["week"]),
            "cases": int(r["cases"]),
            "rain1": float(r["rain_mm_lag1"]), "rain2": float(r["rain_mm_lag2"]),
            "rain3": float(r["rain_mm_lag3"]), "rain_sum4w": float(r["rain_sum4w"]),
        })
    return rows


# ------------------------------------------------------------------ metrics
def mae(y, p):  return sum(abs(a - b) for a, b in zip(y, p)) / len(y)
def rmse(y, p): return math.sqrt(sum((a - b) ** 2 for a, b in zip(y, p)) / len(y))


def auc(labels, scores):
    """Rank-based AUC, ties handled by average rank. Pure Python, no deps."""
    pairs = sorted(zip(scores, labels))
    ranks, i = [0.0] * len(pairs), 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        avg = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            ranks[k] = avg
        i = j + 1
    pos = sum(l for _, l in pairs)
    neg = len(pairs) - pos
    if pos == 0 or neg == 0:
        return float("nan")
    s = sum(r for r, (_, l) in zip(ranks, pairs) if l == 1)
    return (s - pos * (pos + 1) / 2.0) / (pos * neg)


def prec_rec(labels, pred_flags):
    tp = sum(1 for l, p in zip(labels, pred_flags) if l == 1 and p == 1)
    fp = sum(1 for l, p in zip(labels, pred_flags) if l == 0 and p == 1)
    fn = sum(1 for l, p in zip(labels, pred_flags) if l == 1 and p == 0)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return prec, rec, f1


# ------------------------------------------------------------------ main
def main():
    rows = load()
    train = [r for r in rows if r["year"] <= TRAIN_END]
    test = [r for r in rows if r["year"] > TRAIN_END]

    # fitted from TRAINING data only
    reg_mean = defaultdict(float)
    buckets = defaultdict(list)
    for r in train:
        buckets[r["region"]].append(r["cases"])
    for k, v in buckets.items():
        reg_mean[k] = sum(v) / len(v)

    clim = defaultdict(list)
    for r in train:
        clim[(r["region"], r["week"])].append(r["cases"])
    clim_mean = {k: sum(v) / len(v) for k, v in clim.items()}

    actual = {(r["region"], r["year"], r["week"]): r["cases"] for r in rows}

    # rainfall threshold picked on TRAINING data: the 80th percentile of 4-week rain
    tr_rain = sorted(r["rain_sum4w"] for r in train)
    thresh = tr_rain[int(0.80 * len(tr_rain))]

    preds = {}
    preds["zero"] = [0.0 for _ in test]
    preds["region_mean"] = [reg_mean[r["region"]] for r in test]
    preds["climatology"] = [clim_mean.get((r["region"], r["week"]),
                                          reg_mean[r["region"]]) for r in test]
    preds["seasonal_naive"] = [
        float(actual.get((r["region"], r["year"] - 1, r["week"]),
                         reg_mean[r["region"]])) for r in test]
    preds["rain_rule"] = [1.0 if r["rain_sum4w"] >= thresh else 0.0 for r in test]

    y = [r["cases"] for r in test]
    lab = [1 if c > 0 else 0 for c in y]
    base_rate = sum(lab) / len(lab)

    print(f"train {len(train)} rows (2003-{TRAIN_END})   "
          f"test {len(test)} rows ({TRAIN_END+1}-2026)")
    print(f"test weeks with at least one case: {sum(lab)}/{len(lab)} = {100*base_rate:.1f}%")
    print(f"rain_rule threshold (80th pct of 4-week rain in training): {thresh:.1f} mm\n")

    print(f"{'model':<17}{'MAE':>8}{'RMSE':>8}{'AUC':>8}{'prec':>8}{'rec':>8}{'F1':>8}")
    results = []
    for name, p in preds.items():
        flags = [1 if v > 0.5 else 0 for v in p] if name == "rain_rule" else \
                [1 if v >= 0.5 else 0 for v in p]
        pr, rc, f1 = prec_rec(lab, flags)
        a = auc(lab, p)
        print(f"{name:<17}{mae(y,p):>8.3f}{rmse(y,p):>8.3f}"
              f"{a:>8.3f}{pr:>8.3f}{rc:>8.3f}{f1:>8.3f}")
        results.append({"model": name, "mae": round(mae(y, p), 4),
                        "rmse": round(rmse(y, p), 4), "auc": round(a, 4),
                        "precision": round(pr, 4), "recall": round(rc, 4),
                        "f1": round(f1, 4)})

    acc_zero = sum(1 for l in lab if l == 0) / len(lab)
    print(f"\nAccuracy of the 'always predict zero' model: {100*acc_zero:.1f}%")
    print("That is why accuracy is not reported here. It rewards a model that")
    print("has learned nothing. AUC and precision/recall are the honest measures.")

    OUTD.mkdir(exist_ok=True)
    with (OUTD / "baseline_results.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(results[0]))
        w.writeheader(); w.writerows(results)
    with (OUTD / "baseline_predictions.csv").open("w", newline="") as fh:
        cols = ["region", "year", "week", "cases"] + list(preds)
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for i, r in enumerate(test):
            row = {k: r[k] for k in ("region", "year", "week", "cases")}
            for name in preds:
                row[name] = round(preds[name][i], 4)
            w.writerow(row)
    print(f"\nwrote outputs/baseline_results.csv and outputs/baseline_predictions.csv")


if __name__ == "__main__":
    main()
