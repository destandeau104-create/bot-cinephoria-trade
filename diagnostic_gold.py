"""
DIAGNOSTIC GOLD RAISEFX
Script unique - tourne une seule fois et s'arrete
Affiche les vraies valeurs pour calibrer le bot
"""
import asyncio, os
import pandas as pd
import numpy as np
from datetime import datetime, timezone

META_TOKEN = os.getenv("META_API_TOKEN", "")
META_ACCT  = os.getenv("META_ACCOUNT_ID", "7fed6592-a20e-4542-8720-52c9618f16e5")
SYMBOL     = "Gold"

async def main():
    print("="*55, flush=True)
    print("DIAGNOSTIC GOLD RAISEFX", flush=True)
    print("="*55, flush=True)

    if not META_TOKEN:
        print("ERREUR : META_API_TOKEN manquant", flush=True)
        return

    try:
        from metaapi_cloud_sdk import MetaApi
    except ImportError:
        print("ERREUR : metaapi-cloud-sdk non installe", flush=True)
        return

    api     = MetaApi(META_TOKEN)
    account = await api.metatrader_account_api.get_account(META_ACCT)

    print("Connexion RaiseFX...", flush=True)
    await account.wait_connected()
    print("Connecte !", flush=True)

    # ── Prix en temps reel ───────────────────────────────────
    try:
        price = await account.get_symbol_price(SYMBOL)
        if price:
            bid = float(price.get("bid", 0))
            ask = float(price.get("ask", 0))
            print("\n── PRIX TEMPS REEL ──", flush=True)
            print("Bid    : " + str(bid), flush=True)
            print("Ask    : " + str(ask), flush=True)
            print("Spread : " + str(round(ask - bid, 5)) + " points", flush=True)
    except Exception as e:
        print("Prix erreur : " + str(e), flush=True)

    # ── Bougies M5 ──────────────────────────────────────────
    try:
        now = datetime.now(timezone.utc)
        candles = await account.get_historical_candles(SYMBOL, "5m", now, 50)
        if candles:
            rows = []
            for c in candles:
                try:
                    rows.append({
                        "Open":   float(c.get("open",  0)),
                        "High":   float(c.get("high",  0)),
                        "Low":    float(c.get("low",   0)),
                        "Close":  float(c.get("close", 0)),
                    })
                except Exception: continue
            df = pd.DataFrame(rows)
            if not df.empty:
                df["range"] = df["High"] - df["Low"]
                h  = df["High"]
                l  = df["Low"]
                c  = df["Close"]
                tr = pd.concat([
                    h - l,
                    (h - c.shift()).abs(),
                    (l - c.shift()).abs()
                ], axis=1).max(axis=1)
                atr = float(tr.rolling(14, min_periods=14).median().iloc[-1])
                print("\n── BOUGIES M5 (50 dernieres) ──", flush=True)
                print("Prix actuel  : " + str(round(float(df["Close"].iloc[-1]), 5)), flush=True)
                print("Range moyen  : " + str(round(float(df["range"].mean()), 5)) + " points", flush=True)
                print("Range max    : " + str(round(float(df["range"].max()), 5)) + " points", flush=True)
                print("Range min    : " + str(round(float(df["range"].min()), 5)) + " points", flush=True)
                print("ATR 14 M5    : " + str(round(atr, 5)) + " points", flush=True)
                print("\n── CALIBRAGE RECOMMANDE ──", flush=True)
                # On deduit le pip du nombre de decimales du prix
                prix_str   = str(float(df["Close"].iloc[-1]))
                decimales  = len(prix_str.split(".")[1]) if "." in prix_str else 0
                pip_calc   = 10 ** (-decimales)
                atr_pips   = round(atr / pip_calc, 1)
                sl_min_rec = round(atr_pips * 1.5, 0)
                sl_max_rec = round(atr_pips * 15, 0)
                retest_rec = round(atr * 0.30, 5)
                print("Decimales    : " + str(decimales), flush=True)
                print("PIP calcule  : " + str(pip_calc), flush=True)
                print("ATR en pips  : " + str(atr_pips) + " pips", flush=True)
                print("SL_MIN_PIPS  : " + str(sl_min_rec) + " (ATR x1.5)", flush=True)
                print("SL_MAX_PIPS  : " + str(sl_max_rec) + " (ATR x15)", flush=True)
                print("RETEST_THRESH: " + str(retest_rec) + " (ATR x30%)", flush=True)
                print("\n── COLLE CES VALEURS DANS main.py ──", flush=True)
                print("PIP_GOLD        = " + str(pip_calc), flush=True)
                print("SL_MIN_PIPS     = " + str(sl_min_rec), flush=True)
                print("SL_MAX_PIPS     = " + str(sl_max_rec), flush=True)
                print("RETEST_THRESH   = " + str(retest_rec), flush=True)
    except Exception as e:
        print("Bougies erreur : " + str(e), flush=True)

    print("\n" + "="*55, flush=True)
    print("DIAGNOSTIC TERMINE - bot peut s'arreter", flush=True)
    print("="*55, flush=True)

if __name__ == "__main__":
    asyncio.run(main())
