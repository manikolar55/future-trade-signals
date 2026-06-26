import pandas as pd
import numpy as np


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(com=period - 1, adjust=True, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(com=period - 1, adjust=True, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _macd_cross(macd_line: pd.Series, signal_line: pd.Series, lookback: int = 2) -> str:
    for i in range(-lookback, 0):
        prev = macd_line.iloc[i - 1] - signal_line.iloc[i - 1]
        curr = macd_line.iloc[i] - signal_line.iloc[i]
        if prev < 0 and curr >= 0:
            return 'BULL_CROSS'
        if prev > 0 and curr <= 0:
            return 'BEAR_CROSS'
    return 'BULL' if macd_line.iloc[-1] > signal_line.iloc[-1] else 'BEAR'


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, prev_close = df['high'], df['low'], df['close'].shift()
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, adjust=True, min_periods=period).mean()


def _adx(df: pd.DataFrame, period: int = 14):
    high, low, close = df['high'], df['low'], df['close']
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)
    prev_close = close.shift()
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    smooth_tr = tr.ewm(com=period - 1, adjust=True, min_periods=period).mean().replace(0, np.nan)
    plus_di  = 100 * plus_dm.ewm(com=period - 1, adjust=True, min_periods=period).mean() / smooth_tr
    minus_di = 100 * minus_dm.ewm(com=period - 1, adjust=True, min_periods=period).mean() / smooth_tr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(com=period - 1, adjust=True, min_periods=period).mean()
    return adx, plus_di, minus_di


def _find_pivots(df: pd.DataFrame, window: int = 5):
    supports, resistances = [], []
    for i in range(window, len(df) - window):
        slice_h = df['high'].iloc[i - window: i + window + 1]
        slice_l = df['low'].iloc[i - window: i + window + 1]
        if df['high'].iloc[i] == slice_h.max():
            resistances.append(float(df['high'].iloc[i]))
        if df['low'].iloc[i] == slice_l.min():
            supports.append(float(df['low'].iloc[i]))
    return supports[-6:], resistances[-6:]


def _market_structure(df: pd.DataFrame, swing_window: int = 3, lookback: int = 40) -> str:
    recent = df.tail(lookback)
    n = len(recent)
    swing_highs, swing_lows = [], []

    for i in range(swing_window, n - swing_window):
        h = recent['high'].iloc[i]
        l = recent['low'].iloc[i]
        if h == recent['high'].iloc[i - swing_window: i + swing_window + 1].max():
            swing_highs.append(h)
        if l == recent['low'].iloc[i - swing_window: i + swing_window + 1].min():
            swing_lows.append(l)

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return 'SIDEWAYS'

    hh = swing_highs[-1] > swing_highs[-2]
    hl = swing_lows[-1] > swing_lows[-2]
    lh = swing_highs[-1] < swing_highs[-2]
    ll = swing_lows[-1] < swing_lows[-2]

    if hh and hl:
        return 'BULLISH'
    if lh and ll:
        return 'BEARISH'
    return 'SIDEWAYS'


def analyze(df: pd.DataFrame) -> dict:
    df = df.copy()
    df['ema9']  = _ema(df['close'], 9)
    df['ema21'] = _ema(df['close'], 21)
    df['ema50'] = _ema(df['close'], 50)
    df['rsi']   = _rsi(df['close'])
    df['atr']   = _atr(df)

    adx_series, plus_di_series, minus_di_series = _adx(df)
    df['adx']      = adx_series
    df['plus_di']  = plus_di_series
    df['minus_di'] = minus_di_series

    macd_line, signal_line, histogram = _macd(df['close'])
    df['macd']      = macd_line
    df['macd_sig']  = signal_line
    df['macd_hist'] = histogram

    last     = df.iloc[-1]
    prev     = df.iloc[-2]
    vol_avg  = df['volume'].rolling(20).mean().iloc[-1]

    # EMA gap: is EMA9-EMA21 widening (trend accelerating) or narrowing (about to reverse)?
    gap_now  = float(last['ema9']) - float(last['ema21'])
    gap_prev = float(prev['ema9']) - float(prev['ema21'])
    ema_gap_expanding = abs(gap_now) > abs(gap_prev)

    supports, resistances = _find_pivots(df)
    price = float(last['close'])

    # Candle body size relative to ATR — filters indecisive candles
    body_size = abs(float(last['close']) - float(last['open']))
    atr_val   = float(last['atr']) if not np.isnan(last['atr']) else 1.0
    is_strong_candle = body_size > (atr_val * 0.3)

    nearest_support    = max((s for s in supports    if s < price), default=None)
    nearest_resistance = min((r for r in resistances if r > price), default=None)

    # MACD histogram direction: is momentum building?
    hist_curr = float(last['macd_hist'])  if not np.isnan(last['macd_hist'])  else 0.0
    hist_prev = float(prev['macd_hist'])  if not np.isnan(prev['macd_hist'])  else 0.0
    macd_hist_rising  = hist_curr > hist_prev and hist_curr > 0
    macd_hist_falling = hist_curr < hist_prev and hist_curr < 0

    def _safe(val):
        return float(val) if not np.isnan(val) else 0.0

    return {
        'price':              price,
        'ema9':               _safe(last['ema9']),
        'ema21':              _safe(last['ema21']),
        'ema50':              _safe(last['ema50']),
        'rsi':                _safe(last['rsi']),
        'atr':                atr_val,
        'volume':             float(last['volume']),
        'volume_avg':         float(vol_avg),
        'volume_increasing':  bool(last['volume'] > vol_avg),
        'is_bull_candle':     bool(last['close'] > last['open']),
        'is_strong_candle':   is_strong_candle,
        'supports':           supports,
        'resistances':        resistances,
        'nearest_support':    nearest_support,
        'nearest_resistance': nearest_resistance,
        'market_structure':   _market_structure(df),
        'adx':                _safe(last['adx']),
        'plus_di':            _safe(last['plus_di']),
        'minus_di':           _safe(last['minus_di']),
        'macd':               _safe(last['macd']),
        'macd_sig':           _safe(last['macd_sig']),
        'macd_hist':          hist_curr,
        'macd_hist_rising':   macd_hist_rising,
        'macd_hist_falling':  macd_hist_falling,
        'macd_cross':         _macd_cross(df['macd'], df['macd_sig']),
        'ema_gap_expanding':  ema_gap_expanding,
    }
