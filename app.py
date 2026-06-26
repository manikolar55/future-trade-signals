import threading
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import scanner
import signal_tracker
import telegram_notifier

app = Flask(__name__)
CORS(app)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/signals')
def get_signals():
    all_signals = list(scanner.signals_store.values())
    long_count  = sum(1 for s in all_signals if s['signal'] == 'LONG')
    short_count = sum(1 for s in all_signals if s['signal'] == 'SHORT')
    return jsonify({
        'signals':     all_signals,
        'history':     list(scanner.signals_history),
        'active':      signal_tracker.get_active(),
        'closed':      signal_tracker.get_closed(),
        'performance': signal_tracker.get_stats(),
        'last_scan':   scanner.last_scan_time,
        'is_scanning': scanner.is_scanning,
        'total':       len(all_signals),
        'long_count':  long_count,
        'short_count': short_count,
        'no_trade_count': len(all_signals) - long_count - short_count,
        'errors':      scanner.scan_errors[-5:],
    })


@app.route('/api/scan', methods=['POST'])
def trigger_scan():
    if scanner.is_scanning:
        return jsonify({'status': 'already_scanning'})
    t = threading.Thread(target=scanner.run_scan, daemon=True)
    t.start()
    return jsonify({'status': 'started'})


@app.route('/api/settings', methods=['GET'])
def get_settings():
    return jsonify({'telegram_enabled': telegram_notifier.telegram_enabled})


@app.route('/api/settings', methods=['POST'])
def update_settings():
    data = request.get_json()
    if 'telegram_enabled' in data:
        telegram_notifier.telegram_enabled = bool(data['telegram_enabled'])
        telegram_notifier.save_settings()
    return jsonify({'telegram_enabled': telegram_notifier.telegram_enabled})


@app.route('/api/status')
def status():
    return jsonify({
        'scanning':     scanner.is_scanning,
        'last_scan':    scanner.last_scan_time,
        'signal_count': len(scanner.signals_store),
        'performance':  signal_tracker.get_stats(),
    })
