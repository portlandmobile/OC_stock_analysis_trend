import pandas as pd
import numpy as np

try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False

def calculate_williams_r(df, period=21):
    if df is None or len(df) < period:
        return pd.Series([np.nan] * len(df)) if df is not None else None

    high = df['High']
    low = df['Low']
    close = df['Close']

    if HAS_TALIB:
        try:
            return pd.Series(talib.WILLR(high, low, close, timeperiod=period), index=df.index)
        except Exception:
            pass

    # Fallback
    highest_high = high.rolling(window=period).max()
    lowest_low = low.rolling(window=period).min()
    williams_r = ((highest_high - close) / (highest_high - lowest_low)) * -100
    return williams_r

def calculate_ema(series, period=13):
    if series is None or len(series) < period:
        return pd.Series([np.nan] * len(series)) if series is not None else None

    if HAS_TALIB:
        try:
            return pd.Series(talib.EMA(series.values, timeperiod=period), index=series.index)
        except Exception:
            pass

    # Fallback
    return series.ewm(span=period, adjust=False).mean()

def classify_intensity(williams_r_value):
    if williams_r_value is None or np.isnan(williams_r_value):
        return "UNKNOWN"
    
    if williams_r_value < -95:
        return "EXTREME"
    elif -95 <= williams_r_value < -90:
        return "VERY_STRONG"
    elif -90 <= williams_r_value < -85:
        return "STRONG"
    elif -85 <= williams_r_value < -80:
        return "MODERATE"
    else:
        return "NEUTRAL"
