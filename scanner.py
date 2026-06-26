import time
from collections import deque
from datetime import datetime
from binance_client import get_top_usdt_futures, get_ohlcv, get_funding_rate, get_open_interest_change, get_current_price, sync_time
from signal_generator import generate_signal
from telegram_notifier import send_signal
from signal_tracker import add_signal, check_outcome
from config import TOP_SYMBOLS, MIN_CONFIDENCE

signals_store: dict = {}
signals_history: deque = deque(maxlen=100)
last_scan_time: str | None = None
is_scanning: bool = False
scan_errors: list = []
_sent_cache: set = set()


def run_scan() -> None:
    global last_scan_time, is_scanning, scan_errors

    if is_scanning:
        return

    is_scanning = True
    scan_errors = []
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"\n[{ts}] Scan started — fetching top {TOP_SYMBOLS} symbols...")
    sync_time()

    try:
        symbols = get_top_usdt_futures(TOP_SYMBOLS)
        print(f"[scanner] Got {len(symbols)} symbols")

        new_alerts = 0

        for i, symbol in enumerate(symbols):
            try:
                df_15m = get_ohlcv(symbol, '15m', 150)
                df_5m  = get_ohlcv(symbol, '5m', 100)
                df_1h  = get_ohlcv(symbol, '1h', 100)

                if df_15m is None:
                    continue

                # Check if any open signal for this symbol hit TP1 or SL
                current_price = float(df_15m['close'].iloc[-1])
                check_outcome(symbol, current_price)

                funding_rate = get_funding_rate(symbol)
                oi_data      = get_open_interest_change(symbol)
                signal = generate_signal(symbol, df_15m, df_5m, df_1h=df_1h,
                                         funding_rate=funding_rate,
                                         oi_data=oi_data,
                                         min_confidence=MIN_CONFIDENCE)
                signal['timestamp'] = datetime.now().isoformat()
                signals_store[symbol] = signal

                if signal['signal'] in ('LONG', 'SHORT'):
                    from signal_tracker import active_signals as _active
                    if symbol not in _active:                   # don't overwrite existing entry
                        add_signal(signal)
                    signals_history.appendleft(dict(signal))

                    cache_key = f"{symbol}|{signal['signal']}|{signal['confidence']}"
                    if cache_key not in _sent_cache:
                        if send_signal(signal):
                            _sent_cache.add(cache_key)
                            new_alerts += 1

                time.sleep(0.4)

                if (i + 1) % 10 == 0:
                    print(f"  [{i + 1}/{len(symbols)}] scanned...")

            except Exception as e:
                msg = f"{symbol}: {e}"
                scan_errors.append(msg)
                print(f"  [error] {msg}")

        # Check outcome for monitored coins that weren't in this scan's top 50
        from signal_tracker import active_signals
        missed = [sym for sym in list(active_signals.keys()) if sym not in symbols]
        for sym in missed:
            price = get_current_price(sym)
            if price is not None:
                check_outcome(sym, price)

        last_scan_time = datetime.now().isoformat()
        long_c  = sum(1 for s in signals_store.values() if s['signal'] == 'LONG')
        short_c = sum(1 for s in signals_store.values() if s['signal'] == 'SHORT')
        print(f"[scanner] Done — {long_c} LONG, {short_c} SHORT, {new_alerts} alerts sent")

        if len(_sent_cache) > 500:
            _sent_cache.clear()

    except Exception as e:
        print(f"[scanner] Fatal: {e}")
        scan_errors.append(str(e))
    finally:
        is_scanning = False
