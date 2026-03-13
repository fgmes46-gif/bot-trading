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

# ================================
# RADAR ULTRA PRO UPGRADE
# ================================

def get_klines(symbol, interval="1m", limit=100):
    url = f"{API_URL}/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        closes = [float(c[4]) for c in data]
        volumes = [float(c[5]) for c in data]
        return closes, volumes
    except:
        return None, None


def calculate_rsi(prices, period=14):
    if len(prices) < period:
        return 50

    gains = []
    losses = []

    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        if diff > 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))

    avg_gain = sum(gains[-period:]) / period if gains else 0.001
    avg_loss = sum(losses[-period:]) / period if losses else 0.001

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def detect_signal(symbol):

    closes, volumes = get_klines(symbol)

    if not closes:
        return None

    rsi = calculate_rsi(closes)

    last_price = closes[-1]
    prev_price = closes[-2]

    volume_now = volumes[-1]
    volume_prev = volumes[-2]

    change = ((last_price - prev_price) / prev_price) * 100

    score = 0

    if rsi < 30:
        score += 30

    if rsi > 70:
        score += 30

    if volume_now > volume_prev * 1.5:
        score += 25

    if abs(change) > 0.2:
        score += 20

    if score >= 60:

        direction = "COMPRA" if change > 0 else "VENDA"

        return f"""
🚨 SINAL DETECTADO

Moeda: {symbol}
Direção: {direction}

RSI: {round(rsi,2)}
Movimento: {round(change,3)}%

Probabilidade: {score}%

⚡ RADAR ULTRA PRO
"""

    return None


def radar_ultra():

    while True:

        try:

            for coin in SCAN_COINS:

                signal = detect_signal(coin)

                if signal:

                    try:
                        requests.post(
                            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                            json={
                                "chat_id": CHAT_ID,
                                "text": signal
                            }
                        )
                    except:
                        pass

                time.sleep(2)

        except Exception as e:
            print("Erro radar:", e)

        time.sleep(30)


# iniciar radar automático
import threading
threading.Thread(target=radar_ultra).start()
