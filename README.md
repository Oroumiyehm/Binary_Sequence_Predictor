# Binary_Sequence_Predictor
A binary sequence pattern recognition and forecasting engine. Scores recurring patterns by recency and consistency, and predicts the next value in any binary time series.

# Binary_Sequence_Predictor

A binary sequence pattern recognition and forecasting engine. It converts candle data into a binary sequence, finds recurring binary patterns, scores them by recency, repetition, and consistency, then predicts the next binary value using weighted pattern votes.

The current project is designed around daily BTC/USDT candle data, but the logic can be reused for any binary time series.

---

## Project Pipeline

The project runs in this order:

```bash
python "00 RGP_initiator.py"
python "01 RGP_pattern_recognition.py"
python "02 RGP_predict.py"
python "03 RGP_optimize.py"
```

Main data flow:

```text
btcusdt_1D.csv
        ↓
00 RGP_initiator.py
        ↓
btcusdt_1D_candles.csv
        ↓
01 RGP_pattern_recognition.py
        ↓
pattern_results.csv
        ↓
02 RGP_predict.py
        ↓
backtest_results.csv
        ↓
03 RGP_optimize.py
        ↓
optimization_results.csv
```

---

# Requirements

## Python Version

Recommended:

```text
Python 3.10+
```

## Python Packages

Install dependencies:

```bash
pip install pandas numpy optuna
```

Required packages by file:

| File | Required Packages |
|---|---|
| `00 RGP_initiator.py` | `pandas`, `numpy` |
| `01 RGP_pattern_recognition.py` | `pandas`, `numpy`, `math`, `datetime`, `collections` |
| `02 RGP_predict.py` | `pandas`, `numpy`, `sys` |
| `03 RGP_optimize.py` | `pandas`, `numpy`, `optuna`, `math`, `warnings`, `collections`, `sys` |

---

# Input Data Requirement

The initial input file is:

```text
btcusdt_1D.csv
```

It must contain at least these columns:

```text
timestamp
datetime
open
close
```

Example structure:

```csv
timestamp,datetime,open,close
1514764800000,2018-01-01,13715.65,13380.00
1514851200000,2018-01-02,13380.00,14720.00
```

The project converts each candle into a binary value:

| Candle Type | Binary Value |
|---|---|
| Green candle, close above open | `$1$` |
| Red candle, close below open | `$0$` |
| Flat candle, close equals open | Filled using nearby non-flat candles |

---

# File-by-File Explanation

---

# `00 RGP_initiator.py`

## Intention

This file prepares the raw OHLC candle data for binary sequence analysis.

It reads `btcusdt_1D.csv`, converts each candle into a binary value, assigns a row number, and saves the cleaned binary candle sequence to:

```text
btcusdt_1D_candles.csv
```

This file is the first step in the pipeline.

---

## Input

```text
btcusdt_1D.csv
```

Required columns:

```text
timestamp
datetime
open
close
```

---

## Output

```text
btcusdt_1D_candles.csv
```

Output columns:

```text
timestamp
datetime
candle
rownum
```

Where:

| Column | Meaning |
|---|---|
| `timestamp` | Original timestamp |
| `datetime` | Human-readable date/time |
| `candle` | Binary candle value, either `$0$` or `$1$` |
| `rownum` | Descending time index, where `$1$` means newest row |

---

## Main Steps

### Step `$1$`: Load Raw Data

```python
df = pd.read_csv('btcusdt_1D.csv')
```

The script reads the raw candle data.

---

### Step `$2$`: Sort Chronologically

```python
df = df.sort_values('timestamp', ascending=True).reset_index(drop=True)
```

The data is sorted from oldest to newest so that previous and next candles are handled correctly.

---

### Step `$3$`: Calculate Candle Movement

For every row:

$$
\Delta = close - open
$$

In code:

```python
delta = df['close'] - df['open']
```

---

### Step `$4$`: Convert Candle to Binary

The base rule is:

$$
candle =
\begin{cases}
1, & \Delta > 0 \\
0, & \Delta < 0 \\
NaN, & \Delta = 0
\end{cases}
$$

Meaning:

- If the candle closes higher than it opened, it becomes `$1$`.
- If the candle closes lower than it opened, it becomes `$0$`.
- If the candle is flat, it is temporarily marked as missing.

