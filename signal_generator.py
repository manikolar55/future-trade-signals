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
        reasons.append(f"EMA 9 above EMA 21 — short-term bullish")
    if a15['ema21'] > a15['ema50']:
        score += 10
        reasons.append("EMA 21 above EMA 50 — full bullish stack")

    # EMA gap expanding (5 pts)
    if a15.get('ema_gap_expanding') and a15['ema9'] > a15['ema21']:
        score += 5
        reasons.append("EMA gap widening — bullish momentum accelerating")

    # Market structure — 15m (10 pts)
    if a15['market_structure'] == 'BULLISH':
        score += 10
        reasons.append("Bullish market structure (HH / HL)")

    # Bollinger Band position (10 pts) — best entries near mid/lower band
    bp = a15['bb_position']
    if bp < 0.4:
        score += 10
        reasons.append(f"Price near BB lower/mid ({bp:.2f}) — room to run upward")
    elif bp > 0.85:
        reasons.append(f"Price near BB upper band ({bp:.2f}) — extended, LONG risky")

    # RSI — 5m (15 pts)
    rsi = a5['rsi']
    if 45 <= rsi <= 65:
        score += 15
        reasons.append(f"5m RSI at {rsi:.1f} — healthy bullish zone")
    elif 65 < rsi <= 70:
        score += 8
        reasons.append(f"5m RSI at {rsi:.1f} — bullish but approaching overbought")
    elif rsi > 70:
        reasons.append(f"5m RSI at {rsi:.1f} — overbought, LONG risky")
    else:
        reasons.append(f"5m RSI at {rsi:.1f} — weak momentum")

    # Stochastic — 5m (10 pts)
    if a5['stoch_bull_cross'] and a5['stoch_k'] < 60:
        score += 10
        reasons.append(f"Stochastic bullish cross at {a5['stoch_k']:.1f} — momentum turning up")
    elif a5['stoch_oversold']:
        score += 5
        reasons.append(f"Stochastic oversold ({a5['stoch_k']:.1f}) — bounce setup")
    elif a5['stoch_overbought']:
        reasons.append(f"Stochastic overbought ({a5['stoch_k']:.1f}) — LONG risky")

    # OBV — 15m (10 pts)
    if a15['obv_rising'] and not a15['obv_bearish_div']:
        score += 10
        reasons.append("OBV rising — real buying pressure confirmed")
    elif a15['obv_bearish_div']:
        reasons.append("OBV bearish divergence — price up but volume not confirming, caution")

    # Volume + candle body — 5m (10 pts)
    if a5['volume_increasing'] and a5['is_bull_candle'] and a5['is_strong_candle']:
        score += 10
        reasons.append("5m strong bullish candle with above-average volume")
    elif a5['volume_increasing'] and a5['is_bull_candle']:
        score += 5
        reasons.append("5m bullish candle with above-average volume")

    # MACD — 15m (15 pts crossover, 8 pts histogram building)
    cross = a15.get('macd_cross', 'BEAR')
    if cross == 'BULL_CROSS':
        score += 15
        reasons.append("MACD bullish crossover on 15m — momentum shift confirmed")
    elif a15.get('macd_hist_rising'):
        score += 8
        reasons.append(f"MACD histogram building bullish ({a15['macd_hist']:+.4f})")

    # Open Interest (10 pts)
    if oi.get('oi_rising'):
        score += 10
        reasons.append(f"OI rising +{oi['oi_change_pct']:.2f}% — real buyers entering")
    elif oi.get('oi_falling'):
        reasons.append(f"OI falling {oi['oi_change_pct']:.2f}% — possible liquidation, caution")

    return min(score, 100), reasons


