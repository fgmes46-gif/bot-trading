import os
import json
import requests
from datetime import datetime
from binance.client import Client
from telegram.ext import Updater, CommandHandler
import requests

print(requests.get("https://ipinfo.io/json").text)

print("🧠 ARQUITETO PRO 3.0")

# =========================
# CONFIG
# =========================
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

API_KEY = os.getenv("BINANCE_KEY")
API_SECRET = os.getenv("BINANCE_SECRET")

client = Client(API_KEY, API_SECRET)

COINS = ["BTCUSDT","ETHUSDT","SOLUSDT"]

ARQUIVO = "historico.json"

MODO_SIMULACAO = True
BOT_ATIVO = False
saldo_fake = 100

ULTIMA_ENTRADA = {}

# =========================
# TELEGRAM CONTROLE
# =========================
def ligar(update, context):
    global BOT_ATIVO
    BOT_ATIVO = True
    update.message.reply_text("🟢 BOT LIGADO")

def desligar(update, context):
    global BOT_ATIVO
    BOT_ATIVO = False
    update.message.reply_text("🔴 BOT DESLIGADO")

# =========================
# DADOS
# =========================
def get_candles(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=50"
    data = requests.get(url).json()
    return [float(c[4]) for c in data]

# =========================
# ANALISE INTELIGENTE
# =========================
def analisar(closes):
    mm5 = sum(closes[-5:]) / 5
    mm20 = sum(closes[-20:]) / 20

    if mm5 > mm20:
        return "BUY", 80
    elif mm5 < mm20:
        return "SELL", 80
    return None, 0

# =========================
# HISTÓRICO
# =========================
def carregar_historico():
    try:
        with open(ARQUIVO, "r") as f:
            return json.load(f)
    except:
        return []

def salvar_resultado(resultado):
    dados = carregar_historico()
    dados.append(resultado)
    with open(ARQUIVO, "w") as f:
        json.dump(dados, f)

# =========================
# RISCO
# =========================
def get_balance():
    if MODO_SIMULACAO:
        return saldo_fake
    try:
        balance = client.get_asset_balance(asset='USDT')
        return float(balance['free'])
    except:
        return 0

def calcular_risco(historico):
    if len(historico) < 5:
        return 0.02

    ultimos = historico[-5:]
    if ultimos.count("LOSS") >= 3:
        return 0.01
    elif ultimos.count("WIN") >= 3:
        return 0.03
    return 0.02

# =========================
# ANTI-BURRICE 😂
# =========================
def pode_operar(coin):
    agora = datetime.now()

    if coin in ULTIMA_ENTRADA:
        diff = (agora - ULTIMA_ENTRADA[coin]).seconds
        if diff < 300:
            return False

    ULTIMA_ENTRADA[coin] = agora
    return True

# =========================
# PROTEÇÃO
# =========================
def protecao(historico):
    ultimos = historico[-10:]
    if ultimos.count("LOSS") >= 6:
        return False
    return True

# =========================
# SIMULAÇÃO
# =========================
def simular_trade(symbol, direcao, valor):
    global saldo_fake

    closes = get_candles(symbol)
    entrada = closes[-1]
    saida = closes[-2]

    if direcao == "BUY":
        lucro = (saida - entrada) / entrada
    else:
        lucro = (entrada - saida) / entrada

    resultado = valor * lucro
    saldo_fake += resultado

    if resultado > 0:
        salvar_resultado("WIN")
        status = "WIN 🟢"
    else:
        salvar_resultado("LOSS")
        status = "LOSS 🔴"

    return status, resultado, saldo_fake

# =========================
# EXECUÇÃO REAL
# =========================
def executar_ordem(symbol, side, valor):
    try:
        if side == "BUY":
            return client.order_market_buy(symbol=symbol, quoteOrderQty=valor)
        else:
            return client.order_market_sell(symbol=symbol, quoteOrderQty=valor)
    except Exception as e:
        print("Erro:", e)
        return None

# =========================
# BOT PRINCIPAL
# =========================
def rodar_bot(context):
    global BOT_ATIVO

    if not BOT_ATIVO:
        return

    historico = carregar_historico()

    if not protecao(historico):
        context.bot.send_message(chat_id=CHAT_ID, text="🛑 BOT EM PROTEÇÃO")
        return

    saldo = get_balance()

    if saldo < 100:
        context.bot.send_message(chat_id=CHAT_ID, text="⚠️ Saldo insuficiente (<100 USDT)")
        return

    risco = calcular_risco(historico)
    valor_trade = saldo * risco

    for coin in COINS:
        if not pode_operar(coin):
            continue

        closes = get_candles(coin)
        direcao, prob = analisar(closes)

        if not direcao:
            continue

        if MODO_SIMULACAO:
            status, lucro, saldo_fake_atual = simular_trade(coin, direcao, valor_trade)

            msg = f"""
🧪 SIMULAÇÃO

PAR: {coin}
TIPO: {direcao}
RESULTADO: {status}
LUCRO: {lucro:.2f}

SALDO: {saldo_fake_atual:.2f}
"""
        else:
            executar_ordem(coin, direcao, valor_trade)
            msg = f"🚀 ORDEM REAL: {coin} {direcao}"

        context.bot.send_message(chat_id=CHAT_ID, text=msg)

# =========================
# RELATÓRIO
# =========================
def relatorio(context):
    historico = carregar_historico()
    wins = historico.count("WIN")
    loss = historico.count("LOSS")

    msg = f"""
📊 RELATÓRIO

WIN: {wins}
LOSS: {loss}
TOTAL: {len(historico)}

🧠 Arquiteto
"""
    context.bot.send_message(chat_id=CHAT_ID, text=msg)

# =========================
# START
# =========================
def start(update, context):
    update.message.reply_text("🤖 ARQUITETO PRO ONLINE")

# =========================
# INICIAR
# =========================
updater = Updater(TOKEN, use_context=True)
dp = updater.dispatcher

dp.add_handler(CommandHandler("start", start))
dp.add_handler(CommandHandler("ligar", ligar))
dp.add_handler(CommandHandler("desligar", desligar))

job_queue = updater.job_queue

job_queue.run_repeating(rodar_bot, interval=60, first=10)
job_queue.run_repeating(relatorio, interval=3600, first=60)

print("🚀 BOT RODANDO...")

updater.start_polling()
updater.idle()
