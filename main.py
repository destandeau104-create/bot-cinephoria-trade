import os
import time
import logging
import threading
from datetime import datetime, timedelta
import pytz
import requests
import pandas as pd
import yfinance as yf
import pandas_ta as ta
import telebot
from flask import Flask

# ─────────────────────────────────────────────
#  SERVEUR KEEP-ALIVE (Inclus directement ici)
# ─────────────────────────────────────────────
app = Flask('')
@app.route('/')
def home(): return "Bot XAU/USD en ligne !"

def run_server():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run_server)
    t.daemon = True
    t.start()

# ─────────────────────────────────────────────
#  CONFIGURATION & LOGS
# ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN   = "8794987935:AAECh2yzzM_g9dZ3ki3tlKC1UWdC44YOjCk"
TELEGRAM_CHAT_ID = "1432682636"

# INITIALISATION DU BOT (C'ÉTAIT LA LIGNE MANQUANTE)
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# MONEY MANAGEMENT
ACCOUNT_SIZE   = 40_000
RISK_PER_TRADE = 200
STOP_LOSS_PTS  = 4.0
TAKE_PROFIT_PTS = 8.0
PIP_VALUE      = 100
LOT_SIZE = round(RISK_PER_TRADE / (STOP_LOSS_PTS * PIP_VALUE), 2)

# PARAMÈTRES STRATÉGIE
RSI_PERIOD, EMA_H4_PERIOD, EMA_H1_PERIOD = 14, 200, 50
VOL_SMA_PERIOD, VOL_MULTIPLIER = 20, 1.2
RSI_BUY_CROSS, RSI_SELL_CROSS, RSI_M15_MID = 55, 45, 50
COOLDOWN_MINUTES = 15
PARIS_TZ = pytz.timezone("Europe/Paris")
SESSION_WINDOWS = [(9, 0, 11, 30), (14, 30, 17, 30)]

# ─────────────────────────────────────────────
#  FONCTIONS UTILES
# ─────────────────────────────────────────────
def is_in_session():
    now = datetime.now(PARIS_TZ)
    for h_s, m_s, h_e, m_e in SESSION_WINDOWS:
        start = now.replace(hour=h_s, minute=m_s, second=0, microsecond=0)
        end = now.replace(hour=h_e, minute=m_e, second=0, microsecond=0)
        if start <= now <= end: return True
    return False

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
        return True
    except: return False

def format_signal_message(direction, price, sl, tp, lot):
    arrow = "🟢 ACHAT" if direction == "BUY" else "🔴 VENTE"
    return (f"<b>⚡ SIGNAL XAU/USD — {arrow}</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 <b>Entrée :</b> {price:.2f}\n🛑 <b>SL :</b> {sl:.2f}\n🎯 <b>TP :</b> {tp:.2f}\n"
            f"📦 <b>Lot :</b> {lot}\n━━━━━━━━━━━━━━━━━━━━\n✅ <i>Volume confirmé par ETF GLD</i>")

def fetch_ohlcv(ticker, interval, period):
    try:
        return yf.download(ticker, interval=interval, period=period, progress=False, auto_adjust=True)
    except: return pd.DataFrame()

# ─────────────────────────────────────────────
#  LOGIQUE D'ANALYSE
# ─────────────────────────────────────────────
def analyse():
    df_h4 = fetch_ohlcv("XAUUSD=X", "1h", "60d")
    if df_h4.empty: return None
    df_h4 = df_h4.resample("4h").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()
    
    p_h4 = df_h4["Close"].iloc[-1]
    ema_h4 = ta.ema(df_h4["Close"].squeeze(), length=EMA_H4_PERIOD).iloc[-1]
    
    df_h1 = fetch_ohlcv("XAUUSD=X", "1h", "30d")
    ema_h1 = ta.ema(df_h1["Close"].squeeze(), length=EMA_H1_PERIOD).iloc[-1]
    p_h1 = df_h1["Close"].iloc[-1]

    df_m15 = fetch_ohlcv("XAUUSD=X", "15m", "5d")
    rsi_m15 = ta.rsi(df_m15["Close"].squeeze(), length=RSI_PERIOD).iloc[-1]

    df_m5 = fetch_ohlcv("XAUUSD=X", "5m", "2d")
    rsi_m5 = ta.rsi(df_m5["Close"].squeeze(), length=RSI_PERIOD)
    
    # Volume GLD
    df_gld = fetch_ohlcv("GLD", "5m", "2d")
    vols = df_gld["Volume"]
    vol_ok = vols.iloc[-1] > (vols.rolling(VOL_SMA_PERIOD).mean().iloc[-1] * VOL_MULTIPLIER)

    price_now = df_m5["Close"].iloc[-1]
    r_prev, r_last = rsi_m5.iloc[-2], rsi_m5.iloc[-1]

    if p_h4 > ema_h4 and p_h1 > ema_h1 and rsi_m15 > 50 and r_prev < 55 and r_last >= 55 and vol_ok:
        return {"direction": "BUY", "price": price_now, "sl": price_now - 4, "tp": price_now + 8}
    if p_h4 < ema_h4 and p_h1 < ema_h1 and rsi_m15 < 50 and r_prev > 45 and r_last <= 45 and vol_ok:
        return {"direction": "SELL", "price": price_now, "sl": price_now + 4, "tp": price_now - 8}
    return None

# ─────────────────────────────────────────────
#  BOUCLE PRINCIPALE
# ─────────────────────────────────────────────
def main_loop():
    logger.info("🚀 Boucle de trading active")
    last_sig_time, last_dir = None, None
    while True:
        try:
            if is_in_session():
                sig = analyse()
                if sig:
                    now = datetime.now(PARIS_TZ)
                    if not (last_sig_time and last_dir == sig["direction"] and (now - last_sig_time).seconds < 900):
                        msg = format_signal_message(sig["direction"], sig["price"], sig["sl"], sig["tp"], LOT_SIZE)
                        send_telegram(msg)
                        last_sig_time, last_dir = now, sig["direction"]
            time.sleep(300)
        except Exception as e:
            logger.error(f"Erreur : {e}")
            time.sleep(60)

if __name__ == "__main__":
    print("--- DÉMARRAGE DU BOT ---")
    keep_alive() # Lance le serveur web
    
    # Lancement Telegram en arrière-plan
    t = threading.Thread(target=lambda: bot.infinity_polling())
    t.daemon = True
    t.start()
    print("✅ Telegram OK")
    
    # Lancement Trading
    main_loop()
