import os, json, requests
from flask import Flask, request
from datetime import datetime, timedelta

# ================= CONFIG =================
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
    wins, losses = 0, 0

    for k in MEM:
        if k.startswith(direcao):
            wins += MEM[k]["win"]
            losses += MEM[k]["loss"]

    total = wins + losses
    return wins / total if total > 0 else 0.55

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
        entrada = datetime.strptime(d["entrada"], "%H:%M")
        tempo = int(d["tempo"])

        r1 = (entrada + timedelta(minutes=tempo)).strftime("%H:%M")
        r2 = (entrada + timedelta(minutes=tempo * 2)).strftime("%H:%M")

        par = d['par'].replace("USDT", "/USDT")

        msg = f"""
⚠️ TRADE RÁPIDO

💵 {par}
⏰ Expiração = {tempo} Minuto
🛎️ Entrada = {d['entrada']}
{d['direcao']}

1ª reentrada - {r1}
2ª reentrada - {r2}

👉🏼 Até 2 reentradas se necessário
"""

        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

        res = requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": msg
        })

        # ===== BOTÕES =====
        if res.status_code == 200:
            kb = {
                "inline_keyboard": [[
                    {"text": "🟢 WIN", "callback_data": f"win|{d['id']}"},
                    {"text": "🔴 LOSS", "callback_data": f"loss|{d['id']}"}
                ]]
            }

            requests.post(url, json={
                "chat_id": CHAT_ID,
                "text": "Resultado da operação:",
                "reply_markup": kb
            })

    except Exception as e:
        print("❌ ERRO TELEGRAM:", e)

# ================= CALLBACK (WIN / LOSS) =================
@app.route("/callback", methods=["POST"])
def callback():
    global MEM

    data = request.json
    print("📩 CALLBACK:", data)

    try:
        cb = data["callback_query"]
        action, trade_id = cb["data"].split("|")

        if trade_id in MEM:
            if action == "win":
                MEM[trade_id]["win"] += 1
            elif action == "loss":
                MEM[trade_id]["loss"] += 1

            MEM[trade_id]["status"] = action
            save(MEM)

            print(f"✅ RESULTADO SALVO: {action} - {trade_id}")

        return {"ok": True}

    except Exception as e:
        print("❌ ERRO CALLBACK:", e)
        return {"ok": False}

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

# ================= TESTE =================
@app.route("/teste")
def teste():
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": "🚀 TESTE OK"
        }
    )
    return "ok"

# ================= STATUS =================
@app.route("/")
def home():
    return "🚂 BOT TRADING PROFISSIONAL ONLINE"
