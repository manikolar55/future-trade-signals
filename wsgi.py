import threading
from apscheduler.schedulers.background import BackgroundScheduler
from app import app
from scanner import run_scan
from telegram_notifier import send_startup
from config import SCAN_INTERVAL

send_startup()

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(run_scan, 'interval', minutes=SCAN_INTERVAL, id='scan_job')
scheduler.start()

threading.Thread(target=run_scan, daemon=True).start()
