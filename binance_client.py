import time
import ccxt
import pandas as pd
from config import BINANCE_API_KEY, BINANCE_API_SECRET

_exchange = None


def get_exchange():
    global _exchange
    if _exchange is None:
        _exchange = ccxt.binanceusdm({
            'apiKey': BINANCE_API_KEY,
            'secret': BINANCE_API_SECRET,
            'enableRateLimit': True,
            'options': {
                'adjustForTimeDifference': True,
                'recvWindow': 60000,
            },
        })
    return _exchange


def sync_time():
    """Re-sync clock with Binance server — call at the start of every scan."""
    try:
        get_exchange().load_time_difference()
    except Exception:
        pass


def get_top_usdt_futures(limit=50):
    try:
        ex = get_exchange()
        markets = ex.load_markets()

        usdt_symbols = [
            s for s, m in markets.items()
            if m.get('settle') == 'USDT' and m.get('type') == 'swap' and m.get('active', True)
        ]

        print(f"[binance] Found {len(usdt_symbols)} USDT futures markets")

        try:
            tickers = ex.fetch_tickers()
            sym_set = set(usdt_symbols)
            ranked = sorted(
                [(k, v) for k, v in tickers.items() if k in sym_set],
                key=lambda x: x[1].get('quoteVolume') or 0,
                reverse=True
            )
            result = [s for s, _ in ranked]
            if result:
                return result[:limit]
        except Exception as te:
            print(f"[binance] Volume sort failed ({te}), using market list order")

        return usdt_symbols[:limit]

    except Exception as e:
        print(f"[binance] Failed to fetch symbols: {e}")
        return ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'BNB/USDT:USDT', 'SOL/USDT:USDT', 'XRP/USDT:USDT']


def get_ohlcv(symbol: str, timeframe: str = '15m', limit: int = 150, retries: int = 2):
    ex = get_exchange()
    for attempt in range(retries + 1):
        try:
            raw = ex.fetch_ohlcv(symbol, timeframe, limit=limit)
            if not raw or len(raw) < 50:
                return None
            df = pd.DataFrame(raw, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.set_index('timestamp')
            df = df.astype(float)
            return df
        except Exception as e:
            if attempt < retries:
                time.sleep(1.0 * (attempt + 1))   # 1s then 2s backoff
            else:
                print(f"[binance] OHLCV error {symbol} {timeframe}: {e}")
    return None


def get_open_interest_change(symbol: str) -> dict:
    default = {'oi': 0.0, 'oi_change_pct': 0.0, 'oi_rising': False, 'oi_falling': False}
    try:
        ex = get_exchange()
        history = ex.fetch_open_interest_history(symbol, '5m', limit=5)
        if not history or len(history) < 2:
            return default
        latest   = float(history[-1].get('openInterestAmount', 0) or 0)
        earliest = float(history[0].get('openInterestAmount', 0) or 0)
        if earliest == 0:
            return default
        change_pct = (latest - earliest) / earliest * 100
        return {
            'oi': latest,
            'oi_change_pct': round(change_pct, 3),
            'oi_rising':  change_pct >  0.1,
            'oi_falling': change_pct < -0.1,
        }
    except Exception:
        return default


def get_funding_rate(symbol: str) -> float:
    try:
        ex = get_exchange()
        fr = ex.fetch_funding_rate(symbol)
        return float(fr.get('fundingRate', 0) or 0)
    except Exception:
        return 0.0
