# 🧠 ARQUITETO_ANALISE_PRO.py

import os
import requests
import numpy as np
import time
from datetime import datetime, timedelta
from telegram import Bot

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TOKEN)

COINS = ["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT"]

# =========================
# CANDLES
# =========================
def get_candles(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=100"
    data = requests.get(url).json()
    closes = [float(c[4]) for c in data]
    return closes

# =========================
# ANALISE
# =========================
def analisar(closes):
    mm5 = np.mean(closes[-5:])
    mm20 = np.mean(closes[-20:])

    if mm5 > mm20:
        return "🟩 COMPRA", 80
    else:
        return "🟥 VENDA", 80

# =========================
# MELHOR SINAL
# =========================
def melhor_sinal():
    melhor = None
    melhor_score = 0

    for coin in COINS:
        closes = get_candles(coin)
        direcao, score = analisar(closes)

        if score > melhor_score:
            melhor_score = score
            melhor = (coin, direcao, score)

    return melhor

# =========================
# HORÁRIO AJUSTE
# =========================
def gerar_horarios():
    brasilia = datetime.utcnow() - timedelta(hours=3)
    entrada = brasilia + timedelta(minutes=1)
    manaus = entrada - timedelta(hours=1)

    return entrada, manaus

# =========================
# ENVIAR SINAL
# =========================
def enviar():
    sinal = melhor_sinal()
    if not sinal:
        return

    coin, direcao, score = sinal
    entrada, manaus = gerar_horarios()

    msg = f"""
⚠️ TRADE RÁPIDO

💵 Par: {coin}
⏰ Expiração: 1 minuto

🕒 Brasília: {entrada.strftime('%H:%M')}
🕒 Manaus: {manaus.strftime('%H:%M')}

{direcao}

🔁 Reentrada 1: {(manaus + timedelta(minutes=1)).strftime('%H:%M')}
🔁 Reentrada 2: {(manaus + timedelta(minutes=2)).strftime('%H:%M')}

➡️ Abrir corretora:
https://seulink-aqui.com

🧠 Arquiteto PRO | Score {score}%
"""

    bot.send_message(chat_id=CHAT_ID, text=msg)

# =========================
# LOOP
# =========================
while True:
    enviar()
    time.sleep(120)