def _score_short(a15: dict, a5: dict, oi: dict):
    score = 0
    reasons = []

    # EMA alignment — 15m (25 pts)
    if a15['ema9'] < a15['ema21']:
        score += 15
        reasons.append(f"EMA 9 below EMA 21 — short-term bearish")
    if a15['ema21'] < a15['ema50']:
        score += 10
        reasons.append("EMA 21 below EMA 50 — full bearish stack")

    # EMA gap expanding (5 pts)
    if a15.get('ema_gap_expanding') and a15['ema9'] < a15['ema21']:
        score += 5
        reasons.append("EMA gap widening — bearish momentum accelerating")

    # Market structure — 15m (10 pts)
    if a15['market_structure'] == 'BEARISH':
        score += 10
        reasons.append("Bearish market structure (LH / LL)")

    # Bollinger Band position (10 pts) — best short entries near upper band
    bp = a15['bb_position']
    if bp > 0.6:
        score += 10
        reasons.append(f"Price near BB upper/mid ({bp:.2f}) — room to drop")
    elif bp < 0.15:
        reasons.append(f"Price near BB lower band ({bp:.2f}) — extended down, SHORT risky")

    # RSI — 5m (15 pts): must be clearly bearish, not borderline
    rsi = a5['rsi']
    if 35 <= rsi <= 52:
        score += 15
        reasons.append(f"5m RSI at {rsi:.1f} — healthy bearish zone")
    elif 30 <= rsi < 35:
        score += 8
        reasons.append(f"5m RSI at {rsi:.1f} — bearish but approaching oversold")
    elif rsi < 30:
        reasons.append(f"5m RSI at {rsi:.1f} — oversold, SHORT risky")
    else:
        reasons.append(f"5m RSI at {rsi:.1f} — not bearish enough for SHORT")

    # Stochastic — 5m (10 pts)
    if a5['stoch_bear_cross'] and a5['stoch_k'] > 40:
        score += 10
        reasons.append(f"Stochastic bearish cross at {a5['stoch_k']:.1f} — momentum turning down")
    elif a5['stoch_overbought']:
        score += 5
        reasons.append(f"Stochastic overbought ({a5['stoch_k']:.1f}) — reversal setup")
    elif a5['stoch_oversold']:
        reasons.append(f"Stochastic oversold ({a5['stoch_k']:.1f}) — SHORT risky")

    # OBV — 15m (10 pts)
    if a15['obv_falling'] and not a15['obv_bullish_div']:
        score += 10
        reasons.append("OBV falling — real selling pressure confirmed")
    elif a15['obv_bullish_div']:
        reasons.append("OBV bullish divergence — price down but volume not confirming, caution")

    # Volume + candle body — 5m (10 pts)
    if a5['volume_increasing'] and not a5['is_bull_candle'] and a5['is_strong_candle']:
        score += 10
        reasons.append("5m strong bearish candle with above-average volume")
    elif a5['volume_increasing'] and not a5['is_bull_candle']:
        score += 5
        reasons.append("5m bearish candle with above-average volume")

    # MACD — 15m (15 pts crossover, 8 pts histogram building)
    cross = a15.get('macd_cross', 'BULL')
    if cross == 'BEAR_CROSS':
        score += 15
        reasons.append("MACD bearish crossover on 15m — momentum shift confirmed")
    elif a15.get('macd_hist_falling'):
        score += 8
        reasons.append(f"MACD histogram building bearish ({a15['macd_hist']:+.4f})")

    # Open Interest (10 pts)
    if oi.get('oi_rising'):
        score += 10
        reasons.append(f"OI rising +{oi['oi_change_pct']:.2f}% — real sellers entering")
    elif oi.get('oi_falling'):
        reasons.append(f"OI falling {oi['oi_change_pct']:.2f}% — possible liquidation, caution")

    return min(score, 100), reasons


_OI_DEFAULT = {'oi': 0.0, 'oi_change_pct': 0.0, 'oi_rising': False, 'oi_falling': False}


def _no_trade(symbol: str, a15: dict, a5: dict, reason: str,
              funding_rate: float = 0, oi: dict = None) -> dict:
    return {
        'symbol': symbol, 'signal': 'NO TRADE', 'confidence': 0,
        'entry': a15['price'], 'tp1': None, 'tp2': None, 'sl': None,
        'rr': 'N/A', 'trend': a15['market_structure'], 'adx': a15['adx'],
        'macd_cross': a15.get('macd_cross', ''), 'rsi': a5['rsi'],
        'ema9': a15['ema9'], 'ema21': a15['ema21'], 'ema50': a15['ema50'],
        'volume': a5['volume'], 'funding_rate': funding_rate,
        'oi_change_pct': (oi or _OI_DEFAULT)['oi_change_pct'],
        'oi_rising': (oi or _OI_DEFAULT)['oi_rising'],
        'reasons': [reason],
    }


