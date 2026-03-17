import os
import requests
import logging
from datetime import datetime
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

print("🚀 SNIPER MÁXIMO INICIANDO...")

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

COINS = ["BTCUSDT","ETHUSDT","SOLUSDT","ADAUSDT","XRPUSDT","BNBUSDT"]

logging.basicConfig(level=logging.INFO)

# =========================
# BINANCE DATA
# =========================
def get_candles(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=100"
    try:
        data = requests.get(url, timeout=5).json()
        closes = [float(c[4]) for c in data]
        return closes
    except:
        return []

# =========================
# RSI (MELHORADO)
# =========================
def calcular_rsi(closes, period=14):
    if len(closes) < period:
        return 50

    ganhos = []
    perdas = []

    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        ganhos.append(max(diff, 0))
        perdas.append(abs(min(diff, 0)))

    avg_gain = sum(ganhos[-period:]) / period
    avg_loss = sum(perdas[-period:]) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

# =========================
# EMA
# =========================
def calcular_ema(closes, period=21):
    if len(closes) < period:
        return closes[-1]

    k = 2 / (period + 1)
    ema = closes[0]

    for price in closes:
        ema = price * k + ema * (1 - k)

    return ema

# =========================
# MOVIMENTO
# =========================
def detectar_movimento(closes):
    if len(closes) < 10:
        return "NEUTRO"

    base = closes[-6]
    atual = closes[-1]

    if base == 0:
        return "NEUTRO"

    variacao = ((atual - base) / base) * 100

    if variacao > 1:
        return "PUMP 📈"
    elif variacao < -1:
        return "DUMP 📉"
    return "NEUTRO"

# =========================
# LÓGICA SNIPER
# =========================
def analisar_sniper(closes):
    rsi = calcular_rsi(closes)
    ema = calcular_ema(closes)
    movimento = detectar_movimento(closes)

    preco = closes[-1]

    direcao = "NEUTRO"
    tendencia = preco > ema

    # SNIPER ENTRY
    if preco > ema and rsi < 35:
        direcao = "CALL 📈"
    elif preco < ema and rsi > 65:
        direcao = "PUT 📉"

    # PROBABILIDADE REAL
    prob = 50

    if rsi < 30 or rsi > 70:
        prob += 20

    if movimento != "NEUTRO":
        prob += 10

    if tendencia:
        prob += 10

    prob = min(prob, 95)

    return rsi, ema, movimento, direcao, prob

# =========================
# COMANDO ANALISAR
# =========================
def analisar(update, context):
    par = update.message.text.upper()

    if par not in COINS:
        update.message.reply_text("❌ Par não suportado")
        return

    closes = get_candles(par)

    if not closes:
        update.message.reply_text("Erro ao pegar dados")
        return

    rsi, ema, movimento, direcao, prob = analisar_sniper(closes)

    if direcao == "NEUTRO":
        update.message.reply_text("📊 Mercado sem entrada segura")
        return

    msg = f"""
🎯 SNIPER MÁXIMO

PAR: {par}

RSI: {rsi}
EMA: {round(ema,2)}

MOVIMENTO: {movimento}

DIREÇÃO: {direcao}

PROBABILIDADE: {prob}%

ENTRADA: próxima vela
TEMPO: 1m

REENTRADAS:
1° +1m
2° +2m
"""

    update.message.reply_text(msg)

# =========================
# SCAN
# =========================
def scan(update, context):
    sinais = []

    for coin in COINS:
        closes = get_candles(coin)
        if not closes:
            continue

        rsi, ema, movimento, direcao, prob = analisar_sniper(closes)

        if prob >= 80 and direcao != "NEUTRO":
            sinais.append(f"{coin} {direcao} {prob}%")

    if not sinais:
        update.message.reply_text("📊 Mercado lateral")
        return

    msg = "🔥 OPORTUNIDADES SNIPER\n\n"
    msg += "\n".join(sinais)

    update.message.reply_text(msg)

# =========================
# RADAR AUTOMÁTICO
# =========================
def radar(context):
    for coin in COINS:
        closes = get_candles(coin)
        if not closes:
            continue

        rsi, ema, movimento, direcao, prob = analisar_sniper(closes)

        if prob >= 85 and direcao != "NEUTRO":
            msg = f"""
🚨 ALERTA SNIPER

PAR: {coin}

RSI: {rsi}
EMA: {round(ema,2)}

MOVIMENTO: {movimento}

DIREÇÃO: {direcao}

PROBABILIDADE: {prob}%
TEMPO: 1m
"""

            context.bot.send_message(chat_id=CHAT_ID, text=msg)

# =========================
# START
# =========================
def start(update, context):
    update.message.reply_text("""
🤖 SNIPER MÁXIMO ATIVO

Comandos:
/scan

Ou digite:
BTCUSDT
ETHUSDT
""")

# =========================
# BOT
# =========================
updater = Updater(TOKEN, use_context=True)
dp = updater.dispatcher

dp.add_handler(CommandHandler("start", start))
dp.add_handler(CommandHandler("scan", scan))
dp.add_handler(MessageHandler(Filters.text & ~Filters.command, analisar))

job_queue = updater.job_queue
job_queue.run_repeating(radar, interval=300, first=20)

print("✅ SNIPER ONLINE")

updater.start_polling(drop_pending_updates=True)
updater.idle()
