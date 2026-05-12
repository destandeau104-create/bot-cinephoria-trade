import os
import time
import threading
from datetime import datetime
import pytz
import pandas as pd
import yfinance as yf
import pandas_ta as ta
import telebot
from flask import Flask

# ============================================================

# CONFIGURATION

# ============================================================

TOKEN   = “8794987935:AAECh2yzzM_g9dZ3ki3tlKC1UWdC44YOjCk”
CHAT_ID = “1432682636”
bot     = telebot.TeleBot(TOKEN)

PARIS_TZ        = pytz.timezone(“Europe/Paris”)
LOT_SIZE        = 0.50
STOP_LOSS_PTS   = 4.0
TAKE_PROFIT_PTS = 8.0

# ============================================================

# FLASK KEEP-ALIVE

# ============================================================

app = Flask(**name**)

@app.route(”/”)
def home():
return “Bot XAU/USD actif”, 200

@app.route(”/health”)
def health():
now = datetime.now(PARIS_TZ).strftime(”%H:%M:%S”)
return “OK “ + now, 200

def run_flask():
print(“Flask demarre sur 0.0.0.0:8080”, flush=True)
app.run(host=“0.0.0.0”, port=8080, debug=False, use_reloader=False)

# ============================================================

# STRATEGIE (NE PAS MODIFIER)

# ============================================================

def is_in_session():
now = datetime.now(PARIS_TZ)
matin = (now.hour, now.minute) >= (9, 0) and (now.hour, now.minute) <= (11, 30)
aprem = (now.hour, now.minute) >= (14, 30) and (now.hour, now.minute) <= (17, 30)
return matin or aprem

def get_data(ticker, interval, period):
try:
df = yf.download(
ticker,
interval=interval,
period=period,
progress=False,
auto_adjust=True
)
return df
except Exception as e:
print(“Erreur get_data “ + ticker + “ : “ + str(e), flush=True)
return pd.DataFrame()

def analyse_market():
# H4 et H1
df_h1 = get_data(“XAUUSD=X”, “1h”, “20d”)
if len(df_h1) < 200:
print(“df_h1 insuffisant : “ + str(len(df_h1)) + “ bougies”, flush=True)
return None

```
ema200_h4 = ta.ema(df_h1["Close"].resample("4h").last().dropna(), length=200)
ema50_h1  = ta.ema(df_h1["Close"], length=50)

if ema200_h4 is None or ema50_h1 is None:
    print("EMA calcul echoue", flush=True)
    return None

# M5 et M15
df_m5 = get_data("XAUUSD=X", "5m", "2d")
if df_m5.empty:
    print("df_m5 vide", flush=True)
    return None

rsi_m15 = ta.rsi(df_m5["Close"].resample("15m").last().dropna(), length=14)
rsi_m5  = ta.rsi(df_m5["Close"], length=14)

if rsi_m15 is None or rsi_m5 is None:
    print("RSI calcul echoue", flush=True)
    return None

# Volume GLD
df_gld = get_data("GLD", "5m", "2d")
if df_gld.empty:
    print("GLD vide", flush=True)
    return None

vol_sma = df_gld["Volume"].rolling(20).mean()

# Valeurs actuelles
p         = float(df_m5["Close"].iloc[-1])
e200      = float(ema200_h4.iloc[-1])
e50       = float(ema50_h1.iloc[-1])
r15       = float(rsi_m15.iloc[-1])
r5_prev   = float(rsi_m5.iloc[-2])
r5_curr   = float(rsi_m5.iloc[-1])
vol_curr  = float(df_gld["Volume"].iloc[-1])
vol_avg   = float(vol_sma.iloc[-1])

print(
    "Prix=" + str(round(p, 2)) +
    " EMA200H4=" + str(round(e200, 2)) +
    " EMA50H1=" + str(round(e50, 2)) +
    " RSI15=" + str(round(r15, 1)) +
    " RSI5=" + str(round(r5_curr, 1)) +
    " Vol=" + str(round(vol_curr, 0)) +
    " VolSMA=" + str(round(vol_avg, 0)),
    flush=True
)

# Signal BUY
if (
    p > e200 and
    p > e50 and
    r15 > 50 and
    r5_prev < 55 and
    r5_curr >= 55 and
    vol_curr > 1.2 * vol_avg
):
    return {
        "dir": "BUY",
        "p":   p,
        "sl":  round(p - STOP_LOSS_PTS, 2),
        "tp":  round(p + TAKE_PROFIT_PTS, 2),
    }

# Signal SELL
if (
    p < e200 and
    p < e50 and
    r15 < 50 and
    r5_prev > 45 and
    r5_curr <= 45 and
    vol_curr > 1.2 * vol_avg
):
    return {
        "dir": "SELL",
        "p":   p,
        "sl":  round(p + STOP_LOSS_PTS, 2),
        "tp":  round(p - TAKE_PROFIT_PTS, 2),
    }

return None
```

# ============================================================

# BOUCLE DE TRADING

# ============================================================

def trading_loop():
print(“Boucle de trading demarree”, flush=True)

```
while True:
    try:
        now_str = datetime.now(PARIS_TZ).strftime("%H:%M")
        print("[" + now_str + "] Verification...", flush=True)

        if is_in_session():
            print("[" + now_str + "] Session active - analyse en cours", flush=True)
            signal = analyse_market()

            if signal:
                direction = "ACHAT" if signal["dir"] == "BUY" else "VENTE"
                emoji     = "BUY" if signal["dir"] == "BUY" else "SELL"
                msg = (
                    "SIGNAL XAU/USD - " + direction + "\n"
                    "Entree : " + str(signal["p"]) + "\n"
                    "Stop   : " + str(signal["sl"]) + "\n"
                    "Cible  : " + str(signal["tp"]) + "\n"
                    "Lot    : " + str(LOT_SIZE)
                )
                bot.send_message(CHAT_ID, msg)
                print("[" + now_str + "] Signal envoye : " + emoji + " @ " + str(signal["p"]), flush=True)
            else:
                print("[" + now_str + "] Pas de signal", flush=True)
        else:
            print("[" + now_str + "] Hors session", flush=True)

        time.sleep(300)

    except Exception as e:
        print("ERREUR : " + str(e), flush=True)
        time.sleep(60)
```

# ============================================================

# LANCEMENT

# ============================================================

if **name** == “**main**”:
print(“Demarrage du bot XAU/USD…”, flush=True)

```
flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()

time.sleep(2)
print("Flask actif - lancement boucle trading", flush=True)

trading_loop()
```
