import os, json, requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

print("🔑 TOKEN:", TOKEN)
print("💬 CHAT_ID:", CHAT_ID)

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
    try:
        print("📡 Preparando envio...")

        entrada = datetime.strptime(d["entrada"], "%H:%M")
        tempo = d["tempo"]

        r1 = (entrada + timedelta(minutes=tempo)).strftime("%H:%M")
        r2 = (entrada + timedelta(minutes=tempo*2)).strftime("%H:%M")

        msg = f"""
TESTE BOT 🚀

Par: {d['par']}
Entrada: {d['entrada']}
Direção: {d['direcao']}
"""

        # 🔥 TESTE 1: SEM BOTÃO
        res = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": msg
            }
        )

        print("📨 STATUS:", res.status_code)
        print("📨 RESPOSTA:", res.text)

        # 🔥 TESTE 2: COM BOTÃO (só se o primeiro funcionar)
        if res.status_code == 200:
            kb = {
                "inline_keyboard":[[
                    {"text":"🟢 WIN","callback_data":f"win|{d['id']}"},
                    {"text":"🔴 LOSS","callback_data":f"loss|{d['id']}"}
                ]]
            }

            res2 = requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                json={
                    "chat_id": CHAT_ID,
                    "text": "Teste com botão",
                    "reply_markup": json.dumps(kb)
                }
            )

            print("📨 STATUS BOTÃO:", res2.status_code)
            print("📨 RESPOSTA BOTÃO:", res2.text)

    except Exception as e:
        print("❌ ERRO:", str(e))

# ================= RECEBER SINAL =================
@app.route("/sinal", methods=["POST"])
def sinal():
    global MEM

    d = request.json
    print("🔥 SINAL RECEBIDO:", d)

    if sinais_hoje() >= MAX_SINAIS_DIA:
        print("⛔ LIMITE DIÁRIO")
        return {"ok": False}

    if not validar(d):
        print("❌ REPROVADO")
        return {"ok": False}

    confianca = prob(d["direcao"])
    print("📊 CONFIANÇA:", confianca)

    if confianca < 0.50:
        print("⚠️ BAIXA CONFIANÇA")
        return {"ok": False}

    trade_id = f"{d['direcao']}_{int(datetime.now().timestamp())}"

    MEM[trade_id] = {
        "win": 0,
        "loss": 0,
        "data": datetime.now().strftime("%Y-%m-%d"),
        "status": "pending"
    }

    save(MEM)

    d["id"] = trade_id

    enviar(d)

    return {"ok": True}

# ================= TESTE MANUAL =================
@app.route("/teste")
def teste():
    print("🚀 TESTE MANUAL ACIONADO")

    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": "TESTE DIRETO VIA /teste 🚀"
        }
    )

    return "ok"

# ================= STATUS =================
@app.route("/")
def home():
    return "🚂 DEBUG ONLINE"
