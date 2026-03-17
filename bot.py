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

# -----------------------------
# PEGAR DADOS BINANCE
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

    except Exception as e:
        print("Erro get_candles:", e)
        return [], []

# =========================
# HISTÓRICO
# =========================
def carregar():
    try:
        with open(ARQUIVO,"r") as f:
            return json.load(f)
    except:
        return []

def salvar(dados):
    with open(ARQUIVO,"w") as f:
        json.dump(dados,f)

def registrar(par,direcao,prob):
    dados = carregar()
    dados.append({
        "par":par,
        "direcao":direcao,
        "prob":prob,
        "hora":datetime.now().strftime("%H"),
        "resultado":None
    })
    salvar(dados)

# =========================
# MARCAR RESULTADO
# =========================
def marcar(update,context):
    txt = update.message.text.lower()
    dados = carregar()

    if not dados:
        update.message.reply_text("Sem histórico")
        return

    if "gain" in txt:
        dados[-1]["resultado"] = "GAIN"
    elif "loss" in txt:
        dados[-1]["resultado"] = "LOSS"

    salvar(dados)
    update.message.reply_text("Resultado salvo")

# =========================
# PERFORMANCE
# =========================
def stats(update,context):
    dados = carregar()

    g = len([d for d in dados if d["resultado"]=="GAIN"])
    l = len([d for d in dados if d["resultado"]=="LOSS"])

    total = g + l

    if total == 0:
        update.message.reply_text("Sem dados")
        return

    taxa = round((g/total)*100,2)

    msg = f"""
📊 RESULTADO

Total: {total}
Gain: {g}
Loss: {l}

Assertividade: {taxa}%
"""
    update.message.reply_text(msg)

# =========================
# FILTRO INTELIGENTE
# =========================
def score_ativo(par):
    dados = carregar()

    filtrado = [d for d in dados if d["par"]==par and d["resultado"]]

    if len(filtrado) < 5:
        return 1

    g = len([d for d in filtrado if d["resultado"]=="GAIN"])
    taxa = g/len(filtrado)

    return taxa

def score_horario():
    h = datetime.now().strftime("%H")
    dados = carregar()

    filtrado = [d for d in dados if d["hora"]==h and d["resultado"]]

    if len(filtrado) < 5:
        return 1

    g = len([d for d in filtrado if d["resultado"]=="GAIN"])
    return g/len(filtrado)

# =========================
# BINANCE
# =========================
def candles(symbol):
    try:
        url=f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=50"
        data=requests.get(url).json()
        return [float(c[4]) for c in data]
    except:
        return []

# =========================
# RSI
# =========================
def rsi(c):
    if len(c)<14: return 50

    g,p=[],[]
    for i in range(1,len(c)):
        d=c[i]-c[i-1]
        g.append(max(d,0))
        p.append(abs(min(d,0)))

    ag=sum(g[-14:])/14
    ap=sum(p[-14:])/14

    if ap==0: return 100

    rs=ag/ap
    return 100-(100/(1+rs))

# =========================
# EMA
# =========================
def ema(c):
    k=2/(21+1)
    e=c[0]
    for p in c:
        e=p*k+e*(1-k)
    return e

# =========================
# HORÁRIOS
# =========================
def horario_ok():
    h=int(datetime.now().strftime("%H"))
    return (9<=h<=10) or (13<=h<=14) or (19<=h<=20) or (0<=h<=2)

# =========================
# SNIPER ADAPTATIVO
# =========================

def filtro_inteligente(prob):

    if prob >= 80:
        return "FORTE 💥"

    elif prob >= 70:
        return "BOA 🔥"

    else:
        return "FRACA ⚠️"

def analisar_sniper(par):

    if not horario_ok():
        return None

    c=candles(par)
    if not c: return None

    r=rsi(c)
    e=ema(c)
    p=c[-1]

    if 45<r<55:
        return None

    direcao=None

    if p>e and r<30:
        direcao="CALL 📈"

    elif p<e and r>70:
        direcao="PUT 📉"

    if not direcao:
        return None

    prob=75

    # ajuste inteligente
    prob += int(score_ativo(par)*10)
    prob += int(score_horario()*10)

    prob=min(prob,95)

    return direcao,prob

# -----------------------------
# SNIPER PROGRAMADO (2x por hora)
# -----------------------------

def filtro_inteligente(prob):

    if prob >= 80:
        return "FORTE 💥"

    elif prob >= 70:
        return "BOA 🔥"

    else:
        return "FRACA ⚠️"