---

### Step `$5$`: Handle Flat Candles

Flat candles have:

$$
\Delta = 0
$$

Instead of ignoring them, the script estimates their direction using the nearest previous and next non-flat candle moves.

The previous non-flat move is:

$$
\Delta_{prev}
$$

The next non-flat move is:

$$
\Delta_{next}
$$

The average is:

$$
\Delta_{flatAvg} = \frac{\Delta_{prev} + \Delta_{next}}{2}
$$

Then:

$$
flatBinary =
\begin{cases}
1, & \Delta_{flatAvg} \ge 0 \\
0, & \Delta_{flatAvg} < 0
\end{cases}
$$

A tie is assigned to `$1$`.

---

### Step `$6$`: Sort Newest First and Add Row Number

```python
df = df.sort_values('timestamp', ascending=False).reset_index(drop=True)
df['rownum'] = range(1, len(df) + 1)
```

After this step:

- `rownum = 1` means the newest candle.
- Larger `rownum` values are older candles.

---

### Step `$7$`: Save Result

```python
result.to_csv('btcusdt_1D_candles.csv', index=False)
```

---

## Formula Summary

Raw candle movement:

$$
\Delta = close - open
$$

Binary candle conversion:

$$
candle =
\begin{cases}
1, & \Delta > 0 \\
0, & \Delta < 0
\end{cases}
$$

Flat candle average:

$$
\Delta_{flatAvg} = \frac{\Delta_{prev} + \Delta_{next}}{2}
$$

Flat candle binary value:

$$
flatBinary =
\begin{cases}
1, & \Delta_{flatAvg} \ge 0 \\
0, & \Delta_{flatAvg} < 0
\end{cases}
$$

---

# `01 RGP_pattern_recognition.py`

## Intention

This file scans the binary candle sequence and finds all recurring binary patterns between a minimum and maximum length.

For each pattern, it calculates:

- Total occurrence count
- Non-overlapping distinct run count
- First and latest appearance
- Recency score
- Count boost
- Consistency score
- Probability of the next value being `$0$`
- Probability of the next value being `$1$`
- Final confidence score

It saves the result to:

```text
pattern_results.csv
```

---

## Input

```text
btcusdt_1D_candles.csv
```

Required columns:

```text
datetime
candle
rownum
```

---

## Output

```text
pattern_results.csv
```

Important output columns:

| Column | Meaning |
|---|---|
| `pattern` | Binary pattern, for example `10110` |
| `length` | Pattern length |
| `count` | Total number of appearances |
| `distinct_runs` | Number of non-overlapping appearances |
| `first_appearance` | Oldest row number where pattern appears |
| `latest_appearance` | Newest row number where pattern appears |
| `recency_mean` | Recency-weighted average time location |
| `distinct_count_weight` | Saturated count boost |
| `consistency_weight` | Time-distribution consistency score |
| `range_coverage` | How widely the pattern spans the date range |
| `bin_coverage` | How many time bins contain the pattern |
| `recency_conf` | Final adjusted confidence score |
| `next_value` | Candidate next value, either `$0$` or `$1$` |
| `next_count` | Number of times that value followed the pattern |
| `next_prob` | Probability of that next value |
| `next_pct` | Probability as percent |

---

## Main Configuration

```python
MIN_LEN = 1
MAX_LEN = 30
MIN_COUNT = 1
RECENCY_POWER = 3.0
START_DATE = pd.Timestamp("2018-01-01")
END_DATE = pd.Timestamp.now()
DECAY_K = 0.4
COUNT_TAU = 5.0
CONSISTENCY_BINS = 10
ALPHA = 1.0
BETA = 1.0
```

Meaning:

| Parameter | Meaning |
|---|---|
| `MIN_LEN` | Minimum pattern length |
| `MAX_LEN` | Maximum pattern length |
| `MIN_COUNT` | Minimum occurrence count required |
| `RECENCY_POWER` | Controls how strongly recent appearances affect `recency_mean` |
| `COUNT_TAU` | Controls saturation speed of count boost |
| `CONSISTENCY_BINS` | Number of timeline bins used for consistency scoring |
| `ALPHA` | Exponent applied to count weight |
| `BETA` | Exponent applied to consistency weight |

