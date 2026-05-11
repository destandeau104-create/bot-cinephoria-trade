import os
import time
import logging
import threading
from datetime import datetime
import pytz
import requests
import pandas as pd
import yfinance as yf
import pandas_ta as ta
import telebot
from flask import Flask

# 1. CONFIGURATION
TOKEN = "8794987935:AAECh2yzzM_g9dZ3ki3tlKC1UWdC44YOjCk"
CHAT_ID = "1432682636"
bot = telebot.TeleBot(TOKEN)

# 2. SERVEUR POUR RENDER
app = Flask('')
@app.route('/')
def home(): return "Bot XAU/USD Stratégie Active"

def run_web():
    app.run(host='0.0.0.0', port=8080)

# 3. PARAMÈTRES DE STRATÉGIE
PARIS_TZ = pytz.timezone("Europe/Paris")
LOT_SIZE = 0.50
STOP_LOSS_PTS = 4.0
TAKE_PROFIT_PTS = 8.0

def is_in_session():
    now = datetime.now(PARIS_TZ)
    # Session Paris: 09:00-11:30 et 14:30-17:30
    return (9, 0) <= (now.hour, now.minute) <= (11, 30) or (14, 30) <= (now.hour, now.minute) <= (17, 30)

# 4. FONCTIONS D'ANALYSE
def get_data(ticker, interval, period):
    try:
        return yf.download(ticker, interval=interval, period=period, progress=False, auto_adjust=True)
    except: return pd.DataFrame()

def analyse_market():
    print(f"🔎 Analyse en cours... ({datetime.now(PARIS_TZ).strftime('%H:%M')})")
    
    # H4 & H1
    df_h1 = get_data("XAUUSD=X", "1h", "20d")
    if len(df_h1) < 200: return None
    
    ema200_h4 = ta.ema(df_h1['Close'].resample('4h').last().dropna(), length=200)
    ema50_h1 = ta.ema(df_h1['Close'], length=50)
    
    # M15 & M5
    df_m5 = get_data("XAUUSD=X", "5m", "2d")
    rsi_m15 = ta.rsi(df_m5['Close'].resample('15m').last().dropna(), length=14)
    rsi_m5 = ta.rsi(df_m5['Close'], length=14)
    
    # Volume GLD
    df_gld = get_data("GLD", "5m", "2d")
    if df_gld.empty: return None
    vol_sma = df_gld['Volume'].rolling(20).mean()
    
    # Prix actuels
    p = df_m5['Close'].iloc[-1]
    
    # CONDITIONS ACHAT
    if (p > ema200_h4.iloc[-1] and p > ema50_h1.iloc[-1] and rsi_m15.iloc[-1] > 50 and 
        rsi_m5.iloc[-2] < 55 and rsi_m5.iloc[-1] >= 55 and df_gld['Volume'].iloc[-1] > 1.2 * vol_sma.iloc[-1]):
        return {"dir": "BUY", "p": p, "sl": p - STOP_LOSS_PTS, "tp": p + TAKE_PROFIT_PTS}

    # CONDITIONS VENTE
    if (p < ema200_h4.iloc[-1] and p < ema50_h1.iloc[-1] and rsi_m15.iloc[-1] < 50 and 
        rsi_m5.iloc[-2] > 45 and rsi_m5.iloc[-1] <= 45 and df_gld['Volume'].iloc[-1] > 1.2 * vol_sma.iloc[-1]):
        return {"dir": "SELL", "p": p, "sl": p + STOP_LOSS_PTS, "tp": p - TAKE_PROFIT_PTS}

    return None

# 5. BOUCLE PRINCIPALE
def trading_loop():
    last_signal_time = 0
    while True:
        try:
            if is_in_session():
                signal = analyse_market()
                if signal and (time.time() - last_signal_time > 900): # Cooldown 15min
                    emoji = "🟢 ACHAT" if signal['dir'] == "BUY" else "🔴 VENTE"
                    msg = (f"<b>⚡ SIGNAL XAU/USD — {emoji}</b>\n"
                           f"📍 Entrée : {signal['p']:.2f}\n🛑 SL : {signal['sl']:.2f}\n"
                           f"🎯 TP : {signal['tp']:.2f}\n📦 Volume : {LOT_SIZE} lot(s)\n"
                           f"✅ Volume confirmé par ETF GLD")
                    bot.send_message(CHAT_ID, msg, parse_mode="HTML")
                    last_signal_time = time.time()
            else:
                print("🕐 Hors session Paris (Repos)")
            
            time.sleep(300) # Scan toutes les 5 minutes
        except Exception as e:
            print(f"❌ Erreur: {e}")
            time.sleep(60)

# 6. DÉMARRAGE
if __name__ == "__main__":
    print("--- DÉMARRAGE STRATÉGIE INSTITUTIONNELLE ---")
    threading.Thread(target=run_web, daemon=True).start()
    
    # Message de confirmation au lancement
    bot.send_message(CHAT_ID, "🚀 Stratégie réactivée : Analyse XAUUSD/GLD en cours...")
    
    trading_loop()
