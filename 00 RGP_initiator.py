import pandas as pd
import numpy as np

# Load the data
df = pd.read_csv('btcusdt_1D.csv')

# Sort chronologically so "previous" and "next" are correct
df = df.sort_values('timestamp', ascending=True).reset_index(drop=True)

# Raw move per candle
delta = df['close'] - df['open']

# Base candle: 1 = green, 0 = red, NaN = flat (to be filled)
df['candle'] = np.where(delta > 0, 1.0,
                np.where(delta < 0, 0.0, np.nan))

# For flats, use the actual delta of nearest non-flat neighbors
real_delta = delta.where(delta != 0)   # flats become NaN
prev_delta = real_delta.ffill()        # e.g. -300 from previous candle
next_delta = real_delta.bfill()        # e.g. +500 from next candle
flat_avg = (prev_delta + next_delta) / 2   # (-300 + 500)/2 = 200

# Collapse flats to binary: positive avg -> 1, negative -> 0 (tie -> 1)
flat_binary = (flat_avg >= 0).astype(float)

# Fill only the flat rows
df['candle'] = df['candle'].fillna(flat_binary)

# Sort by timeframe descending and add descending row number
df = df.sort_values('timestamp', ascending=False).reset_index(drop=True)
df['rownum'] = range(1, len(df) + 1)

df['candle'] = df['candle'].astype(int)
result = df[['timestamp', 'datetime', 'candle', 'rownum']]
print(result.head(10))
result.to_csv('btcusdt_1D_candles.csv', index=False)