---

## Main Steps

### Step `$1$`: Load Binary Candle Data

```python
df = pd.read_csv(CSV_IN)
df = df.sort_values('rownum')
df['datetime'] = pd.to_datetime(df['datetime'])
```

The script loads the binary candle sequence and sorts by `rownum`.

---

### Step `$2$`: Build Binary Sequence

```python
sequence = "".join(df['candle'].astype(str).tolist())
```

Example:

```text
101100101011...
```

Each candle becomes one character in the sequence.

---

### Step `$3$`: Scan All Patterns

For every pattern length from `MIN_LEN` to `MAX_LEN`, the script scans every possible substring.

For a pattern length `$L$`, each pattern is:

$$
pattern_i = sequence[i : i + L]
$$

The scan range is:

$$
i = 0, 1, 2, \dots, N - L
$$

Where `$N$` is the total sequence length.

---

### Step `$4$`: Count Pattern Occurrences

Each unique pattern is stored with all positions where it appears.

Example:

```text
Pattern: 101
Positions: 3, 18, 41, 105
```

The total count is:

$$
count = \text{number of all appearances}
$$

---

### Step `$5$`: Count Distinct Non-Overlapping Runs

Overlapping appearances are filtered to avoid over-counting nearly identical matches.

For pattern length `$L$`, an occurrence starting at position `$s$` is accepted only if:

$$
s \ge lastEnd
$$

Then:

$$
lastEnd = s + L
$$

The distinct run count is:

$$
distinctRuns = \text{number of accepted non-overlapping appearances}
$$

---

### Step `$6$`: Normalize Time

Each occurrence date is mapped into the range `$[0, 1]$`.

Formula:

$$
t = \frac{date - START\_DATE}{END\_DATE - START\_DATE}
$$

Then it is clamped:

$$
t =
\begin{cases}
0, & t < 0 \\
t, & 0 \le t \le 1 \\
1, & t > 1
\end{cases}
$$

Interpretation:

| Normalized Time | Meaning |
|---|---|
| `$0$` | Near `START_DATE` |
| `$1$` | Near current date |

---

### Step `$7$`: Calculate Recency Mean

Each distinct occurrence gets a weight:

$$
w_i = t_i^{p}
$$

Where:

- `$t_i$` is normalized time
- `$p$` is `RECENCY_POWER`

The recency-weighted mean is:

$$
recencyMean = \frac{\sum_i w_i t_i}{\sum_i w_i}
$$

Higher values mean the pattern appears more recently.

---

### Step `$8$`: Calculate Count Weight

The project uses a saturating count boost:

$$
countWeight(n) = 1 - e^{-n / \tau}
$$

Where:

- `$n$` is the number of distinct runs
- `$\tau$` is `COUNT_TAU`

This prevents very frequent patterns from dominating without limit.

As `$n$` increases, the weight approaches `$1$`.

---

### Step `$9$`: Calculate Consistency Weight

Consistency rewards patterns that appear across the full time range instead of only in one isolated period.

It combines:

### Range Coverage

$$
rangeCoverage = \max(t_i) - \min(t_i)
$$

### Bin Coverage

The timeline is divided into `$B$` bins.

$$
binCoverage = \frac{\text{number of bins touched}}{B}
$$

### Combined Consistency

$$
consistency = \frac{rangeCoverage + binCoverage}{2}
$$

If a pattern appears only once, consistency is:

$$
consistency = 0
$$

---

### Step `$10$`: Calculate Final Recency Confidence

The final pattern score is:

$$
recencyConf =
recencyMean
\times
countWeight^{\alpha}
\times
consistency^{\beta}
$$

Where:

- `$\alpha$` is `ALPHA`
- `$\beta$` is `BETA`

This means a strong pattern should be:

- Recent
- Repeated many times
- Distributed consistently across time

---

### Step `$11$`: Calculate Next-Value Probabilities

For every occurrence of a pattern, the script checks the value immediately after it.

For next value `$v$`, where `$v \in \{0, 1\}$`:

$$
P(v \mid pattern) = \frac{\text{count of times } v \text{ follows pattern}}{\text{total valid next observations}}
$$

The result is saved as:

```text
next_prob
next_pct
```

