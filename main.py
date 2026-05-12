import os
import time
import threading
from datetime import datetime
import pytz
import pandas as pd
import numpy as np
import yfinance as yf
import telebot
from flask import Flask

TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
bot     = telebot.TeleBot(TOKEN)

PARIS_TZ         = pytz.timezone("Europe/Paris")
LOT_SIZE         = 0.50
TAKE_PROFIT_PTS  = 8.0
ATR_PERIOD       = 14
ATR_SPIKE_MULT   = 2.5
SL_ATR_MULT      = 1.5
SL_MIN_PIPS      = 15.0
SL_MAX_PIPS      = 100.0

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot XAU/USD actif", 200

@app.route("/health")
def health():
    now = datetime.now(PARIS_TZ).strftime("%H:%M:%S")
    return "OK " + now, 200

def run_flask():
    print("Flask demarre sur 0.0.0.0:8080", flush=True)
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)

def calc_ema(series, length):
    return series.ewm(span=length, adjust=False).mean()

def calc_rsi(series, length=14):
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_g = gain.ewm(com=length - 1, adjust=False).mean()
    avg_l = loss.ewm(com=length - 1, adjust=False).mean()
    rs    = avg_g / avg_l.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calc_atr(df, period=14):
    high  = df["High"].squeeze()
    low   = df["Low"].squeeze()
    close = df["Close"].squeeze()
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def is_in_session():
    now  = datetime.now(PARIS_TZ)
    h, m = now.hour, now.minute
    return ((h, m) >= (9, 0) and (h, m) <= (11, 30)) or ((h, m) >= (14, 30) and (h, m) <= (17, 30))

def get_data(ticker, interval, period):
    try:
        return yf.download(ticker, interval=interval, period=period, progress=False, auto_adjust=True)
    except Exception as e:
        print("Erreur get_data " + ticker + " : " + str(e), flush=True)
        return pd.DataFrame()

def analyse_market():
    # === DONNEES H1 ===
    df_h1 = get_data("XAUUSD=X", "1h", "20d")
    if len(df_h1) < 200:
        print("df_h1 insuffisant : " + str(len(df_h1)), flush=True)
        return None

    close_h1  = df_h1["Close"].squeeze()
    ema200_h4 = calc_ema(close_h1.resample("4h").last().dropna(), 200)
    ema50_h1  = calc_ema(close_h1, 50)

    # === DONNEES M5 ===
    df_m5 = get_data("XAUUSD=X", "5m", "2d")
    if df_m5.empty or len(df_m5) < 20:
        print("df_m5 vide ou insuffisant", flush=True)
        return None

    # REGLE 1 : iloc[-2] = derniere bougie cloturee confirmee
    close_m5 = df_m5["Close"].squeeze()
    open_m5  = df_m5["Open"].squeeze()
    high_m5  = df_m5["High"].squeeze()
    low_m5   = df_m5["Low"].squeeze()

    rsi_m15  = calc_rsi(close_m5.resample("15min").last().dropna(), 14)
    rsi_m5   = calc_rsi(close_m5, 14)

    # === DONNEES GLD ===
    df_gld = get_data("GLD", "5m", "2d")
    if df_gld.empty:
        print("GLD vide", flush=True)
        return None

    vol_sma = df_gld["Volume"].squeeze().rolling(20).mean()

    # === VALEURS SUR BOUGIE CLOTUREE ===
    p        = float(close_m5.iloc[-2])
    o        = float(open_m5.iloc[-2])
    h        = float(high_m5.iloc[-2])
    l        = float(low_m5.iloc[-2])
    e200     = float(ema200_h4.iloc[-1])
    e50      = float(ema50_h1.iloc[-1])
    r15      = float(rsi_m15.iloc[-1])
    r5_prev  = float(rsi_m5.iloc[-3])
    r5_curr  = float(rsi_m5.iloc[-2])
    vol_curr = float(df_gld["Volume"].squeeze().iloc[-2])
    vol_avg  = float(vol_sma.iloc[-2])

    # === FILTRE 1 : ANTI-PANIQUE (2.5 x ATR) ===
    atr_val     = float(calc_atr(df_m5, ATR_PERIOD).iloc[-2])
    candle_size = h - l
    if candle_size > ATR_SPIKE_MULT * atr_val:
        print(
            "Bougie de panique ignoree : taille=" + str(round(candle_size, 2)) +
            " seuil=" + str(round(ATR_SPIKE_MULT * atr_val, 2)),
            flush=True
        )
        return None

    # === CALCUL SL DYNAMIQUE (1.5 x ATR) ===
    sl_raw = SL_ATR_MULT * atr_val

    # Cascade SL : min 15 pips, max 100 pips (1 pip XAU = 0.10$)
    sl_pips = sl_raw * 10
    if sl_pips < SL_MIN_PIPS:
        sl_pips = SL_MIN_PIPS
        print("SL trop petit, force a " + str(SL_MIN_PIPS) + " pips", flush=True)
    if sl_pips > SL_MAX_PIPS:
        print("SL trop grand (" + str(round(sl_pips, 1)) + " pips) - signal annule", flush=True)
        return None

    sl_pts = sl_pips / 10.0

    print(
        "Prix=" + str(round(p, 2)) +
        " Open=" + str(round(o, 2)) +
        " EMA200H4=" + str(round(e200, 2)) +
        " EMA50H1=" + str(round(e50, 2)) +
        " RSI15=" + str(round(r15, 1)) +
        " RSI5=" + str(round(r5_curr, 1)) +
        " ATR=" + str(round(atr_val, 2)) +
        " SL=" + str(round(sl_pips, 1)) + "pips",
        flush=True
    )

    # === SIGNAL BUY ===
    # Conditions EMA + Volume + RSI
    # REGLE 2 : bougie verte (Close > Open)
    if (
        p > e200 and
        p > e50 and
        r15 > 50 and
        r5_prev < 55 and
        r5_curr >= 55 and
        vol_curr > 1.2 * vol_avg and
        p > o
    ):
        sl = round(p - sl_pts, 2)
        tp = round(p + TAKE_PROFIT_PTS, 2)
        return {"dir": "BUY", "p": p, "sl": sl, "tp": tp, "sl_pips": round(sl_pips, 1)}

    # === SIGNAL SELL ===
    # REGLE 2 : bougie rouge (Close < Open)
    if (
        p < e200 and
        p < e50 and
        r15 < 50 and
        r5_prev > 45 and
        r5_curr <= 45 and
        vol_curr > 1.2 * vol_avg and
        p < o
    ):
        sl = round(p + sl_pts, 2)
        tp = round(p - TAKE_PROFIT_PTS, 2)
        return {"dir": "SELL", "p": p, "sl": sl, "tp": tp, "sl_pips": round(sl_pips, 1)}

    return None

