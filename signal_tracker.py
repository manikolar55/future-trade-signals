import json
import os
from datetime import datetime

_DATA_FILE = 'data.json'

active_signals: dict = {}
closed_signals: list = []
win_count: int = 0
loss_count: int = 0


def _save():
    try:
        with open(_DATA_FILE, 'w') as f:
            json.dump({
                'active':  active_signals,
                'closed':  closed_signals,
                'wins':    win_count,
                'losses':  loss_count,
            }, f)
    except Exception as e:
        print(f"[tracker] Save error: {e}")


def load():
    global active_signals, closed_signals, win_count, loss_count
    if not os.path.exists(_DATA_FILE):
        return
    try:
        with open(_DATA_FILE) as f:
            d = json.load(f)
        active_signals = d.get('active', {})
        closed_signals = d.get('closed', [])
        win_count      = d.get('wins', 0)
        loss_count     = d.get('losses', 0)
        print(f"[tracker] Loaded {len(active_signals)} active, {len(closed_signals)} closed signals from disk")
    except Exception as e:
        print(f"[tracker] Load error: {e}")


def add_signal(signal: dict):
    symbol = signal['symbol']
    active_signals[symbol] = {
        **signal,
        'status': 'MONITORING',
        'open_time': signal.get('timestamp', datetime.now().isoformat()),
    }
    _save()


def check_outcome(symbol: str, current_price: float) -> str | None:
    global win_count, loss_count

    if symbol not in active_signals:
        return None

    signal = active_signals[symbol]
    tp1 = signal['tp1']
    sl  = signal['sl']

    outcome = None
    if signal['signal'] == 'LONG':
        if current_price >= tp1:
            outcome = 'WIN'
        elif current_price <= sl:
            outcome = 'LOSS'
    elif signal['signal'] == 'SHORT':
        if current_price <= tp1:
            outcome = 'WIN'
        elif current_price >= sl:
            outcome = 'LOSS'

    if outcome:
        closed = {
            **signal,
            'outcome':     outcome,
            'close_price': current_price,
            'close_time':  datetime.now().isoformat(),
        }
        closed_signals.insert(0, closed)
        del active_signals[symbol]

        if outcome == 'WIN':
            win_count += 1
        else:
            loss_count += 1

        total = win_count + loss_count
        rate  = round(win_count / total * 100, 1) if total else 0
        print(f"[tracker] {symbol} {signal['signal']} → {outcome} @ {current_price} | Win rate: {rate}%")
        _save()

    return outcome


def get_stats() -> dict:
    total = win_count + loss_count
    return {
        'total':    total,
        'wins':     win_count,
        'losses':   loss_count,
        'win_rate': round(win_count / total * 100, 1) if total else 0,
        'active':   len(active_signals),
    }


def get_active() -> list:
    return list(active_signals.values())


def get_closed() -> list:
    return closed_signals[:100]
