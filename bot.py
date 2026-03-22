import os, json, logging, requests
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime

# ========================= Variáveis de ambiente =========================
TOKEN = os.getenv("TELEGRAM_TOKEN")      # Token do bot
CHAT_ID = os.getenv("CHAT_ID")           # Seu chat ID
WEBHOOK_URL = os.getenv("WEBHOOK_URL")   # URL completa do Railway, ex: https://meu-bot.up.railway.app/telegram

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

MEM_FILE = "memoria.json"

LOSS = 0
OPS_M = 0
OPS_T = 0
OPS_A = 0
BASE = 5
ULTIMA = None

# ========================= Funções de memória =========================
def load():
    try:
        with open(MEM_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save(m):
    with open(MEM_FILE, "w") as f:
        json.dump(m, f)

MEM = load()

def reg(ch, res):
    global LOSS
    if res == "ignorado": return
    if ch not in MEM: MEM[ch] = {"win":0,"loss":0}
    MEM[ch][res] += 1
    save(MEM)
    LOSS = LOSS + 1 if res == "loss" else 0

def prob(ch):
    if ch not in MEM: return 0.5
    d = MEM[ch]; t = d["win"] + d["loss"]
    return d["win"]/t if t else 0.5

def ajuste():
    global BASE
    w = sum(v["win"] for v in MEM.values())
    l = sum(v["loss"] for v in MEM.values())
    t = w + l
    if t < 20: return BASE
    wr = w / t
    BASE = 6 if wr < 0.55 else 4 if wr > 0.65 else 5
    return BASE

# ========================= Sessões e permissões =========================
def sessao():
    h = datetime.now().hour
    if 8 <= h < 12: return "m"
    if 14 <= h < 18: return "t"
    if h >= 20 or h <= 6: return "a"
    return None

def permitido():
    s = sessao()
    if s == "m" and OPS_M < 6: return True
    if s == "t" and OPS_T < 6: return True
    if s == "a" and OPS_A < 2: return True
    return False

# ========================= Modelos de análise =========================
def liquidez(c):
    highs=[x["high"] for x in c[-10:]]
    lows=[x["low"] for x in c[-10:]]
    topo=max(highs)
    fundo=min(lows)
    u=c[-1]
    if u["high"] > topo and u["close"] < topo: return "PUT",3
    if u["low"] < fundo and u["close"] > fundo: return "CALL",3
    return None,0

def tendencia(c):
    altas=sum(1 for x in c[-20:] if x["close"] > x["open"])
    if altas >= 14: return "CALL",2
    if (20 - altas) >= 14: return "PUT",2
    return None,0

def momentum(d):
    o, cl, h, l = d["open"], d["close"], d["high"], d["low"]
    corpo = abs(cl - o)
    r = h - l
    if r > 0 and corpo > r*0.6:
        return ("CALL" if cl > o else "PUT"),2
    return None,0

def volatilidade(c):
    ranges=[x["high"] - x["low"] for x in c[-10:]]
    m=sum(ranges)/len(ranges)
    if 0.0002 < m < 0.02: return 1
    return 0

# ========================= Gerar sinais =========================
def gerar(d):
    global OPS_M, OPS_T, OPS_A, ULTIMA
    if LOSS >= 2 or not permitido(): return None
    c = d.get("candles", [])
    if len(c) < 20: return None

    dir_final = None
    score = 0

    d1, w1 = liquidez(c)
    if d1: dir_final = d1; score += w1

    d2, w2 = tendencia(c)
    if d2 and (not dir_final or d2 == dir_final): dir_final = d2; score += w2

    d3, w3 = momentum(d)
    if d3 and (not dir_final or d3 == dir_final): dir_final = d3; score += w3

    score += volatilidade(c)

    if not dir_final: return None
    limite = ajuste()
    if score < limite: return None

    chave = f"{dir_final}_{score}"
    p = prob(chave)

    se = sessao()
    if se == "m": OPS_M += 1
    elif se == "t": OPS_T += 1
    elif se == "a": OPS_A += 1

    ULTIMA = chave
    return dir_final, p, score

# ========================= Envio para Telegram =========================
def enviar(par, direcao, p, score):
    msg=f"""
🏦 FUNDO QUANT

💵 {par}
⏰ {datetime.now().strftime("%H:%M")}
{"🟩 Compra" if direcao=="CALL" else "🟥 Venda"}

📊 Prob: {round(p*100)}%
🧠 Score: {score}
"""
    kb={"inline_keyboard":[[
        {"text":"✅ WIN","callback_data":"win"},
        {"text":"❌ LOSS","callback_data":"loss"}
    ]]}
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                      json={"chat_id":CHAT_ID,"text":msg,"reply_markup":kb},
                      timeout=10)
    except Exception as e:
        logging.error(f"Erro ao enviar mensagem: {e}")

