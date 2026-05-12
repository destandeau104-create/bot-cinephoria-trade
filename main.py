import os
import time
import threading
from datetime import datetime
import pytz
import requests
import pandas as pd
import yfinance as yf
import pandas_ta as ta
import telebot
from flask import Flask

# ════════════════════════════════════════════

# 1. CONFIGURATION

# ════════════════════════════════════════════

TOKEN   = "8794987935:AAECh2yzzM_g9dZ3ki3tlKC1UWdC44YOjCk"
CHAT_ID = "1432682636"
bot     = telebot.TeleBot(TOKEN)

# ════════════════════════════════════════════

# 2. PARAMÈTRES DE STRATÉGIE

# ════════════════════════════════════════════

PARIS_TZ       = pytz.timezone("Europe/Paris")
LOT_SIZE       = 0.50
STOP_LOSS_PTS  = 4.0
TAKE_PROFIT_PTS = 8.0

# ════════════════════════════════════════════

# 3. FLASK KEEP-ALIVE (obligatoire sur Render)

# ════════════════════════════════════════════

app = Flask(**name**)

@app.route("/")
def home():
return "Gold Bot actif ✅", 200

@app.route("/health")
def health():
now = datetime.now(PARIS_TZ).strftime("%H:%M:%S")
return f"OK — {now}", 200

def run_flask():
print("Flask démarré sur 0.0.0.0:8080", flush=True)
app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)

# ════════════════════════════════════════════

# 4. STRATÉGIE (INTACTE — ne pas modifier)

# ════════════════════════════════════════════

def is_in_session():
now = datetime.now(PARIS_TZ)
return (
(9, 0) <= (now.hour, now.minute) <= (11, 30) or
(14, 30) <= (now.hour, now.minute) <= (17, 30)
)

def get_data(ticker, interval, period):
try:
df = yf.download(
ticker, interval=interval, period=period,
progress=False, auto_adjust=True
)
return df
except Exception as e:
print(f"[get_data] Erreur {ticker} {interval} : {e}", flush=True)
return pd.DataFrame()

def analyse_market():
# ── H4 & H1
df_h1 = get_data("XAUUSD=X", "1h", "20d")
if len(df_h1) < 200:
print("[analyse] df_h1 insuffisant", flush=True)
return None

```
ema200_h4 = ta.ema(df_h1["Close"].resample("4h").last().dropna(), length=200)
ema50_h1  = ta.ema(df_h1["Close"], length=50)

# ── M15 & M5
df_m5   = get_data("XAUUSD=X", "5m", "2d")
rsi_m15 = ta.rsi(df_m5["Close"].resample("15m").last().dropna(), length=14)
rsi_m5  = ta.rsi(df_m5["Close"], length=14)

# ── Volume GLD
df_gld = get_data("GLD", "5m", "2d")
if df_gld.empty:
    print("[analyse] GLD vide", flush=True)
    return None

vol_sma = df_gld["Volume"].rolling(20).mean()
p       = float(df_m5["Close"].iloc[-1])

print(
    f"[analyse] Prix={p:.2f} "
    f"EMA200H4={float(ema200_h4.iloc[-1]):.2f} "
    f"EMA50H1={float(ema50_h1.iloc[-1]):.2f} "
    f"RSI15={float(rsi_m15.iloc[-1]):.1f} "
    f"RSI5={float(rsi_m5.iloc[-1]):.1f}",
    flush=True
)

# ── Signal BUY
if (
    p > float(ema200_h4.iloc[-1]) and
    p > float(ema50_h1.iloc[-1])  and
    float(rsi_m15.iloc[-1]) > 50  and
    float(rsi_m5.iloc[-2])  < 55  and
    float(rsi_m5.iloc[-1])  >= 55 and
    float(df_gld["Volume"].iloc[-1]) > 1.2 * float(vol_sma.iloc[-1])
):
    return {
        "dir": "BUY",
        "p":   p,
        "sl":  p - STOP_LOSS_PTS,
        "tp":  p + TAKE_PROFIT_PTS,
    }

# ── Signal SELL
if (
    p < float(ema200_h4.iloc[-1]) and
    p < float(ema50_h1.iloc[-1])  and
    float(rsi_m15.iloc[-1]) < 50  and
    float(rsi_m5.iloc[-2])  > 45  and
    float(rsi_m5.iloc[-1])  <= 45 and
    float(df_gld["Volume"].iloc[-1]) > 1.2 * float(vol_sma.iloc[-1])
):
    return {
        "dir": "SELL",
        "p":   p,
        "sl":  p + STOP_LOSS_PTS,
        "tp":  p - TAKE_PROFIT_PTS,
    }

return None
```

# ════════════════════════════════════════════

# 5. BOUCLE DE TRADING

# ════════════════════════════════════════════

def trading_loop():
print("Boucle de trading démarrée", flush=True)

```
while True:
    try:
        now = datetime.now(PARIS_TZ).strftime("%H:%M")
        print(f"[{now}] Vérification session...", flush=True)

        if is_in_session():
            print(f"[{now}] Session active — analyse en cours...", flush=True)
            signal = analyse_market()

            if signal:
                emoji = "🟢 ACHAT" if signal["dir"] == "BUY" else "🔴 VENTE"
                msg = (
                    f"⚡ SIGNAL XAU/USD — {emoji}\n"
                    f"Entrée  : {signal['p']:.2f}\n"
                    f"Stop    : {signal['sl']:.2f}\n"
                    f"Cible   : {signal['tp']:.2f}\n"
                    f"Lot     : {LOT_SIZE}"
                )
                bot.send_message(CHAT_ID, msg, parse_mode="HTML")
                print(f"[{now}] Signal envoyé : {signal['dir']} @ {signal['p']:.2f}", flush=True)
            else:
                print(f"[{now}] Pas de signal", flush=True)
        else:
            print(f"[{now}] Hors session", flush=True)

        time.sleep(300)  # Attente 5 minutes

    except Exception as e:
        print(f"[ERREUR] {e}", flush=True)
        time.sleep(60)
```

# ════════════════════════════════════════════

# 6. LANCEMENT (Flask + Trading en parallèle)

# ════════════════════════════════════════════

if **name** == "**main**":
print("Démarrage Gold Bot…", flush=True)

```
# Flask dans un thread séparé (daemon=True → s'arrête avec le programme)
flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()

# Petite pause pour laisser Flask démarrer
time.sleep(2)
print("Flask actif, lancement de la boucle trading...", flush=True)

# Boucle trading dans le thread principal
trading_loop()
```
