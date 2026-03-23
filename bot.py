import os, json, logging, requests, openai, threading, time
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

# ========================= ENV =========================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

MEM_FILE = "memoria.json"
LOSS = 0
OPS_M = OPS_T = OPS_A = 0
BASE = 5

# ========================= MEMÓRIA =========================
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

# ========================= IA =========================
def analizar_ia(candles, setor):
    try:
        prompt = f"Analise os candles {candles}. Responda CALL ou PUT e confiança 0-1"
        r = openai.Completion.create(
            model="text-davinci-003",
            prompt=prompt,
            temperature=0,
            max_tokens=10
        )
        txt = r.choices[0].text.strip().split(",")
        return txt[0].upper(), float(txt[1])
    except:
        return None, 0

# ========================= ESTRATÉGIAS =========================
def tendencia(c):
    altas = sum(1 for x in c[-20:] if x["close"] > x["open"])
    if altas >= 14: return "CALL", 2
    if (20-altas) >= 14: return "PUT", 2
    return None, 0

def momentum(d):
    if abs(d["close"]-d["open"]) > (d["high"]-d["low"])*0.6:
        return ("CALL" if d["close"]>d["open"] else "PUT"), 2
    return None, 0

# ========================= GERAR =========================
def gerar(d):
    c = d["candles"]
    if len(c) < 20: return None

    score = 0
    direcao = None

    for func in [tendencia, lambda x: momentum(x[-1])]:
        d1, s1 = func(c)
        if d1: direcao = d1
        score += s1

    if score < BASE or not direcao:
        return None

    chave = f"{direcao}_{score}_{int(time.time())}"
    return direcao, prob(chave), score, chave

# ========================= TELEGRAM =========================
def enviar(par, direcao, p, score, chave):
    msg = f"""
⚠️ TRADE RÁPIDO

💵 {par}
⏰ {datetime.now().strftime("%H:%M")}
{"🟩 Compra" if direcao=="CALL" else "🟥 Venda"}

📊 Prob: {round(p*100)}%
🧠 Score: {score}
"""

    kb = {
        "inline_keyboard":[[
            {"text":"✅ WIN","callback_data":f"win|{chave}"},
            {"text":"❌ LOSS","callback_data":f"loss|{chave}"}
        ]]
    }

    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id":CHAT_ID,"text":msg,"reply_markup":kb})

# ========================= BINANCE =========================
def get_binance(symbol):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol":symbol,"interval":"1m","limit":50}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        return [{
            "open":float(c[1]),
            "high":float(c[2]),
            "low":float(c[3]),
            "close":float(c[4])
        } for c in data]
    except:
        return []

# ========================= LOOP =========================
def loop():
    while True:
        try:
            for par in ["BTCUSDT","ETHUSDT"]:
                candles = get_binance(par)
                if candles:
                    r = gerar({"candles":candles})
                    if r:
                        enviar(par, *r)
        except Exception as e:
            logging.error(e)

        time.sleep(60)

# ========================= TELEGRAM WEBHOOK =========================
@app.route("/telegram", methods=["POST"])
def telegram():
    d = request.json

    if "callback_query" in d:
        data = d["callback_query"]["data"].split("|")
        acao = data[0]
        chave = data[1]
        reg(chave, acao)

    return jsonify({"ok":True})

# ========================= START =========================
def set_webhook():
    if WEBHOOK_URL:
        requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}/telegram")

if __name__ == "__main__":
    set_webhook()
    threading.Thread(target=loop).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
