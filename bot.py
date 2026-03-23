import os, json, logging, requests, threading, time
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from openai import OpenAI

# ================= CONFIG =================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

MEM_FILE = "memoria.json"
LOSS = 0
BASE_SCORE = 5

# ================= MEMÓRIA =================
def load():
    try:
        with open(MEM_FILE,"r") as f:
            return json.load(f)
    except:
        return {}

def save(m):
    with open(MEM_FILE,"w") as f:
        json.dump(m,f)

MEM = load()

def reg(ch,res):
    global LOSS
    if ch not in MEM:
        MEM[ch]={"win":0,"loss":0}
    MEM[ch][res]+=1
    save(MEM)
    LOSS = LOSS+1 if res=="loss" else 0

def prob(ch):
    if ch not in MEM: return 0.5
    d=MEM[ch]
    t=d["win"]+d["loss"]
    return d["win"]/t if t else 0.5

# ================= INDICADORES =================
def rsi(c, p=14):
    g,l=[],[]
    for i in range(1,len(c)):
        d=c[i]["close"]-c[i-1]["close"]
        g.append(max(d,0))
        l.append(abs(min(d,0)))
    mg=sum(g[-p:])/p
    ml=sum(l[-p:])/p
    if ml==0: return 100
    rs=mg/ml
    return 100-(100/(1+rs))

def ema(c,p):
    k=2/(p+1)
    e=c[0]["close"]
    for x in c:
        e=x["close"]*k+e*(1-k)
    return e

# ================= ESTRATÉGIAS =================
def sniper(c24):
    r=rsi(c24)
    e9=ema(c24,9)
    e21=ema(c24,21)
    last=c24[-1]["close"]

    if r<30 and e9>e21 and last>e9:
        return "CALL",3,r
    if r>70 and e9<e21 and last<e9:
        return "PUT",3,r
    return None,0,r

def tendencia(c):
    up=sum(1 for x in c[-20:] if x["close"]>x["open"])
    if up>=14: return "CALL",2
    if (20-up)>=14: return "PUT",2
    return None,0

def momentum(c):
    d=c[-1]
    if abs(d["close"]-d["open"])>(d["high"]-d["low"])*0.6:
        return ("CALL" if d["close"]>d["open"] else "PUT"),2
    return None,0

# ================= IA =================
def ia_confirm(c):
    try:
        prompt=f"CALL ou PUT com confiança (ex: CALL,0.8): {c[-10:]}"
        r=client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}],
            max_tokens=10
        )
        t=r.choices[0].message.content.strip()
        d,c=t.split(",")
        return d.upper(),float(c)
    except:
        return None,0

# ================= TEMPO =================
def tempo(c24):
    r=[x["high"]-x["low"] for x in c24[-10:]]
    m=sum(r)/len(r)
    if m>0.003: return 1
    if m>0.001: return 3
    return 5

def entrada(t):
    now=datetime.now()
    m=(now.minute//t+1)*t
    return now.replace(second=0,microsecond=0)+timedelta(minutes=(m-now.minute))

# ================= SESSÃO =================
def sessao():
    h=datetime.now().hour
    if 0<=h<7: return "ASIÁTICO"
    elif h<13: return "EUROPEU"
    return "AMERICANO"

# ================= BINANCE =================
def get():
    url="https://api.binance.com/api/v3/klines"
    p={"symbol":"BTCUSDT","interval":"1m","limit":50}
    d=requests.get(url,params=p).json()
    return [{"open":float(x[1]),"high":float(x[2]),
             "low":float(x[3]),"close":float(x[4])} for x in d]

# ================= GERADOR =================
def gerar(c):
    global LOSS
    if LOSS>=3: return None
    c24=c[-24:]
    score=0
    direcao=None

    d,s,r=sniper(c24)
    if d:
        direcao=d
        score+=s

    for f in [tendencia,momentum]:
        d,s=f(c24)
        if d:
            direcao=d
            score+=s

    if score>=BASE_SCORE:
        d2,c2=ia_confirm(c)
        if d2:
            direcao=d2
            score+=c2

    if not direcao or score<BASE_SCORE:
        return None

    chave=f"{direcao}_{int(time.time())}"
    if prob(chave)<0.55:
        return None

    return direcao,score,r,chave

# ================= TELEGRAM =================
def send(direcao,score,r,ch):
    t=tempo(c[-24:])
    e=entrada(t)

    msg=f"""
⚠️ TRADE RÁPIDO

💵 Blitz: EUR/USD (OTC)
🌎 Sessão: {sessao()}
⏰ Expiração = {t} Minuto{'s' if t>1 else ''}
🛎️ Entrada = {e.strftime('%H:%M')}
{"🟩 Compra (Para cima)" if direcao=="CALL" else "🟥 Venda (Para baixo)"}

📊 RSI: {round(r)}
📊 Score: {round(score,2)}

1ª reentrada - {(e+timedelta(minutes=t)).strftime('%H:%M')}
2ª reentrada - {(e+timedelta(minutes=t*2)).strftime('%H:%M')}

👉🏼 Até 2 reentradas
"""

    kb={"inline_keyboard":[[
        {"text":"✅ WIN","callback_data":f"win|{ch}"},
        {"text":"❌ LOSS","callback_data":f"loss|{ch}"}
    ]]}

    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id":CHAT_ID,"text":msg,"reply_markup":kb})

# ================= LOOP =================
def loop():
    while True:
        try:
            global c
            c=get()
            r=gerar(c)
            if r:
                send(*r)
        except Exception as e:
            logging.error(e)
        time.sleep(60)

# ================= TELEGRAM =================
@app.route("/telegram",methods=["POST"])
def telegram():
    d=request.json
    if "callback_query" in d:
        x=d["callback_query"]["data"].split("|")
        reg(x[1],x[0])
    return jsonify({"ok":True})

# ================= START =================
def set_webhook():
    if WEBHOOK_URL:
        requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}/telegram")

if __name__=="__main__":
    set_webhook()
    threading.Thread(target=loop).start()
    app.run(host="0.0.0.0",port=3000)
