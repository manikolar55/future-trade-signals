from analyzer import analyze


def _fmt(price) -> str:
    if price is None:
        return 'N/A'
    if price >= 1000:
        return f"{price:.2f}"
    if price >= 1:
        return f"{price:.4f}"
    return f"{price:.6f}"


def _score_long(a15: dict, a5: dict, oi: dict):
    score = 0
    reasons = []

    # EMA alignment — 15m (25 pts)
    if a15['ema9'] > a15['ema21']:
        score += 15
        reasons.append(f"EMA 9 ({_fmt(a15['ema9'])}) above EMA 21 ({_fmt(a15['ema21'])})")
    if a15['ema21'] > a15['ema50']:
        score += 10
        reasons.append("EMA 21 above EMA 50 — full bullish stack")

    # Market structure — 15m (10 pts)
    if a15['market_structure'] == 'BULLISH':
        score += 10
        reasons.append("Bullish market structure (HH / HL)")

    # Support proximity — 15m (10 pts)
    # Price must be above support but NOT pressed against resistance (within 0.5 ATR)
    atr = a15['atr']
    if a15['nearest_support'] and a15['price'] > a15['nearest_support']:
        if a15['nearest_resistance'] and (a15['nearest_resistance'] - a15['price']) < atr * 0.5:
            reasons.append(f"Price too close to resistance {_fmt(a15['nearest_resistance'])} — limited upside")
        else:
            score += 10
            reasons.append(f"Price holding above support {_fmt(a15['nearest_support'])}")

    # RSI — 5m (15 pts): healthy bullish zone only
    rsi = a5['rsi']
    if 45 <= rsi <= 70:
        score += 15
        reasons.append(f"5m RSI at {rsi:.1f} — bullish momentum, not overbought")
    elif rsi > 70:
        reasons.append(f"5m RSI at {rsi:.1f} — overbought, LONG risky")
    else:
        reasons.append(f"5m RSI at {rsi:.1f} — weak momentum")

    # Volume + candle body — 5m (15 pts)
    if a5['volume_increasing'] and a5['is_bull_candle'] and a5['is_strong_candle']:
        score += 15
        reasons.append("5m strong bullish candle with above-average volume")
    elif a5['volume_increasing'] and a5['is_bull_candle']:
        score += 8
        reasons.append("5m bullish candle with above-average volume")
    elif a5['volume_increasing']:
        score += 3
        reasons.append("5m volume above average (indecisive candle)")

    # MACD — 15m (15 pts crossover, 8 pts histogram building)
    cross = a15.get('macd_cross', 'BEAR')
    if cross == 'BULL_CROSS':
        score += 15
        reasons.append("MACD bullish crossover on 15m — momentum shift confirmed")
    elif a15.get('macd_hist_rising'):
        score += 8
        reasons.append(f"MACD histogram building bullish momentum ({a15['macd_hist']:+.4f})")

    # Open Interest (10 pts)
    if oi.get('oi_rising'):
        score += 10
        reasons.append(f"Open Interest rising +{oi['oi_change_pct']:.2f}% — real buyers entering")
    elif oi.get('oi_falling'):
        reasons.append(f"Open Interest falling {oi['oi_change_pct']:.2f}% — possible liquidation, caution")

    return min(score, 100), reasons


def _score_short(a15: dict, a5: dict, oi: dict):
    score = 0
    reasons = []

    # EMA alignment — 15m (25 pts)
    if a15['ema9'] < a15['ema21']:
        score += 15
        reasons.append(f"EMA 9 ({_fmt(a15['ema9'])}) below EMA 21 ({_fmt(a15['ema21'])})")
    if a15['ema21'] < a15['ema50']:
        score += 10
        reasons.append("EMA 21 below EMA 50 — full bearish stack")

    # Market structure — 15m (10 pts)
    if a15['market_structure'] == 'BEARISH':
        score += 10
        reasons.append("Bearish market structure (LH / LL)")

    # Resistance proximity — 15m (10 pts)
    atr = a15['atr']
    if a15['nearest_resistance'] and a15['price'] < a15['nearest_resistance']:
        if a15['nearest_support'] and (a15['price'] - a15['nearest_support']) < atr * 0.5:
            reasons.append(f"Price too close to support {_fmt(a15['nearest_support'])} — limited downside")
        else:
            score += 10
            reasons.append(f"Price capped below resistance {_fmt(a15['nearest_resistance'])}")

    # RSI — 5m (15 pts): healthy bearish zone only
    rsi = a5['rsi']
    if 30 <= rsi <= 55:
        score += 15
        reasons.append(f"5m RSI at {rsi:.1f} — bearish momentum, not oversold")
    elif rsi < 30:
        reasons.append(f"5m RSI at {rsi:.1f} — oversold, SHORT risky")
    else:
        reasons.append(f"5m RSI at {rsi:.1f} — weak bearish momentum")

    # Volume + candle body — 5m (15 pts)
    if a5['volume_increasing'] and not a5['is_bull_candle'] and a5['is_strong_candle']:
        score += 15
        reasons.append("5m strong bearish candle with above-average volume")
    elif a5['volume_increasing'] and not a5['is_bull_candle']:
        score += 8
        reasons.append("5m bearish candle with above-average volume")
    elif a5['volume_increasing']:
        score += 3
        reasons.append("5m volume above average (indecisive candle)")

    # MACD — 15m (15 pts crossover, 8 pts histogram building)
    cross = a15.get('macd_cross', 'BULL')
    if cross == 'BEAR_CROSS':
        score += 15
        reasons.append("MACD bearish crossover on 15m — momentum shift confirmed")
    elif a15.get('macd_hist_falling'):
        score += 8
        reasons.append(f"MACD histogram building bearish momentum ({a15['macd_hist']:+.4f})")

    # Open Interest (10 pts)
    if oi.get('oi_rising'):
        score += 10
        reasons.append(f"Open Interest rising +{oi['oi_change_pct']:.2f}% — real sellers entering")
    elif oi.get('oi_falling'):
        reasons.append(f"Open Interest falling {oi['oi_change_pct']:.2f}% — possible liquidation, caution")

    return min(score, 100), reasons


