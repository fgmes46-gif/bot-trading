import os
import requests
import logging
from datetime import datetime, timedelta
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

print("🧠 SNIPER MÁXIMO - ARQUITETO ATIVO")

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

COINS = ["BTCUSDT","ETHUSDT","SOLUSDT","ADAUSDT","XRPUSDT","BNBUSDT"]

logging.basicConfig(level=logging.INFO)

# =========================
# HORÁRIOS (COM ASIÁTICO)
# =========================
def horario_permitido():
    agora = datetime.now().hour

    horarios = [
        (9,10),
        (13,14),
        (19,20),
        (0,2)
    ]

    for inicio,fim in horarios:
        if inicio <= agora <= fim:
            return True

    return False

# =========================
# BINANCE
# =========================
def get_candles(symbol, interval="1m", limit=100):

    print(f"Buscando dados de {symbol}...")

    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"

    try:
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            print("Erro API:", response.text)
            return []

        data = response.json()

        if not isinstance(data, list):
            print("Erro formato:", data)
            return []

        closes = [float(c[4]) for c in data]

        return closes

    except Exception as e:
        print("Erro conexão:", e)
        return []

# =========================
# RSI
# =========================
def calcular_rsi(closes, period=14):

    if len(closes) < period:
        return 50

    ganhos, perdas = [], []

    for i in range(1,len(closes)):
        diff = closes[i] - closes[i-1]
        ganhos.append(max(diff,0))
        perdas.append(abs(min(diff,0)))

    avg_gain = sum(ganhos[-period:]) / period
    avg_loss = sum(perdas[-period:]) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss

    return round(100 - (100/(1+rs)),2)

# =========================
# EMA
# =========================
def calcular_ema(closes, period=21):

    if len(closes) < period:
        return closes[-1]

    k = 2/(period+1)
    ema = closes[0]

    for price in closes:
        ema = price*k + ema*(1-k)

    return ema

# =========================
# FORÇA
# =========================
def forca_tendencia(closes):
    return sum([1 for i in range(-10,-1) if closes[i] > closes[i-1]])

# =========================
# FILTRO VELA FORTE
# =========================
def vela_forte(closes):

    if len(closes) < 3:
        return False

    tamanho = abs(closes[-1] - closes[-2])
    media = sum([abs(closes[i] - closes[i-1]) for i in range(-10, -1)]) / 9

    return tamanho > media * 2

# =========================
# HORÁRIOS ENTRADA
# =========================
def gerar_horarios():

    agora = datetime.now()

    entrada = agora + timedelta(minutes=1)
    r1 = entrada + timedelta(minutes=1)
    r2 = entrada + timedelta(minutes=2)

    return entrada.strftime("%H:%M"), r1.strftime("%H:%M"), r2.strftime("%H:%M")

# =========================
# LÓGICA SNIPER
# =========================
def analisar_sniper(symbol):

    if not horario_permitido():
        return None

    closes_1m = get_candles(symbol,"1m")
    closes_5m = get_candles(symbol,"5m")

    if not closes_1m or not closes_5m:
        return None

    if vela_forte(closes_1m):
        return None

    rsi = calcular_rsi(closes_1m)
    ema = calcular_ema(closes_1m)
    preco = closes_1m[-1]

    distancia = abs(preco - ema)

    if distancia / preco > 0.01:
        return None

    tendencia = preco > ema
    forca = forca_tendencia(closes_1m)

    if 45 < rsi < 55:
        return None

    direcao = "NEUTRO"

    if tendencia and rsi < 30 and forca >= 6:
        direcao = "CALL 📈"

    elif not tendencia and rsi > 70 and forca <= 3:
        direcao = "PUT 📉"

    if direcao == "NEUTRO":
        return None

    prob = 70

    if rsi < 25 or rsi > 75:
        prob += 10

    if forca >= 7:
        prob += 10

    prob = min(prob, 95)

    return direcao, prob

# =========================
# VENDA AUTOMÁTICA
# =========================
def vender(update, context):

    msg = """
🚀 ACESSO VIP

🔥 Sinais filtrados
🎯 Alta precisão
📡 Radar automático

💰 R$29

👉 Fale comigo
"""

    update.message.reply_text(msg)

# =========================
# ANALISAR
# =========================
def analisar(update, context):

    texto = update.message.text.lower()

    if any(p in texto for p in ["vip","plano","acesso"]):
        vender(update, context)
        return

    par = update.message.text.upper()

    if par not in COINS:
        update.message.reply_text("❌ Par inválido")
        return

    resultado = analisar_sniper(par)

    if not resultado:
        update.message.reply_text("📊 Sem entrada segura agora")
        return

    direcao, prob = resultado

    entrada, r1, r2 = gerar_horarios()

    direcao_txt = "🟩 COMPRA" if "CALL" in direcao else "🟥 VENDA"

    msg = f"""
⚠️ TRADE RÁPIDO

💵 {par}
⏰ Expiração: 1 minuto

🛎️ Entrada: {entrada}

{direcao_txt}

📊 Probabilidade: {prob}%

1ª reentrada - {r1}
2ª reentrada - {r2}

👉 Até 2 reentradas

🧠 Arquiteto
"""

    update.message.reply_text(msg)

# =========================
# SCAN
# =========================
def scan(update, context):

    if not horario_permitido():
        update.message.reply_text("⏰ Fora do horário operacional")
        return

    sinais = []

    for coin in COINS:
        r = analisar_sniper(coin)

        if r:
            direcao, prob = r

            if prob >= 85:
                sinais.append(f"{coin} {direcao} {prob}%")

    if not sinais:
        update.message.reply_text("📊 Mercado sem oportunidade")
        return

    msg = "🔥 OPORTUNIDADES\n\n" + "\n".join(sinais)
    update.message.reply_text(msg)

# =========================
# RADAR AUTOMÁTICO
# =========================
def radar(context):

    if not horario_permitido():
        return

    for coin in COINS:

        r = analisar_sniper(coin)

        if r:
            direcao, prob = r

            if prob >= 90:

                entrada, r1, r2 = gerar_horarios()

                msg = f"""
🚨 ALERTA SNIPER

{coin}

{direcao}
{prob}%

⏰ {entrada}
1ª {r1}
2ª {r2}

🧠 Arquiteto
"""

                context.bot.send_message(chat_id=CHAT_ID, text=msg)

# =========================
# START
# =========================
def start(update, context):

    update.message.reply_text(
        "🤖 SNIPER MÁXIMO ATIVO\n\nUse /scan ou digite a moeda (BTCUSDT)"
    )

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

print("✅ BOT ONLINE")

updater.start_polling(drop_pending_updates=True)
updater.idle()
