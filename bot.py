import os
import requests
import random
import json
from datetime import datetime
from telegram.ext import Updater, CommandHandler

print("🚀 RADAR FAMÍLIA INICIANDO")

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

API_URL = "https://api.binance.com/api/v3/klines"

COINS = [
"BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT",
"ADAUSDT","DOGEUSDT","AVAXUSDT","LINKUSDT","MATICUSDT"
]

TIMEFRAMES = ["1m","3m","5m"]

sent_cache = set()

asia_signals = 0
west_signals = 0

MAX_ASIA = 10
MAX_WEST = 10

# -----------------------------
# IDENTIFICAR SESSÃO
# -----------------------------

def session_type():

    hour = datetime.utcnow().hour

    if 0 <= hour <= 7:
        return "ASIA"

    return "WEST"

# -----------------------------
# PEGAR CANDLES
# -----------------------------

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

# -----------------------------
# RSI
# -----------------------------

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

# -----------------------------
# TENDÊNCIA
# -----------------------------

def trend(candles):

    closes = [c["close"] for c in candles[-10:]]

    if closes[-1] > closes[0]:
        return "UP"

    if closes[-1] < closes[0]:
        return "DOWN"

    return "SIDE"

# -----------------------------
# VOLUME
# -----------------------------

def volume_spike(candles):

    volumes = [c["volume"] for c in candles]

    avg = sum(volumes[:-1]) / len(volumes[:-1])

    return volumes[-1] > avg * 1.5

# -----------------------------
# VOLATILIDADE
# -----------------------------

def volatility(candles):

    highs = [c["high"] for c in candles[-10:]]
    lows = [c["low"] for c in candles[-10:]]

    return max(highs) - min(lows)

# -----------------------------
# FILTRO LATERAL
# -----------------------------

def anti_lateral(candles):

    v = volatility(candles)

    if v < candles[-1]["close"] * 0.002:
        return False

    return True

# -----------------------------
# ROMPIMENTO
# -----------------------------

def breakout(candles):

    highs = [c["high"] for c in candles[-20:]]
    lows = [c["low"] for c in candles[-20:]]

    last = candles[-1]["close"]

    if last > max(highs[:-1]):
        return "UP"

    if last < min(lows[:-1]):
        return "DOWN"

    return None

# -----------------------------
# ANALISAR PAR
# -----------------------------

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
    trend_dir = trend(candles)
    break_dir = breakout(candles)
    volat = volatility(candles)

    score = 0

    if vol:
        score += 20

    if direction == "CALL" and trend_dir == "UP":
        score += 25

    if direction == "PUT" and trend_dir == "DOWN":
        score += 25

    if break_dir:
        score += 20

    if rsi < 30 or rsi > 70:
        score += 10

    if volat > candles[-1]["close"] * 0.005:
        score += 10

    if score < 50:
        return None

    return {
        "symbol": symbol,
        "direction": direction,
        "timeframe": timeframe,
        "score": score
    }

# -----------------------------
# SALVAR HISTÓRICO
# -----------------------------

def save_signal(data):

    try:
        with open("signals.json","r") as f:
            history = json.load(f)
    except:
        history = []

    history.append(data)

    with open("signals.json","w") as f:
        json.dump(history,f,indent=4)

# -----------------------------
# RADAR
# -----------------------------

def radar(context):

    global asia_signals
    global west_signals

    session = session_type()

    if session == "ASIA" and asia_signals >= MAX_ASIA:
        return

    if session == "WEST" and west_signals >= MAX_WEST:
        return

    for coin in COINS:

        result = analyze(coin)

        if not result:
            continue

        key = f"{result['symbol']}-{result['direction']}"

        if key in sent_cache:
            continue

        sent_cache.add(key)

        if session == "ASIA":
            asia_signals += 1
        else:
            west_signals += 1

        now = datetime.utcnow().strftime("%H:%M")

        msg = f"""
⚠️ SINAL CRIPTO

PAR: {result['symbol']}
TEMPO: {result['timeframe']}

ENTRADA: {now}
DIREÇÃO: {result['direction']}

FORÇA: {result['score']}%
SESSÃO: {session}
"""

        context.bot.send_message(
            chat_id=CHAT_ID,
            text=msg
        )

        save_signal({
            "symbol": result['symbol'],
            "direction": result['direction'],
            "timeframe": result['timeframe'],
            "session": session,
            "time": now
        })

# -----------------------------
# PAINEL
# -----------------------------

def painel(update, context):

    try:
        with open("signals.json","r") as f:
            history = json.load(f)
    except:
        update.message.reply_text("Sem dados ainda.")
        return

    total = len(history)

    pairs = {}

    for s in history:

        p = s["symbol"]

        if p not in pairs:
            pairs[p] = 0

        pairs[p] += 1

    msg = f"\n📊 PAINEL DO BOT\n\nTotal sinais: {total}\n\nTOP PARES\n"

    for p in pairs:

        msg += f"{p}: {pairs[p]}\n"

    update.message.reply_text(msg)

# -----------------------------
# START
# -----------------------------

def start(update, context):

    update.message.reply_text(
        "🤖 RADAR FAMÍLIA ONLINE"
    )

# -----------------------------
# START BOT
# -----------------------------

updater = Updater(TOKEN, use_context=True)

dp = updater.dispatcher

dp.add_handler(CommandHandler("start", start))
dp.add_handler(CommandHandler("painel", painel))

job_queue = updater.job_queue

job_queue.run_repeating(radar, interval=60, first=10)

print("✅ BOT ATIVO")

updater.start_polling()
updater.idle()
