import time
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def _fmt(price) -> str:
    if price is None:
        return 'N/A'
    if price >= 1000:
        return f"{price:.2f}"
    if price >= 1:
        return f"{price:.4f}"
    return f"{price:.6f}"


def _post(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[telegram] Not configured — skipping message")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for attempt in range(3):
        try:
            resp = requests.post(url, json={
                'chat_id': TELEGRAM_CHAT_ID,
                'text': text,
                'parse_mode': 'HTML',
            }, timeout=15)
            return resp.status_code == 200
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                print(f"[telegram] Error after 3 attempts: {e}")
    return False


def send_signal(signal: dict) -> bool:
    s = signal['signal']
    emoji = '🟢' if s == 'LONG' else '🔴'
    sym = signal['symbol'].split('/')[0]
    reasons = '\n'.join(f"  • {r}" for r in signal['reasons'])

    macd_cross = signal.get('macd_cross', '')
    macd_label = {'BULL_CROSS': '✅ Bullish crossover', 'BEAR_CROSS': '✅ Bearish crossover',
                  'BULL': 'Above signal', 'BEAR': 'Below signal'}.get(macd_cross, '—')
    oi_pct  = signal.get('oi_change_pct', 0)
    oi_icon = '📈' if oi_pct > 0 else '📉'
    fr      = signal.get('funding_rate', 0)

    text = (
        f"{emoji} <b>{s} — {sym}/USDT</b>\n\n"
        f"📊 <b>Confidence:</b> {signal['confidence']}%\n"
        f"💰 <b>Entry:</b> <code>{_fmt(signal['entry'])}</code>\n"
        f"🎯 <b>TP1:</b> <code>{_fmt(signal['tp1'])}</code>\n"
        f"🎯 <b>TP2:</b> <code>{_fmt(signal['tp2'])}</code>\n"
        f"🛡️ <b>Stop Loss:</b> <code>{_fmt(signal['sl'])}</code>\n"
        f"⚖️ <b>R/R:</b> {signal['rr']}\n\n"
        f"📈 <b>Trend:</b> {signal['trend']}\n"
        f"📉 <b>RSI (5m):</b> {signal['rsi']:.1f}\n"
        f"📊 <b>ADX:</b> {signal.get('adx', 0):.1f}\n"
        f"〽️ <b>MACD:</b> {macd_label}\n"
        f"{oi_icon} <b>Open Interest:</b> {oi_pct:+.2f}%\n"
        f"💸 <b>Funding Rate:</b> {fr*100:.3f}%\n\n"
        f"<b>Analysis:</b>\n{reasons}\n\n"
        f"⚠️ <i>Not financial advice. Always use proper risk management.</i>"
    )
    return _post(text)


def send_startup() -> None:
    _post(
        "🚀 <b>Futures Signal Scanner is live!</b>\n"
        "Scanning top USDT futures pairs on Binance every 5 minutes.\n"
        "Only signals with ≥70% confidence will be sent here."
    )