_OI_DEFAULT = {'oi': 0.0, 'oi_change_pct': 0.0, 'oi_rising': False, 'oi_falling': False}


def _no_trade(symbol: str, a15: dict, a5: dict, reason: str,
              funding_rate: float = 0, oi: dict = None) -> dict:
    return {
        'symbol': symbol,
        'signal': 'NO TRADE',
        'confidence': 0,
        'entry': a15['price'],
        'tp1': None, 'tp2': None, 'sl': None,
        'rr': 'N/A',
        'trend': a15['market_structure'],
        'adx': a15['adx'],
        'macd_cross': a15.get('macd_cross', ''),
        'rsi': a5['rsi'],
        'ema9': a15['ema9'], 'ema21': a15['ema21'], 'ema50': a15['ema50'],
        'volume': a5['volume'],
        'funding_rate': funding_rate,
        'oi_change_pct': (oi or _OI_DEFAULT)['oi_change_pct'],
        'oi_rising': (oi or _OI_DEFAULT)['oi_rising'],
        'reasons': [reason],
    }


def generate_signal(symbol: str, df_15m, df_5m=None, df_1h=None,
                    funding_rate: float = 0, oi_data: dict = None,
                    min_confidence: int = 75) -> dict:
    a15 = analyze(df_15m)
    a5  = analyze(df_5m) if df_5m is not None else a15
    a1h = analyze(df_1h) if df_1h is not None else None
    oi  = oi_data or _OI_DEFAULT

    price = a15['price']
    atr   = a15['atr']
    adx   = a15['adx']

    # ADX gate — no trend, no trade
    if adx < 25:
        return _no_trade(symbol, a15, a5,
                         f"ADX at {adx:.1f} — market ranging, no tradeable trend",
                         funding_rate, oi)

    long_score,  long_reasons  = _score_long(a15, a5, oi)
    short_score, short_reasons = _score_short(a15, a5, oi)

    # Directional ADX bonus — only boost the direction DI confirms
    if adx > 30:
        if a15['plus_di'] > a15['minus_di']:
            long_score  = min(long_score + 5, 100)
            long_reasons.append(f"ADX {adx:.1f} strong trend, +DI dominant — bulls in control")
        else:
            short_score = min(short_score + 5, 100)
            short_reasons.append(f"ADX {adx:.1f} strong trend, -DI dominant — bears in control")

    # Funding rate penalty
    if funding_rate > 0.0005 and long_score >= short_score:
        long_score = max(long_score - 15, 0)
        long_reasons.append(f"Funding {funding_rate*100:.3f}% — longs paying heavy, confidence reduced")
    if funding_rate < -0.0005 and short_score > long_score:
        short_score = max(short_score - 15, 0)
        short_reasons.append(f"Funding {funding_rate*100:.3f}% — shorts paying heavy, confidence reduced")

    # 1H trend filter — block trades against the bigger trend
    if a1h is not None:
        h1_bullish = a1h['ema9'] > a1h['ema21'] and a1h['ema21'] > a1h['ema50']
        h1_bearish = a1h['ema9'] < a1h['ema21'] and a1h['ema21'] < a1h['ema50']

        if h1_bearish and long_score > short_score:
            return _no_trade(symbol, a15, a5,
                             "1H trend is bearish — LONG blocked to avoid counter-trend trade",
                             funding_rate, oi)
        if h1_bullish and short_score > long_score:
            return _no_trade(symbol, a15, a5,
                             "1H trend is bullish — SHORT blocked to avoid counter-trend trade",
                             funding_rate, oi)

    # Weak volume guard
    if not a5['volume_increasing'] and max(long_score, short_score) < 75:
        return _no_trade(symbol, a15, a5, "Weak volume — insufficient participation", funding_rate, oi)

    if long_score == short_score:
        return _no_trade(symbol, a15, a5, "Conflicting indicators — no clear bias", funding_rate, oi)

    def _build(sig, score, reasons, sl, tp1, tp2):
        rr = round(abs(tp1 - price) / max(abs(price - sl), 1e-9), 1)
        return {
            'symbol': symbol, 'signal': sig, 'confidence': score,
            'entry': price, 'tp1': tp1, 'tp2': tp2, 'sl': sl,
            'rr': f"1:{rr}",
            'trend': a15['market_structure'],
            'adx': adx,
            'macd_cross': a15.get('macd_cross', ''),
            'rsi': a5['rsi'],
            'ema9': a15['ema9'], 'ema21': a15['ema21'], 'ema50': a15['ema50'],
            'volume': a5['volume'],
            'funding_rate': funding_rate,
            'oi_change_pct': oi['oi_change_pct'],
            'oi_rising': oi['oi_rising'],
            'reasons': reasons,
        }

    if long_score > short_score and long_score >= min_confidence:
        return _build('LONG', long_score, long_reasons,
                      sl=price - atr * 2.0,
                      tp1=price + atr * 3.0,
                      tp2=price + atr * 5.0)

    if short_score > long_score and short_score >= min_confidence:
        return _build('SHORT', short_score, short_reasons,
                      sl=price + atr * 2.0,
                      tp1=price - atr * 3.0,
                      tp2=price - atr * 5.0)

    return _no_trade(symbol, a15, a5,
                     f"Confidence below {min_confidence}% — skipped for capital protection",
                     funding_rate, oi)