---

## Formula Summary

Pattern extraction:

$$
pattern_i = sequence[i : i + L]
$$

Normalized time:

$$
t = \frac{date - START\_DATE}{END\_DATE - START\_DATE}
$$

Recency weight:

$$
w_i = t_i^{RECENCY\_POWER}
$$

Recency mean:

$$
recencyMean = \frac{\sum_i w_i t_i}{\sum_i w_i}
$$

Count weight:

$$
countWeight(n) = 1 - e^{-n / COUNT\_TAU}
$$

Range coverage:

$$
rangeCoverage = \max(t_i) - \min(t_i)
$$

Bin coverage:

$$
binCoverage = \frac{\text{bins touched}}{CONSISTENCY\_BINS}
$$

Consistency:

$$
consistency = \frac{rangeCoverage + binCoverage}{2}
$$

Final confidence:

$$
recencyConf =
recencyMean
\times
countWeight^{ALPHA}
\times
consistency^{BETA}
$$

Next-value probability:

$$
P(v \mid pattern) =
\frac{\text{number of times } v \text{ follows pattern}}
{\text{number of valid next observations}}
$$

---

# `02 RGP_predict.py`

## Intention

This file uses the generated pattern database to make predictions and backtest them.

It reads:

```text
btcusdt_1D_candles.csv
pattern_results.csv
```

Then it walks through the candle history, finds matching patterns that end at the current history, votes for the next value, compares the prediction with the actual value, and saves the results to:

```text
backtest_results.csv
```

---

## Input

```text
btcusdt_1D_candles.csv
pattern_results.csv
```

---

## Output

```text
backtest_results.csv
```

Output columns:

| Column | Meaning |
|---|---|
| `date` | Date tested |
| `pred` | Predicted binary value |
| `actual` | Actual binary value |
| `correct` | `$1$` if prediction was correct, otherwise `$0$` |
| `matched` | Number of matching patterns |
| `s0` | Vote score for `$0$` |
| `s1` | Vote score for `$1$` |
| `weight` | Recency weight used in weighted accuracy |

---

## Main Steps

### Step `$1$`: Load Candles and Patterns

```python
candles = pd.read_csv(CSV_IN)
patterns = pd.read_csv(CSV_PAT)
```

The script removes patterns with invalid or zero confidence:

```python
patterns = patterns[patterns['next_value'].notna()]
patterns = patterns[patterns['recency_conf'] != 0]
```

---

### Step `$2$`: Group Pattern Rows

Each pattern has two possible next-value rows:

- one row for `$next\_value = 0$`
- one row for `$next\_value = 1$`

The script groups them by pattern:

```python
groups = {str(pat): grp for pat, grp in patterns.groupby('pattern')}
```

---

### Step `$3$`: Build History at Each Position

For each test position `$pos$`, the history is:

$$
history = candle_0 candle_1 \dots candle_{pos-1}
$$

The actual value is:

$$
actual = candle_{pos}
$$

---

### Step `$4$`: Match Patterns Against History

A pattern matches if the current history ends with that pattern:

$$
history.endswith(pattern) = True
$$

This means the most recent known binary sequence matches a known historical pattern.

---

### Step `$5$`: Vote for the Next Value

For each matching pattern, the script adds weighted votes to `$0$` and `$1$`.

For candidate value `$v$`:

$$
score_v =
\sum_{p \in M}
recencyConf(p) \times P(v \mid p)
$$

Where:

- `$M$` is the set of matched patterns
- `$recencyConf(p)$` is the final confidence of pattern `$p$`
- `$P(v \mid p)$` is the historical probability that `$v$` follows pattern `$p$`

In code:

```python
votes[int(row['next_value'])] += row['recency_conf'] * row['next_prob']
```

---

### Step `$6$`: Make Prediction

The prediction rule is:

$$
prediction =
\begin{cases}
1, & score_1 \ge score_0 \\
0, & score_1 < score_0
\end{cases}
$$

Ties are assigned to `$1$`.

---

### Step `$7$`: Backtest Accuracy

The script compares prediction with actual value:

$$
correct =
\begin{cases}
1, & prediction = actual \\
0, & prediction \ne actual
\end{cases}
$$

Accuracy is:

