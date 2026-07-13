import logging
import time
from collections import deque
from datetime import datetime
from binance_client import get_top_usdt_futures, get_ohlcv, get_funding_rate, get_open_interest_change, get_current_price, sync_time
from signal_generator import generate_signal
from telegram_notifier import send_signal
from signal_tracker import add_signal, check_outcome, expire_old_signals
from config import TOP_SYMBOLS, MIN_CONFIDENCE

log = logging.getLogger(__name__)

signals_store: dict = {}
signals_history: deque = deque(maxlen=100)
last_scan_time: str | None = None
is_scanning: bool = False
scan_errors: list = []
_sent_cache: set = set()
market_health: dict = {}
_pending: dict = {}  # symbol -> direction — waits for 2nd consecutive confirmation


def run_scan() -> None:
    global last_scan_time, is_scanning, scan_errors

    if is_scanning:
        return

    is_scanning = True
    scan_errors = []
    log.info(f"=== Scan started — fetching top {TOP_SYMBOLS} symbols ===")
    sync_time()

    expired = expire_old_signals(72)  # drop signals open >3 days
    if expired:
        log.info(f"[scanner] Expired {expired} stale signal(s) older than 72h")

    try:
        symbols = get_top_usdt_futures(TOP_SYMBOLS)
        log.info(f"[scanner] Got {len(symbols)} symbols")

        new_alerts = 0

        for i, symbol in enumerate(symbols):
            try:
                df_15m = get_ohlcv(symbol, '15m', 150)
                df_5m  = get_ohlcv(symbol, '5m', 100)
                df_1h  = get_ohlcv(symbol, '1h', 100)
                df_4h  = get_ohlcv(symbol, '4h', 60)

                if df_15m is None:
                    continue

                current_price = float(df_15m['close'].iloc[-1])
                check_outcome(symbol, current_price)

                funding_rate = get_funding_rate(symbol)
                oi_data      = get_open_interest_change(symbol)
                signal = generate_signal(symbol, df_15m, df_5m, df_1h=df_1h, df_4h=df_4h,
                                         funding_rate=funding_rate,
                                         oi_data=oi_data,
                                         min_confidence=MIN_CONFIDENCE)
                signal['timestamp'] = datetime.now().isoformat()
                signals_store[symbol] = signal

                sym_short = symbol.split('/')[0]

                if signal['signal'] in ('LONG', 'SHORT'):
                    direction = signal['signal']
                    if _pending.get(symbol) == direction:
                        # Confirmed across 2 consecutive scans — enter
                        _pending.pop(symbol, None)
                        log.info(f"  *** {sym_short} {direction} CONFIRMED | conf={signal['confidence']}% | "
                                 f"entry={signal['entry']} tp1={signal['tp1']} sl={signal['sl']} | "
                                 f"rsi={signal['rsi']:.1f} adx={signal['adx']:.1f} bb={signal.get('bb_position', 0):.2f} | "
                                 f"reasons: {' / '.join(signal['reasons'])}")

                        from signal_tracker import active_signals as _active
                        is_new = symbol not in _active
                        if is_new:
                            add_signal(signal)
                            signals_history.appendleft(dict(signal))

                        cache_key = f"{symbol}|{direction}"
                        if cache_key not in _sent_cache:
                            if send_signal(signal):
                                _sent_cache.add(cache_key)
                                new_alerts += 1
                    else:
                        # First time seeing this signal — stage it, wait for next scan
                        _pending[symbol] = direction
                        log.info(f"  [staged] {sym_short} {direction} conf={signal['confidence']}% — waiting for confirmation")
                else:
                    _pending.pop(symbol, None)  # Reset if signal disappears
                    log.info(f"  {sym_short} NO TRADE — {signal['reasons'][0]}")

                time.sleep(0.4)

            except Exception as e:
                msg = f"{symbol}: {e}"
                scan_errors.append(msg)
                log.error(f"  [error] {msg}")

        # Check monitored coins not in current scan
        from signal_tracker import active_signals
        if not symbols:
            log.warning("[scanner] Empty symbol list — skipping missed-signal checks")
        missed = [sym for sym in list(active_signals.keys()) if sym not in symbols] if symbols else []
        for sym in missed:
            price = get_current_price(sym)
            if price is not None:
                check_outcome(sym, price)

        last_scan_time = datetime.now().isoformat()
        long_c  = sum(1 for s in signals_store.values() if s['signal'] == 'LONG')
        short_c = sum(1 for s in signals_store.values() if s['signal'] == 'SHORT')

        # Market health snapshot
        all_adx = [(s['symbol'].split('/')[0], s.get('adx', 0)) for s in signals_store.values() if s.get('adx')]
        all_adx.sort(key=lambda x: x[1], reverse=True)
        adx_values = [v for _, v in all_adx]
        avg_adx = round(sum(adx_values) / len(adx_values), 1) if adx_values else 0
        above_30 = sum(1 for v in adx_values if v >= 30)
        state = 'TRENDING' if above_30 >= 10 else ('MIXED' if above_30 >= 3 else 'RANGING')
        market_health.update({
            'avg_adx':    avg_adx,
            'above_30':   above_30,
            'state':      state,
            'watchlist':  [{'symbol': s, 'adx': round(v, 1)} for s, v in all_adx[:8]],
        })

        log.info(f"=== Scan done — {long_c} LONG, {short_c} SHORT, {new_alerts} alerts sent | "
                 f"Market: {state} avg_adx={avg_adx} coins_trending={above_30} ===")

        if len(_sent_cache) > 500:
            _sent_cache.clear()

    except Exception as e:
        log.error(f"[scanner] Fatal: {e}")
        scan_errors.append(str(e))
    finally:
        is_scanning = False
