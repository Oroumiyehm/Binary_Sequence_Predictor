"""
RGP_optimize.py  –  Bayesian hyperparameter search via Optuna
Optimizes parameters in RGP_pattern_recognition.py to maximize weighted backtest accuracy.
Usage:  python RGP_optimize.py [n_trials]   (default: 1000)
"""

import sys
import math
import warnings
import numpy as np
import pandas as pd
import optuna
from collections import defaultdict

optuna.logging.set_verbosity(optuna.logging.WARNING)
warnings.filterwarnings("ignore")

# ── Fixed paths ───────────────────────────────────────────────────────────────
CSV_CANDLES = "btcusdt_1D_candles.csv"

# ── Inline pattern recognition ────────────────────────────────────────────────

def run_pattern_recognition(cfg):
    MIN_LEN          = cfg["MIN_LEN"]
    MAX_LEN          = cfg["MAX_LEN"]
    MIN_COUNT        = cfg["MIN_COUNT"]
    RECENCY_POWER    = cfg["RECENCY_POWER"]
    DECAY_K          = cfg["DECAY_K"]
    COUNT_TAU        = cfg["COUNT_TAU"]
    CONSISTENCY_BINS = cfg["CONSISTENCY_BINS"]
    ALPHA            = cfg["ALPHA"]
    BETA             = cfg["BETA"]

    START_DATE = pd.Timestamp("2018-01-01")
    END_DATE   = pd.Timestamp.now()

    def norm_time(dt):
        span = (END_DATE - START_DATE).total_seconds()
        t = (pd.Timestamp(dt) - START_DATE).total_seconds() / span
        return min(1.0, max(0.0, t))

    def recency_weight(t):
        return math.exp(DECAY_K * (t - 1.0))

    def count_weight(n):
        return 1.0 - math.exp(-n / COUNT_TAU) if n > 0 else 0.0

    def consistency_weight(times):
        if len(times) < 2:
            return 0.0, 0.0, 0.0
        tvals = sorted(times)
        range_cov = max(tvals) - min(tvals)
        hit_bins = set(min(int(t * CONSISTENCY_BINS), CONSISTENCY_BINS - 1) for t in tvals)
        bin_cov = len(hit_bins) / CONSISTENCY_BINS
        return (range_cov + bin_cov) / 2.0, range_cov, bin_cov

    df = pd.read_csv(CSV_CANDLES)
    df = df.sort_values("rownum")
    df["datetime"] = pd.to_datetime(df["datetime"])
    sequence = "".join(df["candle"].astype(str).tolist())
    dates    = df["datetime"].tolist()

    pattern_data = defaultdict(list)
    for length in range(MIN_LEN, MAX_LEN + 1):
        for i in range(len(sequence) - length + 1):
            pattern_data[sequence[i:i+length]].append(i)

    results = []
    for sub, idxs in pattern_data.items():
        L = len(sub)
        if len(idxs) < MIN_COUNT:
            continue

        sorted_idxs = sorted(idxs)
        distinct_idxs, last_end = [], -1
        for s in sorted_idxs:
            if s >= last_end:
                distinct_idxs.append(s)
                last_end = s + L

        distinct_count = len(distinct_idxs)
        distinct_tvals = [norm_time(dates[i]) for i in distinct_idxs]

        tvals_arr = np.array(distinct_tvals)
        weights   = tvals_arr ** RECENCY_POWER
        denom     = weights.sum()
        recency_mean = (weights * tvals_arr).sum() / denom if denom > 0 else 0.0

        dcw         = count_weight(distinct_count)
        consistency, range_cov, bin_cov = consistency_weight(distinct_tvals)
        recency_conf = recency_mean * (dcw ** ALPHA) * (consistency ** BETA)

        next_vals = [int(sequence[i+L]) for i in idxs if i+L < len(sequence)]
        n = len(next_vals)

        for val in [0, 1]:
            nc = next_vals.count(val)
            results.append({
                "pattern": sub, "recency_conf": round(recency_conf, 6),
                "next_value": val, "next_prob": round(nc / n, 4) if n else 0,
            })

    return pd.DataFrame(results)


