import requests
import time
import random
from datetime import datetime, timedelta
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, CallbackContext

print("🚀 BOT RADAR ULTRA INICIADO")

TOKEN = "8787052983:AAF356OSvJ6lnzodM7dRWXQMR_8i1JJHlIc"
CHAT_ID = "SEU_CHAT_ID"

bot = Bot(token=TOKEN)

bot_active = False

asia_open_alert = False
asia_close_alert = False

# ===============================
# COMANDOS TELEGRAM
# ===============================

def ligar(update: Update, context: CallbackContext):
    global bot_active
    bot_active = True
    update.message.reply_text("✅ Bot ligado")

def desligar(update: Update, context: CallbackContext):
    global bot_active
    bot_active = False
    update.message.reply_text("⛔ Bot desligado")

def status(update: Update, context: CallbackContext):

    if bot_active:
        s = "🟢 ATIVO"
    else:
        s = "🔴 DESLIGADO"

    update.message.reply_text(f"Status do bot: {s}")

# ===============================
# MERCADO ASIATICO
# ===============================

def asian_market():

    global asia_open_alert
    global asia_close_alert

    now = datetime.utcnow()
    hour = now.hour

    if hour == 0 and not asia_open_alert:

        bot.send_message(chat_id=CHAT_ID,
        text="🌏 Mercado Asiático ABERTO")

        asia_open_alert = True
        asia_close_alert = False

    if hour == 8 and not asia_close_alert:

        bot.send_message(chat_id=CHAT_ID,
        text="🌏 Mercado Asiático FECHANDO")

        asia_close_alert = True
        asia_open_alert = False

# ===============================
# PEGAR MERCADO
# ===============================

def get_markets():

    url = "https://api.coingecko.com/api/v3/coins/markets"

    params = {
        "vs_currency":"usd",
        "order":"market_cap_desc",
        "per_page":300,
        "page":1
    }

    r = requests.get(url,params=params)

    return r.json()

# ===============================
# DETECTAR PUMP
# ===============================

def pump_detector(volume,marketcap):

    if marketcap == 0:
        return False

    if volume > marketcap * 0.08:
        return True

    return False

# ===============================
# ANALISE
# ===============================

def analyze_coin(coin):

    prob = 50

    change = coin.get("price_change_percentage_24h",0)
    volume = coin.get("total_volume",0)
    marketcap = coin.get("market_cap",1)

    if change > 5:
        prob += 15

    if change < -5:
        prob += 15

    if pump_detector(volume,marketcap):
        prob += 20

    direction = "COMPRA" if change < 0 else "VENDA"

    return {
        "symbol":coin["symbol"].upper(),
        "prob":prob,
        "dir":direction
    }

# ===============================
# RANKING
# ===============================

def ranking():

    markets = get_markets()

    signals = []

    for coin in markets:

        try:

            s = analyze_coin(coin)

            if s["prob"] >= 75:
                signals.append(s)

        except:
            pass

    signals = sorted(signals,key=lambda x:x["prob"],reverse=True)

    return signals[:3]

# ===============================
# TEMPO DE ENTRADA
# ===============================

def entry_time():

    now = datetime.utcnow()

    wait = random.randint(5,8)

    entry = now + timedelta(minutes=wait)

    candle = random.choice(["1m","3m","5m","10m"])

    return now, entry, candle

# ===============================
# ENVIAR SINAL
# ===============================

def send_signal():

    if not bot_active:
        print("Bot desligado")
        return

    asian_market()

    top = ranking()

    if not top:
        print("Sem sinais fortes")
        return

    now, entry, candle = entry_time()

    msg = "📡 RADAR PROFISSIONAL\n\n"

    msg += f"⏱ Análise: {now.strftime('%H:%M')}\n"
    msg += f"🎯 Entrada: {entry.strftime('%H:%M')}\n\n"

    for s in top:

        msg += f"""
Moeda: {s['symbol']}
Direção: {s['dir']}
Candle: {candle}
Probabilidade: {s['prob']}%
"""

    bot.send_message(chat_id=CHAT_ID,text=msg)

# ===============================
# LOOP
# ===============================

def loop():

    while True:

        print("🔎 Escaneando mercado")

        try:

            send_signal()

        except Exception as e:

            print("Erro:",e)

        time.sleep(300)

# ===============================
# TELEGRAM
# ===============================

updater = Updater(TOKEN)

dp = updater.dispatcher

dp.add_handler(CommandHandler("ligar",ligar))
dp.add_handler(CommandHandler("desligar",desligar))
dp.add_handler(CommandHandler("status",status))

updater.start_polling()

loop()
