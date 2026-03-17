import os
import requests
import logging
from datetime import datetime, timedelta
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

print("🏦 SNIPER INSTITUCIONAL - ARQUITETO")

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

COINS = ["BTCUSDT","ETHUSDT","SOLUSDT","ADAUSDT","XRPUSDT","BNBUSDT"]

logging.basicConfig(level=logging.INFO)

# =========================
# BINANCE DATA
# =========================
def get_candles(symbol, interval="1m", limit=100):
    
    print(f"Buscando dados de {symbol}...")
    
    url = f"https://api.binance.us/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    
    try:
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            print("Erro API:", response.status_code, response.text)
            return []

        data = response.json()

        if not isinstance(data, list):
            print("Resposta inválida:", data)
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
# FORÇA DE TENDÊNCIA
# =========================
def forca_tendencia(closes):
    if len(closes) < 10:
        return 0

    subida = sum([1 for i in range(-10, -1) if closes[i] > closes[i-1]])
    return subida

# =========================
# HORÁRIOS (SNIPER)
# =========================
def gerar_horarios():
    agora = datetime.now()

    entrada = agora + timedelta(minutes=1)
    r1 = entrada + timedelta(minutes=1)
    r2 = entrada + timedelta(minutes=2)

    return (
        entrada.strftime("%H:%M"),
        r1.strftime("%H:%M"),
        r2.strftime("%H:%M")
    )

# =========================
# LÓGICA INSTITUCIONAL
# =========================
def analisar_institucional(symbol):

    closes_1m = get_candles(symbol, "1m")
    closes_5m = get_candles(symbol, "5m")

    if not closes_1m or not closes_5m:
        return None

    rsi_1m = calcular_rsi(closes_1m)
    rsi_5m = calcular_rsi(closes_5m)

    ema_1m = calcular_ema(closes_1m)
    ema_5m = calcular_ema(closes_5m)

    preco = closes_1m[-1]

    tendencia_1m = preco > ema_1m
    tendencia_5m = closes_5m[-1] > ema_5m

    forca = forca_tendencia(closes_1m)

    direcao = "NEUTRO"

    if tendencia_1m and tendencia_5m and rsi_1m < 35 and forca >= 6:
        direcao = "CALL 📈"

    elif not tendencia_1m and not tendencia_5m and rsi_1m > 65 and forca <= 3:
        direcao = "PUT 📉"

    if direcao == "NEUTRO":
        return None

    prob = 60

    if rsi_1m < 30 or rsi_1m > 70:
        prob += 10

    if rsi_5m < 40 or rsi_5m > 60:
        prob += 10

    if tendencia_1m == tendencia_5m:
        prob += 10

    if forca >= 7:
        prob += 10

    prob = min(prob, 97)

    return {
        "direcao": direcao,
        "prob": prob,
        "rsi": rsi_1m,
        "forca": forca,
        "ema": round(ema_1m,2)
    }

# =========================
# VENDA AUTOMÁTICA
# =========================
def vender(update, context):
    msg = """
🚀 ACESSO VIP LIBERADO

Você está vendo apenas 20% do que o bot faz.

🔥 No VIP você recebe:
- Sinais em tempo real
- Radar automático
- Alta precisão

💰 VALOR HOJE: R$29

👉 Fale comigo: @JrGmes_bot
"""
    update.message.reply_text(msg)

# =========================
# ANALISAR
# =========================
def analisar(update, context):
    texto = update.message.text.lower()

    # gatilho de venda
    if any(p in texto for p in ["vip","plano","acesso","entrar"]):
        vender(update, context)
        return

    par = update.message.text.upper()

    if par not in COINS:
        update.message.reply_text("❌ Par inválido")
        return

    dados = analisar_institucional(par)

    if not dados:
        update.message.reply_text("📊 Sem entrada institucional")
        return

    entrada, r1, r2 = gerar_horarios()

    direcao_txt = "🟩 Compra (CALL)" if "CALL" in dados["direcao"] else "🟥 Venda (PUT)"

    msg = f"""
⚠️ TRADE RÁPIDO

💵 {par}
⏰ Expiração: 1 Minuto

🛎️ Entrada: {entrada}

{direcao_txt}

📊 Probabilidade: {dados['prob']}%

1ª reentrada - {r1}
2ª reentrada - {r2}

👉 Até 2 reentradas se necessário

🧠 Arquiteto
"""

    update.message.reply_text(msg)

# =========================
# SCAN
# =========================
def scan(update, context):
    sinais = []

    for coin in COINS:
        dados = analisar_institucional(coin)

        if dados and dados["prob"] >= 85:
            sinais.append(f"{coin} {dados['direcao']} {dados['prob']}%")

    if not sinais:
        update.message.reply_text("📊 Mercado sem oportunidade forte")
        return

    msg = "🏦 SCANNER INSTITUCIONAL\n\n" + "\n".join(sinais)
    update.message.reply_text(msg)

# =========================
# RADAR AUTOMÁTICO
# =========================
def radar(context):
    for coin in COINS:
        dados = analisar_institucional(coin)

        if dados and dados["prob"] >= 90:
            entrada, r1, r2 = gerar_horarios()

            direcao_txt = "🟩 CALL" if "CALL" in dados["direcao"] else "🟥 PUT"

            msg = f"""
🚨 ALERTA INSTITUCIONAL

PAR: {coin}

{direcao_txt}
PROBABILIDADE: {dados['prob']}%

⏰ Entrada: {entrada}

1ª: {r1}
2ª: {r2}

🧠 Arquiteto
"""
            context.bot.send_message(chat_id=CHAT_ID, text=msg)

# =========================
# START
# =========================
def start(update, context):
    update.message.reply_text("""
🏦 BOT INSTITUCIONAL ATIVO

Comandos:
/scan

Digite:
BTCUSDT
ETHUSDT
""")

# =========================
# BOT START
# =========================
updater = Updater(TOKEN, use_context=True)
dp = updater.dispatcher

dp.add_handler(CommandHandler("start", start))
dp.add_handler(CommandHandler("scan", scan))
dp.add_handler(MessageHandler(Filters.text & ~Filters.command, analisar))

job_queue = updater.job_queue
job_queue.run_repeating(radar, interval=300, first=20)

print("✅ BOT INSTITUCIONAL ONLINE")

updater.start_polling(drop_pending_updates=True)
updater.idle()