# ── Inline backtest ───────────────────────────────────────────────────────────

def run_backtest(patterns_df, candles_df, recency_sharpness):
    patterns_df = patterns_df[patterns_df["next_value"].notna()]
    patterns_df = patterns_df[patterns_df["recency_conf"] != 0]
    groups = {str(p): g for p, g in patterns_df.groupby("pattern")}

    candles = candles_df.sort_values("rownum", ascending=False).reset_index(drop=True)
    sequence_full = candles["candle"].astype(str).tolist()

    rows = []
    for pos in range(1, len(candles)):
        history = "".join(sequence_full[:pos])
        actual  = int(candles.loc[pos, "candle"])
        dt      = candles.loc[pos, "datetime"]

        votes = {0: 0.0, 1: 0.0}
        for pat, grp in groups.items():
            if history.endswith(pat):
                for _, row in grp.iterrows():
                    votes[int(row["next_value"])] += row["recency_conf"] * row["next_prob"]

        if votes[0] == 0 and votes[1] == 0:
            continue

        pred = 1 if votes[1] >= votes[0] else 0
        rows.append({"date": dt, "correct": int(pred == actual)})

    if not rows:
        return 0.0

    detail = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    n = len(detail)
    detail["weight"] = ((detail.index + 1) / n) ** recency_sharpness
    return (detail["correct"] * detail["weight"]).sum() / detail["weight"].sum()


# ── Optuna objective ──────────────────────────────────────────────────────────

_candles_df = None

def objective(trial):
    PARAM_SPACE = {
        "MIN_LEN":            dict(type="int",   low=1,    high=5,    step=1),
        "MAX_LEN":            dict(type="int",   low=6,    high=35,   step=1),
        "MIN_COUNT":          dict(type="int",   low=1,    high=10,   step=1),
        "RECENCY_POWER":      dict(type="float", low=0.5,  high=6.0,  step=None),
        "DECAY_K":            dict(type="float", low=0.05, high=2.0,  step=None),
        "COUNT_TAU":          dict(type="float", low=1.0,  high=20.0, step=None),
        "CONSISTENCY_BINS":   dict(type="int",   low=4,    high=20,   step=1),
        "ALPHA":              dict(type="float", low=0.1,  high=3.0,  step=None),
        "BETA":               dict(type="float", low=0.1,  high=3.0,  step=None),
        "RECENCY_SHARPNESS":  dict(type="float", low=0.5,  high=5.0,  step=None),
    }

    cfg = {}
    for name, s in PARAM_SPACE.items():
        if s["type"] == "int":
            cfg[name] = trial.suggest_int(name, s["low"], s["high"], step=s["step"])
        else:
            cfg[name] = trial.suggest_float(name, s["low"], s["high"], step=s["step"])

    if cfg["MIN_LEN"] >= cfg["MAX_LEN"]:
        return 0.0

    try:
        patterns_df = run_pattern_recognition(cfg)
        if patterns_df.empty:
            return 0.0
        return run_backtest(patterns_df, _candles_df, cfg["RECENCY_SHARPNESS"])
    except Exception:
        return 0.0


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    n_trials = int(sys.argv[1]) if len(sys.argv) > 1 else 1000

    _candles_df = pd.read_csv(CSV_CANDLES)
    _candles_df["datetime"] = pd.to_datetime(_candles_df["datetime"])

    print(f"Starting Bayesian optimization — {n_trials} trials")

    study = optuna.create_study(direction="maximize",
                                sampler=optuna.samplers.TPESampler(seed=42))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

    best = study.best_trial
    print(f"\n{'='*50}")
    print(f"Best Weighted Accuracy: {best.value:.4f}  ({best.value*100:.2f}%)")
    print(f"{'='*50}")
    print("Best parameters:")
    for k, v in best.params.items():
        print(f"  {k:20s} = {v}")

    df_trials = study.trials_dataframe()
    df_trials.to_csv("optimization_results.csv", index=False)
    print("\nAll trial results saved to optimization_results.csv")
