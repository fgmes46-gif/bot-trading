import os, json, requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)

MEM_FILE = "memoria.json"
MAX_SINAIS_DIA = 18

# ================= MEMÓRIA =================
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

# ================= CONTADOR DIÁRIO =================
def sinais_hoje():
    hoje = datetime.now().strftime("%Y-%m-%d")
    return sum(1 for k in MEM if MEM[k]["data"] == hoje)

# ================= PROBABILIDADE =================
def prob(direcao):
    wins = 0
    losses = 0

    for k in MEM:
        if k.startswith(direcao):
            wins += MEM[k]["win"]
            losses += MEM[k]["loss"]

    total = wins + losses
    if total == 0:
        return 0.55

    return wins / total

# ================= VALIDAÇÃO =================
def validar(d):
    rsi = d.get("rsi", 50)
    direcao = d["direcao"]

    if direcao == "CALL" and rsi < 35:
        return True
    if direcao == "PUT" and rsi > 65:
        return True

    if 40 < rsi < 60:
        return True

    return False

# ================= TELEGRAM =================
def enviar(d):
    entrada = datetime.strptime(d["entrada"], "%H:%M")
    tempo = d["tempo"]

    r1 = (entrada + timedelta(minutes=tempo)).strftime("%H:%M")
    r2 = (entrada + timedelta(minutes=tempo*2)).strftime("%H:%M")

    msg = f"""
⚠️ TRADE RÁPIDO

💵 Blitz: {d['par']}
⏰ Expiração = {tempo} Minuto{'s' if tempo>1 else ''}
🛎️ Entrada = {d['entrada']}
{"🟩 Compra (Para cima)" if d['direcao']=="CALL" else "🟥 Venda (Para baixo)"}

1ª reentrada - {r1}
2ª reentrada - {r2}

👉🏼 Até 2 reentradas se necessário

➡️ Clique aqui para abrir a corretora
"""

    kb = {
        "inline_keyboard":[[
            {"text":"🟢 WIN","callback_data":f"win|{d['id']}"},
            {"text":"🔴 LOSS","callback_data":f"loss|{d['id']}"}
        ]]
    }

    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": msg,
            "reply_markup": kb
        }
    )

# ================= RECEBER SINAL =================


    d = request.json

    @app.route('/sinal', methods=['POST'])
def receber_sinal():

    
    print("🔥 SINAL RECEBIDO:", data)  # 👈 ADICIONA ISSO


    # limite diário
    if sinais_hoje() >= MAX_SINAIS_DIA:
        return {"ok": False, "msg": "limite diário"}

    # validação leve
    if not validar(d):
        return {"ok": False, "msg": "reprovado"}

    # confiança histórica
    confianca = prob(d["direcao"])

    if confianca < 0.50:
        return {"ok": False, "msg": "baixa confiança"}

    # ID único
    trade_id = f"{d['direcao']}_{int(datetime.now().timestamp())}"

    MEM[trade_id] = {
        "win": 0,
        "loss": 0,
        "data": datetime.now().strftime("%Y-%m-%d"),
        "status": "pending"  # <- importante
    }

    save(MEM)

    d["id"] = trade_id

    enviar(d)

    return {"ok": True}

# ================= TELEGRAM CALLBACK =================
@app.route("/telegram", methods=["POST"])
def telegram():
    global MEM

    data = request.json

    if "callback_query" in data:
        res, trade_id = data["callback_query"]["data"].split("|")

        if trade_id in MEM and MEM[trade_id]["status"] == "pending":
            MEM[trade_id][res] += 1
            MEM[trade_id]["status"] = "done"  # <- trava duplicação
            save(MEM)

    return jsonify({"ok": True})

# ================= STATUS =================
@app.route("/")
def home():
    return "🚂 Railway Inteligente FINAL ONLINE"
