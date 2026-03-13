import os
import time
import requests
import random
from datetime import datetime

from telegram.ext import Updater, CommandHandler

print("🚀 BOT RADAR ULTRA INICIANDO...")

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not TOKEN:
    print("❌ BOT_TOKEN não encontrado")
    exit()

# ------------------------------
# CONFIG
# ------------------------------

API_URL = "https://api.binance.com/api/v3/klines"

SCAN_COINS = [
"BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT",
"ADAUSDT","DOGEUSDT","AVAXUSDT","LINKUSDT","DOTUSDT"
]

TIMEFRAMES = {
"1m":"1m",
"3m":"3m",
"5m":"5m"
}

# ------------------------------
# BINANCE DATA
# ------------------------------

def get_candles(symbol, interval="1m", limit=30):

    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }

    r = requests.get(API_URL, params=params, timeout=10)

    data = r.json()

    candles = []

    for c in data:
        candles.append({
            "open": float(c[1]),
            "close": float(c[4]),
            "high": float(c[2]),
            "low": float(c[3]),
            "volume": float(c[5])
        })

    return candles


# ------------------------------
# ANTI FAKE FILTER
# ------------------------------

def anti_fake(candles):

    closes = [c["close"] for c in candles]

    avg = sum(closes)/len(closes)

    last = closes[-1]

    if abs(last-avg)/avg > 0.03:
        return False

    return True


# ------------------------------
# SIGNAL LOGIC
# ------------------------------

def analyze(symbol):

    candles = get_candles(symbol)

    if not candles:
        return None

    if not anti_fake(candles):
        return None

    last = candles[-1]
    prev = candles[-2]

    direction = None

    if last["close"] > prev["close"]:
        direction = "CALL"

    if last["close"] < prev["close"]:
        direction = "PUT"

    if not direction:
        return None

    timeframe = random.choice(["1m","3m","5m"])

    return {
        "symbol":symbol,
        "direction":direction,
        "timeframe":timeframe
    }


# ------------------------------
# ASIAN SESSION RADAR
# ------------------------------

def asian_session():

    hour = datetime.utcnow().hour

    return hour >= 23 or hour <= 6


# ------------------------------
# SCANNER
# ------------------------------

def scan():

    signals = []

    for coin in SCAN_COINS:

        try:

            result = analyze(coin)

            if result:
                signals.append(result)

        except:
            pass

    return signals


# ------------------------------
# TELEGRAM
# ------------------------------

def start(update, context):

    update.message.reply_text(
        "🤖 BOT RADAR ULTRA ATIVO"
    )


def status(update, context):

    update.message.reply_text(
        "📡 Scanner rodando..."
    )


# ------------------------------
# MAIN LOOP
# ------------------------------

def radar(context):

    if not CHAT_ID:
        return

    print("🔎 Escaneando mercado...")

    signals = scan()

    if not signals:
        return

    for s in signals:

        msg = f"""
🚨 SINAL DETECTADO

MOEDA: {s['symbol']}
DIREÇÃO: {s['direction']}
TEMPO: {s['timeframe']}

Sessão Asiática: {"SIM" if asian_session() else "NÃO"}
"""

        context.bot.send_message(
            chat_id=CHAT_ID,
            text=msg
        )


# ------------------------------
# START BOT
# ------------------------------

updater = Updater(TOKEN)

dp = updater.dispatcher

dp.add_handler(CommandHandler("start", start))
dp.add_handler(CommandHandler("status", status))

job = updater.job_queue
job.run_repeating(radar, interval=60, first=10)

print("✅ BOT ONLINE")

updater.start_polling()
updater.idle()
