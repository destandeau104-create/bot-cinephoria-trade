"""
DIAGNOSTIC GOLD RAISEFX - Decouverte symboles
Tourne une fois, liste tous les symboles, s'arrete
"""
import asyncio, os
from datetime import datetime, timezone

META_TOKEN = os.getenv("META_API_TOKEN", "")
META_ACCT  = os.getenv("META_ACCOUNT_ID", "7fed6592-a20e-4542-8720-52c9618f16e5")

# Noms possibles du Gold selon les brokers
GOLD_CANDIDATES = ["Gold", "GOLD", "XAUUSD", "XAUUSDm", "XAUUSD.", "XAUUSDc", "XAUUSD+"]

async def main():
    print("="*55, flush=True)
    print("DIAGNOSTIC SYMBOLES RAISEFX", flush=True)
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

    # ── Methode 1 : Terminal state symbols ───────────────────
    print("\n── METHODE 1 : Terminal State ──", flush=True)
    try:
        connection = account.get_rpc_connection()
        await connection.connect()
        await connection.wait_synchronized()
        symbols = await connection.get_symbols()
        if symbols:
            print("Symboles disponibles (" + str(len(symbols)) + ") :", flush=True)
            # Cherche Gold dans la liste
            gold_found = [s for s in symbols if "gold" in s.lower() or "xau" in s.lower()]
            if gold_found:
                print("GOLD TROUVE : " + str(gold_found), flush=True)
            else:
                print("Gold/XAU non trouve - liste complete :", flush=True)
                for s in sorted(symbols)[:50]:
                    print("  " + s, flush=True)
        else:
            print("Aucun symbole retourne", flush=True)
        await connection.close()
    except Exception as e:
        print("Terminal state erreur : " + str(e), flush=True)

    # ── Methode 2 : Test direct des candidats ────────────────
    print("\n── METHODE 2 : Test direct des noms ──", flush=True)
    for candidate in GOLD_CANDIDATES:
        try:
            now = datetime.now(timezone.utc)
            candles = await account.get_historical_candles(candidate, "5m", now, 3)
            if candles and len(candles) > 0:
                prix = float(candles[-1].get("close", 0))
                print("✅ FONCTIONNE : '" + candidate + "' -> prix=" + str(prix), flush=True)
            else:
                print("❌ Vide : '" + candidate + "'", flush=True)
        except Exception as e:
            err = str(e)[:60]
            print("❌ Erreur : '" + candidate + "' -> " + err, flush=True)
        await asyncio.sleep(1)

    print("\n" + "="*55, flush=True)
    print("DIAGNOSTIC TERMINE", flush=True)
    print("Utilise le symbole marque ✅ dans main.py", flush=True)
    print("="*55, flush=True)

if __name__ == "__main__":
    asyncio.run(main())
