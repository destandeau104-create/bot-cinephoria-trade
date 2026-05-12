import yfinance as yf
import pandas_ta as ta
import pytz
import requests
import time
from datetime import datetime

# CONFIGURATION
TOKEN = "8218163213:AAEDXu19mXfeUSM65JIZAiBucxUAxmRHwy4"
CHAT_ID = "1432682636"
TZ_PARIS = pytz.timezone('Europe/Paris')

def run_bot():
    print("🚀 BOT GOLD V4.3 DÉMARRÉ SUR RENDER")
    while True:
        try:
            now = datetime.now(TZ_PARIS)
            h_dec = now.hour + (now.minute / 60)
            
            # Vérification Session (9h-13h / 14h30-19h)
            if (9.0 <= h_dec <= 13.0) or (14.5 <= h_dec <= 19.0):
                # 1. DATA
                g_m5 = yf.download("GC=F", period="2d", interval="5m", progress=False, auto_adjust=True)
                g_h1 = yf.download("GC=F", period="10d", interval="1h", progress=False, auto_adjust=True)
                dxy = yf.download("DX-Y.NYB", period="10d", interval="1h", progress=False, auto_adjust=True)
                
                for df in [g_m5, g_h1, dxy]:
                    if hasattr(df.columns, 'get_level_values'): df.columns = df.columns.get_level_values(0)

                # 2. INDICATEURS
                ema200_h1 = ta.ema(g_h1['Close'], length=200).iloc[-1]
                ema20_m5 = ta.ema(g_m5['Close'], length=20).iloc[-1]
                prix = g_m5['Close'].iloc[-1]
                k_dxy = ta.stoch(dxy['High'], dxy['Low'], dxy['Close'])['STOCHk_14_3_3'].iloc[-1]
                vol_ok = g_m5['Volume'].iloc[-1] > (g_m5['Volume'].rolling(20).mean().iloc[-1] * 0.8)

                # 3. LOGIQUE RETEST
                retest = abs(prix - ema20_m5) < 0.35
                
                if prix > ema200_h1 and k_dxy > 20 and retest and vol_ok:
                    requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text=🎯 ACHAT GOLD @ {prix:.2f}")
                    time.sleep(300) # Pause 5 min
                elif prix < ema200_h1 and k_dxy < 80 and retest and vol_ok:
                    requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text=📉 VENTE GOLD @ {prix:.2f}")
                    time.sleep(300)
            
            print(f"[{now.strftime('%H:%M')}] Scan OK - Prix: {g_m5['Close'].iloc[-1]:.2f}", end="\r")
            
        except Exception as e:
            print(f"\n⚠️ Erreur: {e}")
        
        time.sleep(60) # Relance toutes les minutes

if __name__ == "__main__":
    run_bot()
