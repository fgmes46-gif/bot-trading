# 🧠 ARQUITETO_ANALISE_PRO_V3.py

import os
import requests
import numpy as np
import time
from datetime import datetime, timedelta
from telegram import Bot

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # API do Google Cloud

bot = Bot(token=TOKEN)

COINS = [
 "BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT",
 "BNBUSDT","ADAUSDT","DOGEUSDT"
]

# =========================
# CANDLES (ROBUSTO)
# =========================
def get_candles(symbol, interval="1m"):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=120"
        data = requests.get(url, timeout=5).json()

        if not isinstance(data, list):
            return None, None

        closes = [float(c[4]) for c in data]
        volumes = [float(c[5]) for c in data]

        return closes, volumes

    except:
        return None, None

# =========================
# INDICADORES
# =========================
def sma(closes, period=14):
    return np.mean(closes[-period:])

def rsi(closes):
    deltas = np.diff(closes)
    gain = np.mean([d for d in deltas if d > 0]) if any(d > 0 for d in deltas) else 0
    loss = abs(np.mean([d for d in deltas if d < 0])) if any(d < 0 for d in deltas) else 1
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# =========================
# SCORE MULTI-TIMEFRAME
# =========================
def analisar_multi(symbol):
    total_score = 0
    direcao_final = None

    for tf in ["1m","3m","5m"]:
        closes, volumes = get_candles(symbol, tf)

        if closes is None or len(closes) < 30:
            continue

        sma14 = sma(closes)
        mm20 = np.mean(closes[-20:])
        rsi_val = rsi(closes)

        preco = closes[-1]
        prev = closes[-2]

        score = 0
        direcao = None

        # rompimento
        if prev < sma14 and preco > sma14:
            direcao = "CALL"
            score += 40
        elif prev > sma14 and preco < sma14:
            direcao = "PUT"
            score += 40

        # tendência
        if direcao == "CALL" and preco > mm20:
            score += 20
        elif direcao == "PUT" and preco < mm20:
            score += 20

        # RSI
        if 45 < rsi_val < 65:
            score += 20

        # volume
        if volumes[-1] > np.mean(volumes[-10:]):
            score += 20

        total_score += score

        if direcao:
            direcao_final = direcao

    return direcao_final, total_score

# =========================
# ESCOLHER MELHOR
# =========================
def melhor_sinal():
    melhor = None
    melhor_score = 0

    for coin in COINS:
        direcao, score = analisar_multi(coin)

        if direcao and score > melhor_score:
            melhor_score = score
            melhor = (coin, direcao, score)

    return melhor

# =========================
# DEFINIR EXPIRAÇÃO
# =========================
def definir_expiracao(score):
    if score > 180:
        return "1m"
    elif score > 140:
        return "3m"
    else:
        return "5m"

# =========================
# HORÁRIOS
# =========================
def gerar_horario(exp):
    brasilia = datetime.utcnow() - timedelta(hours=3)

    minutos = int(exp.replace("m",""))
    entrada = brasilia + timedelta(minutes=1)
    manaus = entrada - timedelta(hours=1)

    return entrada, manaus, minutos

# =========================
# WEBHOOK (BINANCE)
# =========================
def enviar_webhook(coin, direcao):
    if not WEBHOOK_URL:
        return

    try:
        payload = {
            "symbol": coin,
            "side": "BUY" if direcao == "CALL" else "SELL"
        }
        requests.post(WEBHOOK_URL, json=payload, timeout=3)
    except:
        pass

# =========================
# TELEGRAM
# =========================
def enviar():
    sinal = melhor_sinal()

    if not sinal:
        print("Sem sinal forte...")
        return

    coin, direcao, score = sinal
    exp = definir_expiracao(score)

    entrada, manaus, minutos = gerar_horario(exp)

    direcao_txt = "🟩 Compra (CALL)" if direcao == "CALL" else "🟥 Venda (PUT)"

    msg = f"""
⚠️ TRADE RÁPIDO

💵 Criptomoeda: {coin}
⏰ Expiração: {exp}

🛎️ Entrada (Manaus): {manaus.strftime('%H:%M')}

{direcao_txt}

🔁 1ª reentrada: {(manaus + timedelta(minutes=1)).strftime('%H:%M')}
🔁 2ª reentrada: {(manaus + timedelta(minutes=2)).strftime('%H:%M')}

👉🏼 Até 2 reentradas se necessário

➡️ Abrir corretora:
https://seulink-aqui.com

🧠 Arquiteto PRO V3
🔥 Score: {score}
"""

    bot.send_message(chat_id=CHAT_ID, text=msg)

    # envia pro bot Binance
    enviar_webhook(coin, direcao)

    print(f"SINAL: {coin} {direcao} SCORE {score}")

# =========================
# LOOP
# =========================
while True:
    enviar()
    time.sleep(180)
