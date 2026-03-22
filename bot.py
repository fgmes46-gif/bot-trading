import os, json, logging, requests, openai
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime, timedelta

# ========================= Variáveis de ambiente =========================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

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

# ========================= Modelos de análise com IA =========================
def analizar_ia(candles, setor):
    """
    Analisa cada setor com OpenAI e retorna (direcao, confianca)
    """
    try:
        prompt = f"""
Você é um trader experiente. Analise os últimos candles do setor {setor}: {candles}.
Diga se devemos 'CALL' ou 'PUT' e forneça uma confiança de 0 a 1.
Retorne no formato: DIRECAO,CONFIANCA
"""
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=prompt,
            temperature=0,
            max_tokens=10
        )
        resultado = response.choices[0].text.strip().split(",")
        direcao = resultado[0].upper()
        confianca = float(resultado[1])
        return direcao, confianca
    except Exception as e:
        logging.error(f"Erro IA setor {setor}: {e}")
        return None, 0

def liquidez(c):
    highs=[x["high"] for x in c[-10:]]
    lows=[x["low"] for x in c[-10:]]
    topo=max(highs)
    fundo=min(lows)
    u=c[-1]
    dir_final = None
    score = 0
    if u["high"] > topo and u["close"] < topo: dir_final = "PUT"; score += 3
    if u["low"] < fundo and u["close"] > fundo: dir_final = "CALL"; score += 3
    ia_dir, ia_conf = analizar_ia(c[-10:], "liquidez")
    if ia_dir in ["CALL","PUT"]: dir_final = ia_dir; score += ia_conf
    return dir_final, score

def tendencia(c):
    altas=sum(1 for x in c[-20:] if x["close"] > x["open"])
    dir_final = None
    score = 0
    if altas >= 14: dir_final = "CALL"; score += 2
    if (20 - altas) >= 14: dir_final = "PUT"; score += 2
    ia_dir, ia_conf = analizar_ia(c[-20:], "tendencia")
    if ia_dir in ["CALL","PUT"]: dir_final = ia_dir; score += ia_conf
    return dir_final, score

def momentum(d):
    o, cl, h, l = d["open"], d["close"], d["high"], d["low"]
    dir_final = None
    score = 0
    corpo = abs(cl - o)
    r = h - l
    if r > 0 and corpo > r*0.6:
        dir_final = "CALL" if cl > o else "PUT"; score += 2
    ia_dir, ia_conf = analizar_ia([d], "momentum")
    if ia_dir in ["CALL","PUT"]: dir_final = ia_dir; score += ia_conf
    return dir_final, score

def volatilidade(c):
    ranges=[x["high"] - x["low"] for x in c[-10:]]
    m=sum(ranges)/len(ranges)
    score = 0
    if 0.0002 < m < 0.02: score += 1
    ia_dir, ia_conf = analizar_ia(c[-10:], "volatilidade")
    return ia_dir, score + ia_conf

# ========================= Gerar sinais =========================
def gerar(d):
    global OPS_M, OPS_T, OPS_A, ULTIMA
    if LOSS >= 2 or not permitido(): return None
    c = d.get("candles", [])
    if len(c) < 20: return None

    dir_final = None
    score = 0

    for func in [liquidez, tendencia, momentum, volatilidade]:
        d1, s1 = func(c if func!=momentum else d)
        if d1: dir_final = d1
        score += s1

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

# ========================= Envio Telegram =========================
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

# ========================= Enviar trade Blitz =========================
def enviar_trade(par, direcao, hora_entrada, reentradas=[]):
    status = "🟩 Compra" if direcao=="CALL" else "🟥 Venda"
    msg = f"""
⚠️ TRADE RÁPIDO

💵 Blitz: {par}
⏰ Expiração = 1 Minuto
🛎️ Entrada = {hora_entrada}
{status}
"""
    for i, r in enumerate(reentradas, start=1):
        msg += f"\n{i}ª reentrada - {r}"
    msg += "\n\n👉🏼 Até 2 reentradas se necessário\n➡️ Clique aqui para abrir a corretora"
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                      json={"chat_id":CHAT_ID,"text":msg},
                      timeout=10)
    except Exception as e:
        logging.error(f"Erro ao enviar trade: {e}")

# ========================= Rotas Flask =========================
@app.route("/telegram", methods=["POST"])
def telegram():
    global ULTIMA
    d = request.json
    logging.info(f"Recebido POST do Telegram: {d}")

    if "callback_query" in d:
        r = d["callback_query"]["data"]
        if ULTIMA: reg(ULTIMA, r)

    if "message" in d:
        text = d["message"].get("text", "")
        chat_id = d["message"]["chat"]["id"]

        if text.startswith("/codex"):
            prompt = text[len("/codex "):].strip()
            codigo = gerar_codigo(prompt)
            if codigo:
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                              json={"chat_id": chat_id,"text":f"```python\n{codigo}\n```", "parse_mode":"Markdown"})
            else:
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                              json={"chat_id": chat_id,"text":"Erro ao gerar código"} )
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
        enviar_trade(
            par=s[0],
            direcao=s[1],
            hora_entrada=datetime.now().strftime("%H:%M"),
            reentradas=[
                (datetime.now() + timedelta(minutes=1)).strftime("%H:%M"),
                (datetime.now() + timedelta(minutes=2)).strftime("%H:%M")
            ]
        )
    return jsonify({"ok": True})

# ========================= Webhook automático =========================
def set_webhook():
    if not WEBHOOK_URL:
        logging.warning("WEBHOOK_URL não definido! ❌")
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

if __name__ == "__main__":
    set_webhook()
    logging.info("Bot iniciado com Flask, testando rotas e webhook...")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