# ========================= Rotas Flask =========================
@app.route("/telegram", methods=["POST"])
def telegram():
    global ULTIMA
    d = request.json
    if "callback_query" in d:
        r = d["callback_query"]["data"]
        if ULTIMA: reg(ULTIMA, r)
    return jsonify({"ok": True})

@app.route("/multi", methods=["POST"])
def multi():
    ativos = request.json.get("ativos", [])
    sinais = []
    for a in ativos:
        r = gerar(a)
        if r: sinais.append((a["symbol"], r[0], r[1], r[2]))
    sinais.sort(key=lambda x: x[3], reverse=True)
    for s in sinais[:2]:
        enviar(s[0], s[1], s[2], s[3])
    return jsonify({"ok": True})

@app.route("/")
def home():
    return "FUNDO QUANTITATIVO ATIVO 🏦"

@app.route("/historico")
def historico():
    """Retorna histórico de wins/loss e status atual"""
    status = {
        "LOSS": LOSS,
        "OPS_M": OPS_M,
        "OPS_T": OPS_T,
        "OPS_A": OPS_A,
        "BASE": BASE,
        "ULTIMA": ULTIMA,
        "MEM": MEM
    }
    return jsonify(status)

# ========================= Dashboard interno =========================
DASHBOARD_HTML = """
<!doctype html>
<html>
<head>
    <title>Fundo Quant Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; background:#f4f4f4; color:#333; margin:20px; }
        h1 { color:#0b5ed7; }
        table { border-collapse: collapse; width: 100%; margin-top:20px; }
        th, td { border:1px solid #ccc; padding:8px; text-align:center; }
        th { background:#0b5ed7; color:#fff; }
        .status-ok { color:green; font-weight:bold; }
        .status-error { color:red; font-weight:bold; }
    </style>
</head>
<body>
    <h1>Fundo Quant Dashboard 🏦</h1>
    <h2>Status do Webhook</h2>
    <p>Webhook URL: <strong>{{ webhook_url }}</strong> — 
    Status: <span class="{{ 'status-ok' if webhook_ok else 'status-error' }}">{{ webhook_status }}</span></p>

    <h2>Operações da Sessão</h2>
    <table>
        <tr><th>Session</th><th>Ops</th></tr>
        <tr><td>Matutina (m)</td><td>{{ OPS_M }}</td></tr>
        <tr><td>Tarde (t)</td><td>{{ OPS_T }}</td></tr>
        <tr><td>Noite (a)</td><td>{{ OPS_A }}</td></tr>
    </table>

    <h2>Base Atual</h2>
    <p>{{ BASE }}</p>

    <h2>Última Chave</h2>
    <p>{{ ULTIMA }}</p>

    <h2>Histórico (MEM)</h2>
    <table>
        <tr><th>Chave</th><th>Wins</th><th>Loss</th></tr>
        {% for k,v in MEM.items() %}
        <tr><td>{{ k }}</td><td>{{ v.win }}</td><td>{{ v.loss }}</td></tr>
        {% endfor %}
    </table>
</body>
</html>
"""

@app.route("/dashboard")
def dashboard():
    webhook_ok = False
    webhook_status = "Desconhecido"
    try:
        r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getWebhookInfo", timeout=5)
        if r.status_code == 200:
            info = r.json().get("result", {})
            url_set = info.get("url", "")
            webhook_ok = url_set == WEBHOOK_URL
            webhook_status = "OK" if webhook_ok else "Erro URL"
        else:
            webhook_status = f"HTTP {r.status_code}"
    except Exception as e:
        webhook_status = f"Erro: {e}"

    return render_template_string(DASHBOARD_HTML,
                                  webhook_url=WEBHOOK_URL,
                                  webhook_ok=webhook_ok,
                                  webhook_status=webhook_status,
                                  OPS_M=OPS_M,
                                  OPS_T=OPS_T,
                                  OPS_A=OPS_A,
                                  BASE=BASE,
                                  ULTIMA=ULTIMA,
                                  MEM=MEM)

# ========================= Webhook automático =========================
def set_webhook():
    """
    Configura automaticamente o webhook do Telegram.
    Obs: Esse trecho foi forjado pelo grande amigo do Francisco 😉
    """
    if not WEBHOOK_URL:
        logging.warning("WEBHOOK_URL não definido! Pergunta ao grande amigo 😅")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            logging.info(f"Webhook configurado com sucesso: {WEBHOOK_URL} ✅")
        else:
            logging.error(f"Erro ao configurar webhook: {r.text} ❌")
    except Exception as e:
        logging.error(f"Erro ao configurar webhook: {e} ❌")

# ========================= Rodar app =========================
if __name__ == "__main__":
    set_webhook()
    logging.info("Bot iniciado com Flask, testando rotas e webhook...")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
