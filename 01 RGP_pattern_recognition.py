import pandas as pd
import numpy as np
import math
from datetime import datetime
from collections import defaultdict

# --- Configuration ---
CSV_IN = 'btcusdt_1D_candles.csv'
CSV_OUT = 'pattern_results.csv'
MIN_LEN = 1
MAX_LEN = 30
MIN_COUNT = 1
SMOOTH = 10             # kept for future ranking use; not used directly here

RECENCY_POWER = 3.0  # 0 = plain mean, 1 = current behavior, 2+ = stronger recency bias

# --- Date-based recency factor ---
START_DATE = pd.Timestamp("2018-01-01")
END_DATE = pd.Timestamp.now()
DECAY_K = 0.4           # higher = stronger recent-date bias

# --- Distinct-run count boost ---
COUNT_TAU = 5.0         # saturation speed for distinct run count boost

# --- Consistency / time-distribution settings ---
CONSISTENCY_BINS = 10   # number of timeline bins
ALPHA = 1.0             # exponent for count weight
BETA = 1.0              # exponent for consistency weight


def norm_time(dt):
    """Map a date into [0,1]: START_DATE -> 0, END_DATE -> 1 (clamped)."""
    span = (END_DATE - START_DATE).total_seconds()
    t = (pd.Timestamp(dt) - START_DATE).total_seconds() / span
    return min(1.0, max(0.0, t))


def recency_weight(t, k=DECAY_K):
    """Asymmetric exponential: today -> 1, older dates decay convexly."""
    return math.exp(k * (t - 1.0))


def count_weight(n, tau=COUNT_TAU):
    """Saturating boost for higher distinct-run counts, in [0,1)."""
    return 1.0 - math.exp(-n / tau) if n > 0 else 0.0


def consistency_weight(times, bins=CONSISTENCY_BINS):
    """
    Reward patterns that are distributed across the full date range.
    Combines:
      1) normalized range coverage
      2) fraction of timeline bins touched
    """
    if not times:
        return 0.0, 0.0, 0.0

    if len(times) == 1:
        return 0.0, 0.0, 0.0

    tvals = sorted(times)

    # 1. Range coverage: how much of [0,1] the pattern spans
    range_coverage = max(tvals) - min(tvals)

    # 2. Bin coverage: how many timeline bins contain at least one occurrence
    hit_bins = set()
    for t in tvals:
        b = min(int(t * bins), bins - 1)
        hit_bins.add(b)

    bin_coverage = len(hit_bins) / bins

    # Combined consistency
    combined = (range_coverage + bin_coverage) / 2.0
    return combined, range_coverage, bin_coverage


def safe_to_csv(df, path):
    try:
        df.to_csv(path, index=False)
        print(f"Successfully saved to {path}")
        return path
    except PermissionError:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_path = path.replace(".csv", f"_{timestamp}.csv")
        df.to_csv(new_path, index=False)
        print(f"Warning: {path} was locked. Saved to {new_path} instead.")
        return new_path


# 1. Load Data
df = pd.read_csv(CSV_IN)
df = df.sort_values('rownum')   # ascending: rownum 1 (newest) -> oldest
df['datetime'] = pd.to_datetime(df['datetime'])

sequence = "".join(df['candle'].astype(str).tolist())
rownums = df['rownum'].tolist()
dates = df['datetime'].tolist()

pattern_data = defaultdict(list)

# 2. Scan Patterns
for length in range(MIN_LEN, MAX_LEN + 1):
    for i in range(len(sequence) - length + 1):
        sub = sequence[i:i + length]
        pattern_data[sub].append(i)

results = []

for sub, idxs in pattern_data.items():
    L = len(sub)
    count = len(idxs)
    if count < MIN_COUNT:
        continue

    # Distinct (non-overlapping) runs
    sorted_idxs = sorted(idxs)
    distinct_idxs = []
    last_end = -1
    for start_idx in sorted_idxs:
        if start_idx >= last_end:
            distinct_idxs.append(start_idx)
            last_end = start_idx + L

    distinct_count = len(distinct_idxs)
    distinct_dates = [dates[i] for i in distinct_idxs]
    distinct_tvals = [norm_time(d) for d in distinct_dates]

    # Appearance bounds
    occurrence_rownums = [rownums[i] for i in idxs]
    first_appearance = max(occurrence_rownums)   # oldest
    latest_appearance = min(occurrence_rownums)  # newest

    # 1. Recency mean
    tvals_arr = np.array(distinct_tvals)
    weights = tvals_arr ** RECENCY_POWER
    denom = weights.sum()
    recency_mean = (weights * tvals_arr).sum() / denom if denom > 0 else 0.0


    # 2. Count boost
    distinct_count_weight = count_weight(distinct_count)

    # 3. Consistency boost across full time range
    consistency, range_coverage, bin_coverage = consistency_weight(distinct_tvals)

    # Final adjusted recency confidence
    recency_conf = (
        recency_mean *
        (distinct_count_weight ** ALPHA) *
        (consistency ** BETA)
    )

    # Next outcome stats
    next_vals = []
    for i_start in idxs:
        next_idx = i_start + L
        if next_idx < len(sequence):
            next_vals.append(int(sequence[next_idx]))

    n = len(next_vals)

    for val in [0, 1]:
        next_count = next_vals.count(val)
        next_prob = round(next_count / n, 4) if n else 0

        results.append({
            "pattern": sub,
            "length": L,
            "count": count,
            "distinct_runs": distinct_count,
            "first_appearance": first_appearance,
            "latest_appearance": latest_appearance,
            "recency_mean": round(recency_mean, 6),
            "distinct_count_weight": round(distinct_count_weight, 6),
            "consistency_weight": round(consistency, 6),
            "range_coverage": round(range_coverage, 6),
            "bin_coverage": round(bin_coverage, 6),
            "recency_conf": round(recency_conf, 6),
            "next_value": val,
            "next_count": next_count,
            "next_prob": next_prob,
            "next_pct": round(next_prob * 100, 2),
        })

# 3. Save
results_df = pd.DataFrame(results)
if not results_df.empty:
    results_df = results_df.sort_values(
        ['length', 'pattern'],
        ascending=[True, True]
    )
    safe_to_csv(results_df, CSV_OUT)
