import logging
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from app import app
from scanner import run_scan
from signal_tracker import load as load_tracker
from telegram_notifier import send_startup, load_settings
from config import SCAN_INTERVAL

# Write logs to file AND console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(message)s',
    handlers=[
        logging.FileHandler('scanner.log'),
        logging.StreamHandler(),
    ]
)

load_tracker()
load_settings()
send_startup()

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(run_scan, 'interval', minutes=SCAN_INTERVAL, id='scan_job')
scheduler.start()

threading.Thread(target=run_scan, daemon=True).start()
