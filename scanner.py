import time
from collections import deque
from datetime import datetime
from binance_client import get_top_usdt_futures, get_ohlcv, get_funding_rate, get_open_interest_change
from signal_generator import generate_signal
from telegram_notifier import send_signal
from config import TOP_SYMBOLS, MIN_CONFIDENCE

signals_store: dict = {}
signals_history: deque = deque(maxlen=100)   # last 100 actionable signals across all scans
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

    try:
        symbols = get_top_usdt_futures(TOP_SYMBOLS)
        print(f"[scanner] Got {len(symbols)} symbols")

        new_alerts = 0

        for i, symbol in enumerate(symbols):
            try:
                df_15m = get_ohlcv(symbol, '15m', 150)
                df_5m = get_ohlcv(symbol, '5m', 100)

                if df_15m is None:
                    continue

                funding_rate = get_funding_rate(symbol)
                oi_data      = get_open_interest_change(symbol)
                signal = generate_signal(symbol, df_15m, df_5m,
                                         funding_rate=funding_rate,
                                         oi_data=oi_data,
                                         min_confidence=MIN_CONFIDENCE)
                signal['timestamp'] = datetime.now().isoformat()
                signals_store[symbol] = signal

                if signal['signal'] in ('LONG', 'SHORT'):
                    signals_history.appendleft(dict(signal))   # newest first
                    cache_key = f"{symbol}|{signal['signal']}|{signal['confidence']}"
                    if cache_key not in _sent_cache:
                        if send_signal(signal):
                            _sent_cache.add(cache_key)
                            new_alerts += 1

                time.sleep(0.15)

                if (i + 1) % 10 == 0:
                    print(f"  [{i + 1}/{len(symbols)}] scanned...")

            except Exception as e:
                msg = f"{symbol}: {e}"
                scan_errors.append(msg)
                print(f"  [error] {msg}")

        last_scan_time = datetime.now().isoformat()
        long_c = sum(1 for s in signals_store.values() if s['signal'] == 'LONG')
        short_c = sum(1 for s in signals_store.values() if s['signal'] == 'SHORT')
        print(f"[scanner] Done — {long_c} LONG, {short_c} SHORT, {new_alerts} Telegram alerts sent")

        if len(_sent_cache) > 500:
            _sent_cache.clear()

    except Exception as e:
        print(f"[scanner] Fatal: {e}")
        scan_errors.append(str(e))
    finally:
        is_scanning = False