$$
accuracy = \frac{correctPredictions}{totalPredictions}
$$

---

### Step `$8$`: Recency-Weighted Accuracy

The backtest results are sorted by date from oldest to newest.

For result index `$i$` out of `$n$` total rows, the weight is:

$$
weight_i = \frac{i + 1}{n}
$$

So newer results receive larger weights.

Weighted accuracy is:

$$
weightedAccuracy =
\frac{\sum_i correct_i \times weight_i}
{\sum_i weight_i}
$$

---

### Step `$9$`: Classification Metrics

The script also calculates:

### Precision

$$
precision =
\frac{TP}{TP + FP}
$$

### Recall

$$
recall =
\frac{TP}{TP + FN}
$$

### F1 Score

$$
F1 =
\frac{2 \times precision \times recall}
{precision + recall}
$$

Where:

| Metric | Meaning |
|---|---|
| `TP` | Predicted `$1$`, actual `$1$` |
| `TN` | Predicted `$0$`, actual `$0$` |
| `FP` | Predicted `$1$`, actual `$0$` |
| `FN` | Predicted `$0$`, actual `$1$` |

---

## Optional Date Range Backtest

You can backtest only a specific date range:

```bash
python "02 RGP_predict.py" 2022-01-01 2024-01-01
```

Arguments:

```text
start_date
end_date
```

---

## Formula Summary

Vote score:

$$
score_v =
\sum_{p \in M}
recencyConf(p) \times P(v \mid p)
$$

Prediction:

$$
prediction =
\begin{cases}
1, & score_1 \ge score_0 \\
0, & score_1 < score_0
\end{cases}
$$

Accuracy:

$$
accuracy = \frac{correct}{total}
$$

Recency weight:

$$
weight_i = \frac{i + 1}{n}
$$

Weighted accuracy:

$$
weightedAccuracy =
\frac{\sum_i correct_i \times weight_i}
{\sum_i weight_i}
$$

Precision:

$$
precision =
\frac{TP}{TP + FP}
$$

Recall:

$$
recall =
\frac{TP}{TP + FN}
$$

F1:

$$
F1 =
\frac{2 \times precision \times recall}
{precision + recall}
$$

---

# `03 RGP_optimize.py`

## Intention

This file performs Bayesian hyperparameter optimization using Optuna.

It searches for the best configuration of the pattern recognition and prediction system by repeatedly:

1. Sampling a set of parameters
2. Running pattern recognition in memory
3. Running a backtest in memory
4. Measuring recency-weighted accuracy
5. Saving the best parameter set

It outputs:

```text
optimization_results.csv
```

---

## Input

```text
btcusdt_1D_candles.csv
```

This file must already be generated by:

```bash
python "00 RGP_initiator.py"
```

---

## Output

```text
optimization_results.csv
```

This file contains all Optuna trial results.

The script also prints the best trial to the terminal.

---

## Run Command

Default run:

```bash
python "03 RGP_optimize.py"
```

Run with a custom number of trials:

```bash
python "03 RGP_optimize.py" 500
```

Where `$500$` is the number of optimization trials.

---

## Main Steps

### Step `$1$`: Define Search Space

The script uses Optuna to search across these parameters:

| Parameter | Type | Search Range |
|---|---:|---:|
| `MIN_LEN` | integer | `$1$` to `$5$` |
| `MAX_LEN` | integer | `$6$` to `$35$` |
| `MIN_COUNT` | integer | `$1$` to `$10$` |
| `RECENCY_POWER` | float | `$0.5$` to `$6.0$` |
| `DECAY_K` | float | `$0.05$` to `$2.0$` |
| `COUNT_TAU` | float | `$1.0$` to `$20.0$` |
| `CONSISTENCY_BINS` | integer | `$4$` to `$20$` |
| `ALPHA` | float | `$0.1$` to `$3.0$` |
| `BETA` | float | `$0.1$` to `$3.0$` |
| `RECENCY_SHARPNESS` | float | `$0.5$` to `$5.0$` |

---

### Step `$2$`: Run Pattern Recognition In Memory

Instead of writing `pattern_results.csv` every trial, the optimizer runs pattern recognition internally and returns a DataFrame.

It uses the same core formulas as `01 RGP_pattern_recognition.py`.

