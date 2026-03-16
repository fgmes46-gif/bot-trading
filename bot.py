import os
import requests
from datetime import datetime
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

print("🚀 RADAR FAMÍLIA PRO INICIANDO")

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

COINS = [
"BTCUSDT",
"ETHUSDT",
"SOLUSDT",
"ADAUSDT",
"XRPUSDT",
"BNBUSDT"
]

# -----------------------------
# PEGAR CANDLES BINANCE
# -----------------------------

def get_candles(symbol):

    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=50"

    try:
        data = requests.get(url).json()

        if not isinstance(data, list):
            return [], []

        closes = [float(c[4]) for c in data if len(c) > 4]
        volumes = [float(c[5]) for c in data if len(c) > 5]

        return closes, volumes

    except:
        return [], []


# -----------------------------
# RSI REAL
# -----------------------------

def calcular_rsi(closes):

    ganhos = []
    perdas = []

    for i in range(1, len(closes)):

        diff = closes[i] - closes[i-1]

        if diff > 0:
            ganhos.append(diff)
        else:
            perdas.append(abs(diff))

    media_ganho = sum(ganhos)/len(ganhos) if ganhos else 0
    media_perda = sum(perdas)/len(perdas) if perdas else 1

    rs = media_ganho / media_perda

    rsi = 100 - (100/(1+rs))

    return round(rsi,2)


# -----------------------------
# DETECTAR PUMP/DUMP
# -----------------------------

def detectar_movimento(closes):

    if len(closes) < 6:
        return "NEUTRO"

    variacao = ((closes[-1] - closes[-5]) / closes[-5]) * 100

    if variacao > 1.2:
        return "PUMP 📈"

    if variacao < -1.2:
        return "DUMP 📉"

    return "NEUTRO"


# -----------------------------
# CALCULAR PROBABILIDADE
# -----------------------------

def calcular_probabilidade(rsi, movimento):

    prob = 60

    if rsi < 30:
        prob += 15

    if rsi > 70:
        prob += 15

    if movimento == "PUMP 📈":
        prob += 5

    if movimento == "DUMP 📉":
        prob += 5

    return min(prob,90)


# -----------------------------
# ANALISAR MOEDA
# -----------------------------

def analisar(update, context):

    par = update.message.text.upper()

    if par not in COINS:

        update.message.reply_text("❌ moeda não suportada")
        return

    closes, volumes = get_candles(par)

    rsi = calcular_rsi(closes)

    movimento = detectar_movimento(closes)

    direcao = "CALL 📈" if rsi < 50 else "PUT 📉"

    prob = calcular_probabilidade(rsi, movimento)

    msg = f"""
📊 ANÁLISE SNIPER

PAR: {par}

RSI: {rsi}

MOVIMENTO: {movimento}

DIREÇÃO: {direcao}

TEMPO: 1m

ENTRADA: próxima vela

PROBABILIDADE: {prob}%

1° REENTRADA: +1m
2° REENTRADA: +2m
"""

    update.message.reply_text(msg)


# -----------------------------
# RANKING
# -----------------------------

def ranking(update, context):

    ranking_lista = []

    for coin in COINS:

        closes,_ = get_candles(coin)

        rsi = calcular_rsi(closes)

        ranking_lista.append((coin,rsi))

    ranking_lista.sort(key=lambda x: x[1])

    msg = "🏆 RANKING DE FORÇA\n\n"

    for coin,rsi in ranking_lista:

        msg += f"{coin}  RSI:{rsi}\n"

    update.message.reply_text(msg)


# -----------------------------
# SCANNER
# -----------------------------

def scan(update, context):

    sinais = []

    for coin in COINS:

        closes,_ = get_candles(coin)

        rsi = calcular_rsi(closes)

        movimento = detectar_movimento(closes)

        prob = calcular_probabilidade(rsi, movimento)

        if prob >= 70:

            direcao = "CALL 📈" if rsi < 50 else "PUT 📉"

            sinais.append(f"{coin} {direcao} {prob}%")

    if not sinais:

        update.message.reply_text("📊 mercado neutro")
        return

    msg = "🔥 OPORTUNIDADES\n\n"

    for s in sinais:

        msg += s + "\n"

    update.message.reply_text(msg)


# -----------------------------
# RADAR AUTOMÁTICO
# -----------------------------

def radar(context):

    for coin in COINS:

        closes,_ = get_candles(coin)

        rsi = calcular_rsi(closes)

        movimento = detectar_movimento(closes)

        prob = calcular_probabilidade(rsi, movimento)

        if prob >= 75:

            direcao = "CALL 📈" if rsi < 50 else "PUT 📉"

            msg = f"""
🚨 RADAR AUTOMÁTICO

PAR: {coin}

RSI: {rsi}

MOVIMENTO: {movimento}

DIREÇÃO: {direcao}

PROBABILIDADE: {prob}%

TEMPO: 1m
"""

            context.bot.send_message(chat_id=CHAT_ID,text=msg)


# -----------------------------
# START
# -----------------------------

def start(update, context):

    msg = """
🤖 RADAR FAMÍLIA PRO

Comandos:

/ranking
/scan

Ou digite moeda

Ex:

BTCUSDT
SOLUSDT
"""

    update.message.reply_text(msg)


# -----------------------------
# BOT START
# -----------------------------

updater = Updater(TOKEN, use_context=True)

dp = updater.dispatcher

dp.add_handler(CommandHandler("start", start))
dp.add_handler(CommandHandler("scan", scan))
dp.add_handler(CommandHandler("ranking", ranking))

dp.add_handler(MessageHandler(Filters.text & ~Filters.command, analisar))

job_queue = updater.job_queue

job_queue.run_repeating(radar, interval=600, first=20)

print("✅ BOT ATIVO")

updater.start_polling(drop_pending_updates=True)

updater.idle()