def wait_for_candle_close():
    now     = datetime.now(PARIS_TZ)
    seconds = now.second + (now.minute % 5) * 60
    wait    = 300 - seconds
    if wait <= 2:
        wait += 300
    print("Prochaine fermeture M5 dans " + str(wait) + "s", flush=True)
    time.sleep(wait)

def trading_loop():
    print("Boucle de trading demarree", flush=True)
    while True:
        try:
            wait_for_candle_close()
            now_str = datetime.now(PARIS_TZ).strftime("%H:%M")
            print("[" + now_str + "] Bougie M5 fermee - verification...", flush=True)
            if is_in_session():
                print("[" + now_str + "] Session active - analyse en cours", flush=True)
                signal = analyse_market()
                if signal:
                    direction = "ACHAT" if signal["dir"] == "BUY" else "VENTE"
                    msg = (
                        "SIGNAL XAU/USD - " + direction + "\n" +
                        "Entree : " + str(signal["p"]) + "\n" +
                        "Stop   : " + str(signal["sl"]) + " (" + str(signal["sl_pips"]) + " pips)\n" +
                        "Cible  : " + str(signal["tp"]) + "\n" +
                        "Lot    : " + str(LOT_SIZE)
                    )
                    bot.send_message(CHAT_ID, msg)
                    print("[" + now_str + "] Signal envoye : " + signal["dir"], flush=True)
                else:
                    print("[" + now_str + "] Pas de signal", flush=True)
            else:
                print("[" + now_str + "] Hors session", flush=True)
        except Exception as e:
            print("ERREUR : " + str(e), flush=True)
            time.sleep(60)

if __name__ == "__main__":
    print("Demarrage du bot XAU/USD...", flush=True)
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    time.sleep(2)
    print("Flask actif - lancement boucle trading", flush=True)

    # Message de confirmation au demarrage / redeploi
    now_start = datetime.now(PARIS_TZ).strftime("%d/%m/%Y a %H:%M")
    msg_start = (
        "Bot XAU/USD demarre\\n" +
        "Date : " + now_start + "\\n" +
        "Lot : " + str(LOT_SIZE) + "\\n" +
        "SL : 1.5x ATR (min 15 pips, max 100 pips)\\n" +
        "TP : " + str(TAKE_PROFIT_PTS) + " pts\\n" +
        "Sessions : 09h-11h30 et 14h30-17h30\\n" +
        "Filtres : Anti-panique ATR x2.5 actif\\n" +
        "Statut : En attente de signal..."
    )
    try:
        bot.send_message(CHAT_ID, msg_start)
        print("Message de demarrage envoye sur Telegram", flush=True)
    except Exception as e:
        print("Erreur envoi message demarrage : " + str(e), flush=True)

    trading_loop()