---

### Step `$3$`: Run Backtest In Memory

The optimizer then runs a simplified version of the backtest from `02 RGP_predict.py`.

For each position, it:

1. Builds the known history
2. Finds matching patterns
3. Computes vote scores
4. Predicts `$0$` or `$1$`
5. Checks if the prediction was correct

---

### Step `$4$`: Calculate Objective Score

The optimization target is recency-weighted accuracy.

Unlike `02 RGP_predict.py`, this file adds a sharpness parameter.

The weight is:

$$
weight_i =
\left(
\frac{i + 1}{n}
\right)^{\gamma}
$$

Where:

- `$\gamma$` is `RECENCY_SHARPNESS`
- `$i$` is the result index after sorting by date
- `$n$` is total tested rows

The objective score is:

$$
score =
\frac{\sum_i correct_i \times weight_i}
{\sum_i weight_i}
$$

Optuna tries to maximize this value.

---

### Step `$5$`: Bayesian Optimization with Optuna

The script creates a study:

```python
study = optuna.create_study(
    direction="maximize",
    sampler=optuna.samplers.TPESampler(seed=42)
)
```

It uses Optuna’s TPE sampler to search for better parameter combinations.

---

### Step `$6$`: Save Trial Results

After all trials, it saves:

```text
optimization_results.csv
```

And prints:

```text
Best Weighted Accuracy
Best parameters
```

---

## Formula Summary

Count weight:

$$
countWeight(n) = 1 - e^{-n / COUNT\_TAU}
$$

Recency mean:

$$
recencyMean = \frac{\sum_i t_i^{RECENCY\_POWER} t_i}{\sum_i t_i^{RECENCY\_POWER}}
$$

Consistency:

$$
consistency =
\frac{rangeCoverage + binCoverage}{2}
$$

Final pattern confidence:

$$
recencyConf =
recencyMean
\times
countWeight^{ALPHA}
\times
consistency^{BETA}
$$

Vote score:

$$
score_v =
\sum_{p \in M}
recencyConf(p) \times P(v \mid p)
$$

Prediction:

$$
prediction =
\begin{cases}
1, & score_1 \ge score_0 \\
0, & score_1 < score_0
\end{cases}
$$

Optimization weight:

$$
weight_i =
\left(
\frac{i + 1}{n}
\right)^{RECENCY\_SHARPNESS}
$$

Optimization objective:

$$
objective =
\frac{\sum_i correct_i \times weight_i}
{\sum_i weight_i}
$$

---

# Generated Files

| File | Created By | Purpose |
|---|---|---|
| `btcusdt_1D_candles.csv` | `00 RGP_initiator.py` | Binary candle sequence |
| `pattern_results.csv` | `01 RGP_pattern_recognition.py` | Pattern statistics and probabilities |
| `backtest_results.csv` | `02 RGP_predict.py` | Per-date prediction results |
| `optimization_results.csv` | `03 RGP_optimize.py` | Optuna trial results |

---

# Important Implementation Note

The project relies heavily on sequence ordering.

`00 RGP_initiator.py` creates:

$$
rownum = 1
$$

for the newest candle.

Then:

- `01 RGP_pattern_recognition.py` sorts by `rownum` ascending.
- `02 RGP_predict.py` sorts by `rownum` descending.
- `03 RGP_optimize.py` follows the same internal behavior.

If you adapt this project for another dataset or production forecasting, make sure the training sequence direction and prediction sequence direction match your intended forecasting direction.

---

# Recommended Usage

## Full Basic Run

```bash
python "00 RGP_initiator.py"
python "01 RGP_pattern_recognition.py"
python "02 RGP_predict.py"
```

## Run Backtest for a Date Range

```bash
python "02 RGP_predict.py" 2021-01-01 2025-01-01
```

## Run Optimization

```bash
python "03 RGP_optimize.py" 1000
```

---

# Project Summary

This project transforms a time series into a binary sequence and searches for repeating historical patterns. Each pattern is scored using:

1. Recency
2. Distinct occurrence count
3. Time-distribution consistency
4. Historical next-value probability

Prediction is made by weighted voting among all matching patterns.

The core idea is:

$$
\text{Better patterns are recent, repeated, consistent, and historically predictive.}
$$
