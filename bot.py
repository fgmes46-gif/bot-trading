import os, json, logging, requests, threading, time
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from openai import OpenAI

# ========================= ENV =========================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

MEM_FILE = "memoria.json"
LOSS = 0
BASE = 5

# ========================= STATUS =========================
@app.route("/")
def home():
    return "🤖 BOT ONLINE"

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
    if ch not in MEM:
        MEM[ch] = {"win":0,"loss":0}
    MEM[ch][res] += 1
    save(MEM)
    LOSS = LOSS + 1 if res == "loss" else 0

def prob(ch):
    if ch not in MEM: return 0.5
    d = MEM[ch]
    t = d["win"] + d["loss"]
    return d["win"]/t if t else 0.5

# ========================= OPENAI =========================
def analizar_ia(candles):
    try:
        prompt = f"Analise os candles e responda CALL ou PUT com confiança 0-1:\n{candles}"
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role":"system","content":"Você é um trader profissional."},
                {"role":"user","content":prompt}
            ],
            temperature=0.2,
            max_tokens=20
        )
        txt = r.choices[0].message.content.strip()
        d, c = txt.split(",")
        return d.upper(), float(c)
    except Exception as e:
        logging.error(f"Erro IA: {e}")
        return None, 0

# ========================= ESTRATÉGIAS =========================
def liquidez(c):
    highs = [x["high"] for x in c[-10:]]
    lows = [x["low"] for x in c[-10:]]
    topo = max(highs)
    fundo = min(lows)
    u = c[-1]

    if u["high"] > topo and u["close"] < topo:
        return "PUT", 3
    if u["low"] < fundo and u["close"] > fundo:
        return "CALL", 3
    return None, 0

def tendencia(c):
    altas = sum(1 for x in c[-20:] if x["close"] > x["open"])
    if altas >= 14:
        return "CALL", 2
    if (20-altas) >= 14:
        return "PUT", 2
    return None, 0

def momentum(d):
    o, cl, h, l = d["open"], d["close"], d["high"], d["low"]
    if abs(cl-o) > (h-l)*0.6:
        return ("CALL" if cl>o else "PUT"), 2
    return None, 0

def volatilidade(c):
    ranges = [x["high"]-x["low"] for x in c[-10:]]
    m = sum(ranges)/len(ranges)
    if 0.0002 < m < 0.02:
        return "OK", 1
    return None, 0

# ========================= GERAR =========================
def gerar(candles):
    if len(candles) < 20:
        return None

    score = 0
    direcao = None

    for func in [liquidez, tendencia, lambda x: momentum(x[-1])]:
        d, s = func(candles)
        if d:
            direcao = d
            score += s

    _, s_vol = volatilidade(candles)
    score += s_vol

    if score >= 4:
        ia_dir, ia_conf = analizar_ia(candles[-10:])
        if ia_dir:
            direcao = ia_dir
            score += ia_conf

    if not direcao or score < BASE:
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
🧠 Score: {round(score,2)}

1ª reentrada - {(datetime.now()+timedelta(minutes=1)).strftime('%H:%M')}
2ª reentrada - {(datetime.now()+timedelta(minutes=2)).strftime('%H:%M')}
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
    except Exception as e:
        logging.error(f"Erro Binance: {e}")
        return []

# ========================= LOOP =========================
def loop():
    # mensagem de vida
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": "🟢 Bot ONLINE e monitorando mercado..."})

    while True:
        try:
            for par in ["BTCUSDT","ETHUSDT"]:
                logging.info(f"🔎 Analisando {par}")
                candles = get_binance(par)

                if candles:
                    r = gerar(candles)
                    if r:
                        enviar(par, *r)

        except Exception as e:
            logging.error(f"Erro loop: {e}")

        time.sleep(60)

# ========================= TELEGRAM =========================
@app.route("/telegram", methods=["POST"])
def telegram():
    d = request.json

    if "callback_query" in d:
        data = d["callback_query"]["data"].split("|")
        reg(data[1], data[0])

    return jsonify({"ok":True})

# ========================= START =========================
def set_webhook():
    if WEBHOOK_URL:
        requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}/telegram")

if __name__ == "__main__":
    set_webhook()
    threading.Thread(target=loop).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
