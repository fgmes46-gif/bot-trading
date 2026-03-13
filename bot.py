import os
import requests
import random
from datetime import datetime
from telegram.ext import Updater, CommandHandler

print("🚀 RADAR ULTRA 3.0 INICIANDO...")

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not TOKEN:
    print("❌ BOT_TOKEN não encontrado")
    exit()

API_URL = "https://api.binance.com/api/v3/klines"

# --------------------------------
# MOEDAS
# --------------------------------

SCAN_COINS = [
"BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT",
"ADAUSDT","DOGEUSDT","AVAXUSDT","LINKUSDT","MATICUSDT",
"LTCUSDT","TRXUSDT","APTUSDT","ARBUSDT","OPUSDT",
"ATOMUSDT","NEARUSDT","FILUSDT","INJUSDT","SANDUSDT",
"FTMUSDT","GALAUSDT","AAVEUSDT","ALGOUSDT","EGLDUSDT",
"DYDXUSDT","RNDRUSDT","FLOWUSDT","KAVAUSDT","ZILUSDT",
"GMTUSDT","CHZUSDT","CRVUSDT","COMPUSDT","SNXUSDT",
"UNIUSDT","1INCHUSDT","BATUSDT","LDOUSDT","ENSUSDT"
]

TIMEFRAMES = ["1m","3m","5m"]

sent_cache = set()

# --------------------------------
# BINANCE DATA
# --------------------------------

def get_candles(symbol, interval="1m", limit=50):

    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }

    r = requests.get(API_URL, params=params)

    if r.status_code != 200:
        return []

    data = r.json()

    candles = []

    for c in data:

        candles.append({
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
            "volume": float(c[5])
        })

    return candles

# --------------------------------
# RSI
# --------------------------------

def calculate_rsi(candles, period=14):

    closes = [c["close"] for c in candles]

    gains = []
    losses = []

    for i in range(1, len(closes)):

        diff = closes[i] - closes[i-1]

        if diff >= 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))

    avg_gain = sum(gains[-period:]) / period if gains else 0
    avg_loss = sum(losses[-period:]) / period if losses else 0

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss

    rsi = 100 - (100 / (1 + rs))

    return rsi

# --------------------------------
# VOLUME SPIKE
# --------------------------------

def volume_spike(candles):

    volumes = [c["volume"] for c in candles]

    avg = sum(volumes[:-1]) / len(volumes[:-1])

    last = volumes[-1]

    return last > avg * 1.5

# --------------------------------
# TREND
# --------------------------------

def trend_direction(candles):

    closes = [c["close"] for c in candles[-10:]]

    if closes[-1] > closes[0]:
        return "UP"

    if closes[-1] < closes[0]:
        return "DOWN"

    return "SIDE"

# --------------------------------
# ANTI LATERAL
# --------------------------------

def anti_lateral(candles):

    highs = [c["high"] for c in candles[-10:]]
    lows = [c["low"] for c in candles[-10:]]

    range_price = max(highs) - min(lows)

    if range_price < (candles[-1]["close"] * 0.002):
        return False

    return True

# --------------------------------
# ANALISE
# --------------------------------

def analyze(symbol):

    timeframe = random.choice(TIMEFRAMES)

    candles = get_candles(symbol, timeframe)

    if not candles:
        return None

    if not anti_lateral(candles):
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

    rsi = calculate_rsi(candles)

    vol = volume_spike(candles)

    trend = trend_direction(candles)

    score = 0

    if vol:
        score += 25

    if direction == "CALL" and trend == "UP":
        score += 30

    if direction == "PUT" and trend == "DOWN":
        score += 30

    if rsi < 30 or rsi > 70:
        score += 25

    if score < 50:
        return None

    return {
        "symbol": symbol,
        "direction": direction,
        "timeframe": timeframe,
        "volume": vol,
        "rsi": round(rsi,2),
        "trend": trend,
        "score": score
    }

# --------------------------------
# SESSÃO ASIÁTICA
# --------------------------------

def asian_session():

    hour = datetime.utcnow().hour

    return hour >= 23 or hour <= 6

# --------------------------------
# SCANNER
# --------------------------------

def scan():

    signals = []

    for coin in SCAN_COINS:

        try:

            result = analyze(coin)

            if result:
                signals.append(result)

        except:
            pass

    print(f"📊 Moedas analisadas: {len(SCAN_COINS)}")

    return signals

# --------------------------------
# TELEGRAM
# --------------------------------

def start(update, context):

    update.message.reply_text(
        "🤖 RADAR ULTRA 3.0 ATIVO"
    )

def status(update, context):

    update.message.reply_text(
        "📡 Scanner funcionando..."
    )

# --------------------------------
# RADAR
# --------------------------------

def radar(context):

    if not CHAT_ID:
        return

    print("🔎 Escaneando mercado...")

    signals = scan()

    for s in signals:

        key = f"{s['symbol']}-{s['direction']}"

        if key in sent_cache:
            continue

        sent_cache.add(key)

        msg = f"""
🚨 SINAL FORTE

MOEDA: {s['symbol']}
DIREÇÃO: {s['direction']}
TEMPO: {s['timeframe']}

RSI: {s['rsi']}
TREND: {s['trend']}
VOLUME: {"SPIKE" if s["volume"] else "NORMAL"}

PROBABILIDADE: {s['score']}%

SESSÃO ASIÁTICA: {"SIM" if asian_session() else "NÃO"}
"""

        context.bot.send_message(
            chat_id=CHAT_ID,
            text=msg
        )

# --------------------------------
# START BOT
# --------------------------------

updater = Updater(TOKEN, use_context=True)

dp = updater.dispatcher

dp.add_handler(CommandHandler("start", start))
dp.add_handler(CommandHandler("status", status))

job_queue = updater.job_queue

job_queue.run_repeating(radar, interval=60, first=10)

print("✅ BOT ONLINE")

updater.start_polling()
updater.idle()