def generate_signal(symbol: str, df_15m, df_5m=None, df_1h=None, df_4h=None,
                    funding_rate: float = 0, oi_data: dict = None,
                    min_confidence: int = 80) -> dict:
    a15 = analyze(df_15m)
    a5  = analyze(df_5m) if df_5m is not None else a15
    a1h = analyze(df_1h) if df_1h is not None else None
    a4h = analyze(df_4h) if df_4h is not None else None
    oi  = oi_data or _OI_DEFAULT

    price = a15['price']
    atr   = a15['atr']
    adx   = a15['adx']

    # ADX gate — no trend, no trade
    if adx < 25:
        return _no_trade(symbol, a15, a5,
                         f"ADX {adx:.1f} — ranging market, no trade",
                         funding_rate, oi)

    long_score,  long_reasons  = _score_long(a15, a5, oi)
    short_score, short_reasons = _score_short(a15, a5, oi)

    # Directional ADX bonus — only boosts direction DI confirms
    if adx > 30:
        if a15['plus_di'] > a15['minus_di']:
            long_score  = min(long_score + 5, 100)
            long_reasons.append(f"ADX {adx:.1f}, +DI dominant — bulls in control")
        else:
            short_score = min(short_score + 5, 100)
            short_reasons.append(f"ADX {adx:.1f}, -DI dominant — bears in control")

    # Funding rate penalty
    if funding_rate > 0.0005 and long_score >= short_score:
        long_score = max(long_score - 15, 0)
        long_reasons.append(f"Funding {funding_rate*100:.3f}% — longs paying heavy")
    if funding_rate < -0.0005 and short_score > long_score:
        short_score = max(short_score - 15, 0)
        short_reasons.append(f"Funding {funding_rate*100:.3f}% — shorts paying heavy")

    # Hard BB gate — only trade from the correct side of the band
    # LONG: price must be in lower half (room to rise). Block if above 0.75
    if long_score > short_score and a15['bb_position'] > 0.75:
        return _no_trade(symbol, a15, a5,
                         f"Price in BB upper zone ({a15['bb_position']:.2f}) — LONG blocked, limited upside",
                         funding_rate, oi)
    # SHORT: price must be in upper half (room to fall). Block if below 0.30
    if short_score > long_score and a15['bb_position'] < 0.30:
        return _no_trade(symbol, a15, a5,
                         f"Price in BB lower zone ({a15['bb_position']:.2f}) — SHORT blocked, limited downside",
                         funding_rate, oi)

    # Hard OBV divergence gate — block trades where volume contradicts price
    if long_score > short_score and a15['obv_bearish_div']:
        return _no_trade(symbol, a15, a5,
                         "OBV bearish divergence — price rising without volume, LONG blocked",
                         funding_rate, oi)
    if short_score > long_score and a15['obv_bullish_div']:
        return _no_trade(symbol, a15, a5,
                         "OBV bullish divergence — price falling without volume, SHORT blocked",
                         funding_rate, oi)

    # 4H trend filter
    if a4h is not None:
        h4_bullish = a4h['ema9'] > a4h['ema21'] and a4h['ema21'] > a4h['ema50']
        h4_bearish = a4h['ema9'] < a4h['ema21'] and a4h['ema21'] < a4h['ema50']
        if h4_bearish and long_score > short_score:
            return _no_trade(symbol, a15, a5, "4H bearish — LONG blocked", funding_rate, oi)
        if h4_bullish and short_score > long_score:
            return _no_trade(symbol, a15, a5, "4H bullish — SHORT blocked", funding_rate, oi)

    # 1H trend filter
    if a1h is not None:
        h1_bullish = a1h['ema9'] > a1h['ema21'] and a1h['ema21'] > a1h['ema50']
        h1_bearish = a1h['ema9'] < a1h['ema21'] and a1h['ema21'] < a1h['ema50']
        if h1_bearish and long_score > short_score:
            return _no_trade(symbol, a15, a5, "1H bearish — LONG blocked", funding_rate, oi)
        if h1_bullish and short_score > long_score:
            return _no_trade(symbol, a15, a5, "1H bullish — SHORT blocked", funding_rate, oi)

    # Hard momentum gate — must have at least one real momentum signal
    if long_score > short_score:
        has_momentum = (
            a15.get('macd_cross') == 'BULL_CROSS' or
            oi.get('oi_rising') or
            a15.get('macd_hist_rising') or
            a5.get('stoch_bull_cross')
        )
        if not has_momentum:
            return _no_trade(symbol, a15, a5,
                             "No momentum confirmation — MACD, OI, Stoch all neutral",
                             funding_rate, oi)

    if short_score > long_score:
        has_momentum = (
            a15.get('macd_cross') == 'BEAR_CROSS' or
            oi.get('oi_rising') or
            a15.get('macd_hist_falling') or
            a5.get('stoch_bear_cross')
        )
        if not has_momentum:
            return _no_trade(symbol, a15, a5,
                             "No momentum confirmation — MACD, OI, Stoch all neutral",
                             funding_rate, oi)

    # Weak volume guard
    if not a5['volume_increasing'] and max(long_score, short_score) < 80:
        return _no_trade(symbol, a15, a5, "Weak volume — insufficient participation", funding_rate, oi)

    if long_score == short_score:
        return _no_trade(symbol, a15, a5, "Conflicting indicators — no clear bias", funding_rate, oi)

    def _build(sig, score, reasons, sl, tp1, tp2):
        rr = round(abs(tp1 - price) / max(abs(price - sl), 1e-9), 1)
        return {
            'symbol': symbol, 'signal': sig, 'confidence': score,
            'entry': price, 'tp1': tp1, 'tp2': tp2, 'sl': sl,
            'rr': f"1:{rr}", 'trend': a15['market_structure'], 'adx': adx,
            'macd_cross': a15.get('macd_cross', ''), 'rsi': a5['rsi'],
            'ema9': a15['ema9'], 'ema21': a15['ema21'], 'ema50': a15['ema50'],
            'volume': a5['volume'], 'funding_rate': funding_rate,
            'oi_change_pct': oi['oi_change_pct'], 'oi_rising': oi['oi_rising'],
            'bb_position': a15['bb_position'],
            'obv_rising': a15['obv_rising'],
            'stoch_k': a5['stoch_k'],
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
                     f"Confidence below {min_confidence}% — skipped",
                     funding_rate, oi)
