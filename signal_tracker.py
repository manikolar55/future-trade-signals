from datetime import datetime

active_signals: dict = {}   # symbol → signal being monitored
closed_signals: list = []   # all closed signals with WIN/LOSS
win_count: int = 0
loss_count: int = 0


def add_signal(signal: dict):
    symbol = signal['symbol']
    active_signals[symbol] = {
        **signal,
        'status': 'MONITORING',
        'open_time': signal.get('timestamp', datetime.now().isoformat()),
    }


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
            'outcome': outcome,
            'close_price': current_price,
            'close_time': datetime.now().isoformat(),
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