def sniper_programado(context):

    sinais = []

    for coin in COINS:

        closes,_ = get_candles(coin)

        if not closes:
            continue

        rsi = calcular_rsi(closes)
        movimento = detectar_movimento(closes)
        prob = calcular_probabilidade(rsi, movimento)

        print(f"{coin} | RSI: {rsi} | Prob: {prob} | Mov: {movimento}")

        if prob >= 70:

            direcao = "CALL 📈" if rsi < 50 else "PUT 📉"

            sinais.append({
                "coin": coin,
                "prob": prob,
                "direcao": direcao,
                "rsi": rsi,
                "movimento": movimento
            })

    # Ordena pelos melhores
    sinais.sort(key=lambda x: x["prob"], reverse=True)

    # Pega só os 2 melhores
    melhores = sinais[:2]

    if not melhores:
        return

    from datetime import datetime, timedelta

    agora = datetime.now()

    for sinal in melhores:

        entrada = agora + timedelta(minutes=1)
        r1 = entrada + timedelta(minutes=1)
        r2 = entrada + timedelta(minutes=2)

        msg = f"""
🚨 ALERTA SNIPER AUTOMÁTICO

PAR: {sinal['coin']}

DIREÇÃO: {sinal['direcao']}
PROBABILIDADE: {sinal['prob']}%

RSI: {sinal['rsi']}
MOVIMENTO: {sinal['movimento']}

⏰ Entrada: {entrada.strftime('%H:%M')}
1ª: {r1.strftime('%H:%M')}
2ª: {r2.strftime('%H:%M')}

🧠 Arquiteto
"""

        context.bot.send_message(chat_id=CHAT_ID, text=msg)

def radar(context):

    for coin in COINS:

        closes,_ = get_candles(coin)

        if not closes:
            continue

        rsi = calcular_rsi(closes)
        movimento = detectar_movimento(closes)
        prob = calcular_probabilidade(rsi, movimento)

        if prob >= 70:

            direcao = "CALL 📈" if rsi < 50 else "PUT 📉"

            msg = f"""
🚨 RADAR AUTOMÁTICO

PAR: {coin}

RSI: {rsi}
MOVIMENTO: {movimento}

DIREÇÃO: {direcao}
PROBABILIDADE: {prob}%

⏰ Tempo: 1m
"""

            context.bot.send_message(chat_id=CHAT_ID, text=msg)

# =========================
# HORÁRIOS TRADE
# =========================
def horarios():
    agora=datetime.now()
    e=agora+timedelta(minutes=1)
    r1=e+timedelta(minutes=1)
    r2=e+timedelta(minutes=2)
    return e.strftime("%H:%M"),r1.strftime("%H:%M"),r2.strftime("%H:%M")

# =========================
# ANALISAR
# =========================
def analisar(update,context):

    txt=update.message.text.lower()

    if txt in ["gain","loss"]:
        marcar(update,context)
        return

    par=update.message.text.upper()

    if par not in COINS:
        update.message.reply_text("Par inválido")
        return

    r=analisar_sniper(par)

    if not r:
        update.message.reply_text("Sem entrada segura")
        return

    direcao,prob=r
    e,r1,r2=horarios()

    registrar(par,direcao,prob)

    msg=f"""
🚨 ALERTA INSTITUCIONAL

PAR: {par}

{direcao}
PROBABILIDADE: {prob}%

⏰ Entrada: {e}

1ª: {r1}
2ª: {r2}

🧠 Arquiteto
"""

    update.message.reply_text(msg)

# =========================
# BOT
# =========================
updater=Updater(TOKEN,use_context=True)
dp=updater.dispatcher

dp.add_handler(CommandHandler("start", lambda u,c: u.message.reply_text("🧠 ARQUITETO PRO ATIVO")))
dp.add_handler(CommandHandler("stats", stats))
dp.add_handler(MessageHandler(Filters.text & ~Filters.command, analisar))

print("✅ ARQUITETO PRO ONLINE")

print("🚀 Iniciando bot...")

job_queue = updater.job_queue

print("📡 Ativando radar...")
job_queue.run_repeating(radar, interval=600, first=20)

print("🎯 Ativando sniper programado...")
job_queue.run_repeating(sniper_programado, interval=60, first=10)

print("✅ ARQUITETO PRO ONLINE")

updater.start_polling()
updater.idle()

updater.start_polling()
updater.idle()
