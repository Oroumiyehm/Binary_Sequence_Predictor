import pandas as pd
import numpy as np
import sys

CSV_IN  = 'btcusdt_1D_candles.csv'
CSV_PAT = 'pattern_results.csv'

def load_data():
    candles = pd.read_csv(CSV_IN)
    candles['datetime'] = pd.to_datetime(candles['datetime'])
    candles = candles.sort_values('rownum', ascending=False).reset_index(drop=True)

    patterns = pd.read_csv(CSV_PAT)
    patterns = patterns[patterns['next_value'].notna()]
    patterns = patterns[patterns['recency_conf'] != 0]
    groups = {str(pat): grp for pat, grp in patterns.groupby('pattern')}
    return candles, groups

def predict_at(pos, candles, groups):
    history = ''.join(candles['candle'].iloc[:pos].astype(str))
    actual  = int(candles.loc[pos, 'candle'])

    votes = {0: 0.0, 1: 0.0}
    matched = 0
    for pat, grp in groups.items():
        if history.endswith(pat):
            matched += 1
            for _, row in grp.iterrows():
                votes[int(row['next_value'])] += row['recency_conf'] * row['next_prob']

    if votes[0] == 0 and votes[1] == 0:
        return None, actual, votes, matched

    prediction = 1 if votes[1] >= votes[0] else 0
    return prediction, actual, votes, matched

def backtest(start=None, end=None, min_history=1):
    candles, groups = load_data()

    if start: start = pd.Timestamp(start)
    if end:   end   = pd.Timestamp(end)

    tp = tn = fp = fn = 0
    correct = total = skipped = 0
    rows = []

    for pos in range(min_history, len(candles)):
        dt = candles.loc[pos, 'datetime']
        if start and dt < start: continue
        if end   and dt > end:   continue

        pred, actual, votes, matched = predict_at(pos, candles, groups)
        if pred is None:
            skipped += 1
            continue

        total += 1
        ok = int(pred == actual)
        correct += ok

        if   pred == 1 and actual == 1: tp += 1
        elif pred == 0 and actual == 0: tn += 1
        elif pred == 1 and actual == 0: fp += 1
        elif pred == 0 and actual == 1: fn += 1

        rows.append({'date': dt, 'pred': pred, 'actual': actual,
                     'correct': ok, 'matched': matched,
                     's0': round(votes[0], 4), 's1': round(votes[1], 4)})

    # Recency-weighted accuracy: weight = rank / n (oldest=1/n, newest=1.0)
    detail = pd.DataFrame(rows)
    if not detail.empty:
        detail = detail.sort_values('date').reset_index(drop=True)
        n = len(detail)
        detail['weight'] = (detail.index + 1) / n
        weighted_acc = (detail['correct'] * detail['weight']).sum() / detail['weight'].sum()
    else:
        weighted_acc = 0.0

    accuracy  = correct / total if total else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall    = tp / (tp + fn) if (tp + fn) else 0.0
    f1        = (2*precision*recall/(precision+recall)) if (precision+recall) else 0.0

    print(f"Tested:            {total}")
    print(f"Skipped:           {skipped}  (no matching pattern)")
    print(f"Correct:           {correct}")
    print(f"Accuracy:          {accuracy:.4f}  ({accuracy*100:.2f}%)")
    print(f"Weighted Accuracy: {weighted_acc:.4f}  ({weighted_acc*100:.2f}%)  ← recency-weighted")
    print(f"Precision:         {precision:.4f}  (class=1)")
    print(f"Recall:            {recall:.4f}  (class=1)")
    print(f"F1:                {f1:.4f}")
    print(f"Confusion:         TP={tp} TN={tn} FP={fp} FN={fn}")

    detail['date'] = detail['date'].dt.date
    detail.to_csv('backtest_results.csv', index=False)
    print("\nPer-date results written to backtest_results.csv")
    return detail

if __name__ == '__main__':
    start = sys.argv[1] if len(sys.argv) > 1 else None
    end   = sys.argv[2] if len(sys.argv) > 2 else None
    backtest(start, end)
