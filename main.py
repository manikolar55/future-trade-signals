import threading
from apscheduler.schedulers.background import BackgroundScheduler
from app import app
from scanner import run_scan
from signal_tracker import load as load_tracker
from telegram_notifier import send_startup, load_settings
from config import SCAN_INTERVAL

if __name__ == '__main__':
    load_tracker()
    load_settings()
    send_startup()

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(run_scan, 'interval', minutes=SCAN_INTERVAL, id='scan_job')
    scheduler.start()

    initial = threading.Thread(target=run_scan, daemon=True)
    initial.start()

    print(f"")
    print(f"  Futures Signal Scanner")
    print(f"  Dashboard -> http://localhost:5000")
    print(f"  Scanning every {SCAN_INTERVAL} minutes")
    print(f"")

    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
