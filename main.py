import yfinance as yf
import pandas as pd
import pandas_ta as ta
import pytz
import requests
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')

# CONFIG
TOKEN = "8218163213:AAEDXu19mXfeUSM65JIZAiBucxUAxmRHwy4"
CHAT_ID = "1432682636"
TZ_PARIS = pytz.timezone('Europe/Paris')

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text={message}"
    try: requests.get(url, timeout=10)
    except: pass

def run_sniper():
    now_paris = datetime.now(TZ_PARIS)
    h_dec = now_paris.hour + (now_paris.minute / 60)
    
    # Vérif session
    if not ((9.0 <= h_dec <= 13.0) or (14.5 <= h_dec <= 19.0)):
        print(f"[{now_paris.strftime('%H:%M')}] 🌙 Hors session. Repos.")
        return

    try:
        g_m5 = yf.download("GC=F", period="2d", interval="5m", progress=False, auto_adjust=True)
        g_h1 = yf.download("GC=F", period="10d", interval="1h", progress=False, auto_adjust=True)
        d_h1 = yf.download("DX-Y.NYB", period="10d", interval="1h", progress=False, auto_adjust=True)
        for df in [g_m5, g_h1, d_h1]:
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    except:
        print("Erreur Data")
        return

    # Stratégie
    ema_t = ta.ema(g_h1['Close'], length=200).iloc[-1]
    prix = g_m5['Close'].iloc[-1]
    ema20 = ta.ema(g_m5['Close'], length=20).iloc[-1]
    vol = g_m5['Volume'].iloc[-1]
    vol_m = g_m5['Volume'].rolling(window=20).mean().iloc[-1]
    k_dxy = ta.stoch(d_h1['High'], d_h1['Low'], d_h1['Close'])['STOCHk_14_3_3'].iloc[-1]

    # Signal
    cond_vol = vol > (vol_m * 0.8)
    retest = abs(prix - ema20) < 0.35

    if prix > ema_t and k_dxy > 20 and retest and cond_vol:
        send_telegram(f"🎯 ACHAT GOLD @ {prix:.2f}")
        print("Signal envoyé !")
    elif prix < ema_t and k_dxy < 80 and retest and cond_vol:
        send_telegram(f"📉 VENTE GOLD @ {prix:.2f}")
        print("Signal envoyé !")
    else:
        print(f"Scan @ {prix:.2f} : Pas de setup.")

if __name__ == "__main__":
    run_sniper()
