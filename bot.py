import os, json, logging
import requests
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime, timedelta, date
import plotly.graph_objects as go

# =========================
# CONFIG
# =========================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("SNIPER")

MEM_FILE = "memoria.json"

# =========================
# ESTADO
# =========================
LOSS_STREAK = 0
OPERACOES_HOJE = 0
DATA_ATUAL = date.today()

BASE_PROB = 0.60  # IA ajusta isso

# =========================
# MEMÓRIA
# =========================
def load_mem():
    try:
        return json.load(open(MEM_FILE))
    except:
        return {}

def save_mem(mem):
    json.dump(mem, open(MEM_FILE, "w"))

MEM = load_mem()

def registrar_resultado(chave, resultado):
    global LOSS_STREAK

    if chave not in MEM:
        MEM[chave] = {"win": 0, "loss": 0}

    MEM[chave][resultado] += 1
    save_mem(MEM)

    if resultado == "loss":
        LOSS_STREAK += 1
    else:
        LOSS_STREAK = 0

def probabilidade(chave):
    if chave not in MEM:
        return 0.5

    d = MEM[chave]
    total = d["win"] + d["loss"]
    return d["win"] / total if total > 0 else 0.5

# =========================
# IA ADAPTATIVA
# =========================
def ajuste_ia():
    global BASE_PROB

    total_win = sum(v["win"] for v in MEM.values())
    total_loss = sum(v["loss"] for v in MEM.values())
    total = total_win + total_loss

    if total < 20:
        return BASE_PROB

    winrate = total_win / total

    # IA ajusta exigência
    if winrate < 0.55:
        BASE_PROB = 0.65
    elif winrate > 0.65:
        BASE_PROB = 0.58
    else:
        BASE_PROB = 0.60

    return BASE_PROB

# =========================
# RESET
# =========================
def reset():
    global OPERACOES_HOJE, DATA_ATUAL
    if date.today() != DATA_ATUAL:
        OPERACOES_HOJE = 0
        DATA_ATUAL = date.today()

# =========================
# FILTROS
# =========================
def lateral(c):
    altas = sum(1 for x in c[-10:] if x["close"] > x["open"])
    baixas = 10 - altas
    return abs(altas - baixas) <= 2

def tendencia(c):
    altas = sum(1 for x in c[-20:] if x["close"] > x["open"])
    baixas = 20 - altas

    if altas >= 14: return "CALL"
    if baixas >= 14: return "PUT"
    return None

# =========================
# SINAL
# =========================
def gerar_sinal(d):
    global OPERACOES_HOJE

    reset()

    if LOSS_STREAK >= 2:
        return None, None, None

    if OPERACOES_HOJE >= 12:
        return None, None, None

    c = d.get("candles", [])
    if len(c) < 20 or lateral(c):
        return None, None, None

    tend = tendencia(c)
    if not tend:
        return None, None, None

    o, cl, h, l = d["open"], d["close"], d["high"], d["low"]

    corpo = abs(cl - o)
    r = h - l

    if r == 0 or corpo < r * 0.3:
        return None, None, None

    direcao = "CALL" if cl > o else "PUT"
    if direcao != tend:
        return None, None, None

    score = 0
    if corpo > r * 0.7: score += 2
    if direcao == "CALL" and cl > h - r * 0.15: score += 1
    if direcao == "PUT" and cl < l + r * 0.15: score += 1

    chave = f"{tend}_{score}"
    prob = probabilidade(chave)

    limite = ajuste_ia()

    if score >= 3 and prob >= limite:
        OPERACOES_HOJE += 1
        return direcao, chave, prob

    return None, None, None

# =========================
# TELEGRAM
# =========================
def enviar(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML"
    })

# =========================
# FORMAT
# =========================
def msg(par, direcao, prob):
    now = datetime.now()
    g1 = now + timedelta(minutes=1)
    g2 = now + timedelta(minutes=2)

    d = "🟩 Compra" if direcao == "CALL" else "🟥 Venda"

    return f"""
⚠️ TRADE RÁPIDO

💵 Blitz: {par}
⏰ Expiração = 1 Minuto
🛎️ Entrada = {now.strftime("%H:%M")}
{d}

📊 Probabilidade: {round(prob*100)}%

1ª reentrada - {g1.strftime("%H:%M")}
2ª reentrada - {g2.strftime("%H:%M")}

👉🏼 Até 2 reentradas

➡️ <a href="https://secure.activtrades.com/personalarea?branch=BH&lang=pt">Abrir corretora</a>
"""

# =========================
# MULTI ATIVO
# =========================
@app.route("/multi", methods=["POST"])
def multi():
    ativos = request.json.get("ativos", [])

    sinais = []

    for a in ativos:
        d, c, p = gerar_sinal(a)
        if d:
            sinais.append((a["symbol"], d, c, p))

    sinais.sort(key=lambda x: x[3], reverse=True)

    enviados = []

    for s in sinais[:2]:
        enviar(msg(s[0], s[1], s[3]))
        enviados.append(s)

    return {"enviados": enviados}

# =========================
# RESULTADO
# =========================
@app.route("/resultado", methods=["POST"])
def resultado():
    data = request.json
    registrar_resultado(data["chave"], data["resultado"])
    return {"ok": True}

# =========================
# DASHBOARD
# =========================
@app.route("/dashboard")
def dash():
    wins = sum(v["win"] for v in MEM.values())
    loss = sum(v["loss"] for v in MEM.values())

    labels = list(MEM.keys())
    valores = [probabilidade(k)*100 for k in labels]

    fig = go.Figure([go.Bar(x=labels, y=valores)])
    graph = fig.to_html(False)

    wr = (wins/(wins+loss)*100) if wins+loss>0 else 0

    return render_template_string(f"""
    <h1>📊 SNIPER PRO</h1>
    <h2>Winrate: {wr:.2f}%</h2>
    {graph}
    """)

# =========================
# HOME
# =========================
@app.route("/")
def home():
    return "SNIPER ONLINE 🚀"

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
