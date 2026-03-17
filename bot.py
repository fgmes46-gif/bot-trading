import os
import requests
import json
from datetime import datetime, timedelta
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

print("🧠 ARQUITETO PRO - BOT ADAPTATIVO")

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

COINS = ["BTCUSDT","ETHUSDT","SOLUSDT","ADAUSDT","XRPUSDT","BNBUSDT"]
ARQUIVO = "historico.json"


# =========================
# 📊 PEGAR DADOS BINANCE
# =========================
def get_candles(symbol):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=50"
        data = requests.get(url).json()
        closes = [float(c[4]) for c in data]
        return closes
    except:
        return None


# =========================
# 🧠 FILTRO INTELIGENTE
# =========================
def filtro_inteligente(prob):
    if prob >= 80:
        return "FORTE 💥"
    elif prob >= 70:
        return "BOA 🔥"
    else:
        return "FRACA ⚠️"


# =========================
# 📈 ANALISE SIMPLES
# =========================
def analisar(closes):
    if not closes:
        return None, 0

    tendencia = "alta" if closes[-1] > closes[0] else "baixa"

    variacao = abs(closes[-1] - closes[0])
    prob = min(90, int(variacao * 1000))

    return tendencia, prob


# =========================
# 🎯 SNIPER PROGRAMADO
# =========================
def sniper_programado(context):
    for coin in COINS:
        closes = get_candles(coin)
        tendencia, prob = analisar(closes)

        if not tendencia:
            continue

        if prob < 70:
            continue

        direcao = "🟩 CALL" if tendencia == "alta" else "🟥 PUT"
        nivel = filtro_inteligente(prob)

        agora = datetime.now()
        entrada = (agora + timedelta(minutes=1)).strftime("%H:%M")
        g1 = (agora + timedelta(minutes=2)).strftime("%H:%M")
        g2 = (agora + timedelta(minutes=3)).strftime("%H:%M")

        mensagem = f"""
🚨 ALERTA INSTITUCIONAL

PAR: {coin}

{direcao}
PROBABILIDADE: {prob}%
NÍVEL: {nivel}

⏰ Entrada: {entrada}
1ª: {g1}
2ª: {g2}

🧠 Arquiteto
"""

        context.bot.send_message(chat_id=CHAT_ID, text=mensagem)


# =========================
# ⚡ SNIPER ADAPTATIVO
# =========================
def sniper_adaptativo(context):
    for coin in COINS:
        closes = get_candles(coin)
        tendencia, prob = analisar(closes)

        if not tendencia:
            continue

        if prob < 70:
            continue

        direcao = "🟩 CALL" if tendencia == "alta" else "🟥 PUT"
        nivel = filtro_inteligente(prob)

        agora = datetime.now()
        entrada = (agora + timedelta(minutes=1)).strftime("%H:%M")
        g1 = (agora + timedelta(minutes=2)).strftime("%H:%M")
        g2 = (agora + timedelta(minutes=3)).strftime("%H:%M")

        mensagem = f"""
🚨 ALERTA ADAPTATIVO

PAR: {coin}

{direcao}
PROBABILIDADE: {prob}%
NÍVEL: {nivel}

⏰ Entrada: {entrada}
1ª: {g1}
2ª: {g2}

🧠 Arquiteto
"""

        context.bot.send_message(chat_id=CHAT_ID, text=mensagem)


# =========================
# 📡 RADAR
# =========================
def radar(context):
    context.bot.send_message(chat_id=CHAT_ID, text="📡 Radar ativo...")


# =========================
# 🚀 START
# =========================
def start(update, context):
    update.message.reply_text("🤖 SNIPER MÁXIMO ATIVO")


# =========================
# 🚀 INICIALIZAÇÃO
# =========================
updater = Updater(TOKEN, use_context=True)

dp = updater.dispatcher

dp.add_handler(CommandHandler("start", start))

job_queue = updater.job_queue

# 🔥 TESTE (DEPOIS MUDA PRA 900 OU 1800)
job_queue.run_repeating(sniper_programado, interval=60, first=10)

print("✅ ARQUITETO PRO ONLINE")
print("🚀 Iniciando bot...")

updater.start_polling()
updater.idle()
