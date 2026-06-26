# Crypto Futures Signal Scanner

A real-time Binance USDT-M Futures signal scanner that analyzes the top 50 coins using multi-timeframe technical analysis and sends trading alerts to Telegram. Built with Python + Flask.

---

## Features

- Scans **top 50 USDT-M Futures pairs** by volume every 5 minutes
- **Dual timeframe analysis** — 15m for trend, 5m for entry confirmation
- **7-layer signal scoring system** with 70% minimum confidence threshold
- Sends **Telegram alerts** for every LONG/SHORT signal with full trade details
- **Live dashboard** at `http://localhost:5000` showing current positions and signal history
- Filters out low-quality setups using ADX, Funding Rate, and Open Interest
- **Signal history** — past signals stay visible even after the next scan

---

## Signal Logic

Every coin is scored out of 100 points across 7 factors:

| Factor | Timeframe | Points |
|--------|-----------|--------|
| EMA 9 / EMA 21 alignment | 15m | 15 |
| EMA 21 / EMA 50 alignment | 15m | 10 |
| Market structure (HH/HL or LH/LL) | 15m | 10 |
| Price vs Support / Resistance | 15m | 10 |
| RSI above/below 50 | 5m | 15 |
| Volume on candle direction | 5m | 15 |
| MACD crossover or position | 15m | 15 |
| Open Interest direction | 5m | 10 |

**Minimum score to generate a signal: 70/100**

### Additional Filters

- **ADX < 20** → NO TRADE (market is ranging, no trend to trade)
- **ADX > 25** → +5 confidence bonus (strong trend confirmed)
- **Funding Rate > +0.05%** → LONG confidence reduced by 15 (longs paying too much)
- **Funding Rate < -0.05%** → SHORT confidence reduced by 15 (shorts paying too much)
- **Open Interest rising** → +10 confidence (real money entering, not just liquidations)

### LONG Conditions
- EMA 9 above EMA 21 (bullish stack)
- RSI above 50 on 5m chart
- Volume above 10-period average on bullish candle
- Price holding above nearest support
- Bullish market structure (Higher Highs / Higher Lows)
- MACD line above or crossing above signal line

### SHORT Conditions
- EMA 9 below EMA 21 (bearish stack)
- RSI below 50 on 5m chart
- Volume above 10-period average on bearish candle
- Price capped below nearest resistance
- Bearish market structure (Lower Highs / Lower Lows)
- MACD line below or crossing below signal line

### Entry / TP / SL Calculation
Based on ATR (Average True Range, 14 period):

```
LONG:
  Stop Loss  = Entry - (ATR × 1.5)
  Take Profit 1 = Entry + (ATR × 2.0)
  Take Profit 2 = Entry + (ATR × 3.5)

SHORT:
  Stop Loss  = Entry + (ATR × 1.5)
  Take Profit 1 = Entry - (ATR × 2.0)
  Take Profit 2 = Entry - (ATR × 3.5)
```

---

## Project Structure

```
├── main.py               # Entry point — starts Flask + scheduler
├── app.py                # Flask web server & API routes
├── scanner.py            # Scan orchestrator — runs every 5 minutes
├── binance_client.py     # Binance USDT-M Futures API wrapper (ccxt)
├── analyzer.py           # Technical indicators (EMA, RSI, MACD, ADX, ATR)
├── signal_generator.py   # Scoring logic & signal generation
├── telegram_notifier.py  # Telegram bot alerts with retry
├── config.py             # Loads environment variables
├── requirements.txt      # Python dependencies
├── .env                  # API keys (not committed to git)
└── templates/
    └── index.html        # Live dashboard frontend
```

---

## Installation

### Requirements
- Python 3.10+
- Binance account with Futures API key
- Telegram Bot (created via @BotFather)

### 1. Clone the repository

```bash
git clone https://github.com/your-username/crypto-futures-scanner.git
cd crypto-futures-scanner
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```env
BINANCE_API_KEY=your_binance_api_key_here
BINANCE_API_SECRET=your_binance_api_secret_here
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here
SCAN_INTERVAL_MINUTES=5
MIN_CONFIDENCE=70
TOP_SYMBOLS=50
```

### 4. Run

```bash
python main.py
```

Open your browser at **http://localhost:5000**

---

## Getting Your Credentials

### Binance API Key
1. Go to [Binance](https://www.binance.com) → Account → API Management
2. Create a new API key
3. Enable **Futures trading** permission
4. Disable **withdrawals** (not needed, safer)
5. Copy the API Key and Secret into `.env`

### Telegram Bot
1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the steps
3. Copy the **Bot Token** into `.env`
4. To get your **Chat ID**: message your bot, then visit:
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
5. Find `"chat":{"id":XXXXXXXXX}` — that number is your Chat ID

---

## Dashboard

The web dashboard at `http://localhost:5000` shows:

**Live Positions** (updates every scan)
- LONG signals in green cards
- SHORT signals in red cards
- Each card shows: Entry · TP1 · TP2 · Stop Loss · R/R · Confidence · RSI · ADX · MACD · OI · Funding Rate

**Signal History** (never disappears)
- All LONG/SHORT signals fired in the current session
- Newest first — keeps last 100 signals
- Columns: Time · Symbol · Signal · Confidence · Entry · TP1 · TP2 · SL · R/R · RSI · ADX

**Auto-refreshes every 30 seconds.** Manual "Scan Now" button available.

---

## Telegram Alerts

Every signal with ≥70% confidence fires a Telegram message:

```
🟢 LONG — BTC/USDT

📊 Confidence: 85%
💰 Entry: 67450.00
🎯 TP1:   68200.00
🎯 TP2:   69100.00
🛡️ Stop Loss: 66800.00
⚖️ R/R: 1:2.1
📈 Trend: BULLISH
📉 RSI (5m): 58.3
📊 ADX: 32.1
〽️ MACD: ✅ Bullish crossover
📈 Open Interest: +1.25%
💸 Funding Rate: +0.010%

Analysis:
  • EMA 9 above EMA 21 — bullish stack
  • Bullish market structure (HH / HL)
  • 5m RSI at 58.3 — bullish momentum
  • MACD bullish crossover on 15m
  • Open Interest rising +1.25% — real buyers entering

⚠️ Not financial advice. Always use proper risk management.
```

---

## Configuration

All settings are in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `BINANCE_API_KEY` | — | Binance API key |
| `BINANCE_API_SECRET` | — | Binance API secret |
| `TELEGRAM_BOT_TOKEN` | — | Telegram bot token |
| `TELEGRAM_CHAT_ID` | — | Telegram chat/user ID |
| `SCAN_INTERVAL_MINUTES` | 5 | How often to scan (minutes) |
| `MIN_CONFIDENCE` | 70 | Minimum score to generate signal |
| `TOP_SYMBOLS` | 50 | Number of top coins to scan |

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard |
| `/api/signals` | GET | Current scan results + history |
| `/api/scan` | POST | Trigger manual scan |
| `/api/status` | GET | Scanner status |

---

## Risk Disclaimer

This tool is for **informational purposes only**. It does not place trades automatically. All signals are based on technical analysis and do not guarantee profit. Cryptocurrency futures trading involves significant risk of loss. Always use proper position sizing and risk management. Never trade more than you can afford to lose.

---

## Tech Stack

- **Python 3.12**
- **ccxt** — Binance USDT-M Futures market data
- **pandas / numpy** — Technical indicator calculations
- **Flask** — Web server & REST API
- **APScheduler** — Background scan scheduling
- **Telegram Bot API** — Signal notifications
