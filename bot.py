import os, json, logging, requests
from flask import Flask, request
from datetime import datetime

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

MEM_FILE="memoria.json"

LOSS=0
OPS_M=0
OPS_T=0
OPS_A=0

BASE=5
ULTIMA=None

def load():
    try: return json.load(open(MEM_FILE))
    except: return {}

def save(m): json.dump(m,open(MEM_FILE,"w"))

MEM=load()

# =========================
def reg(ch,res):
    global LOSS
    if res=="ignorado": return
    if ch not in MEM: MEM[ch]={"win":0,"loss":0}
    MEM[ch][res]+=1
    save(MEM)
    LOSS = LOSS+1 if res=="loss" else 0

def prob(ch):
    if ch not in MEM: return 0.5
    d=MEM[ch]; t=d["win"]+d["loss"]
    return d["win"]/t if t else 0.5

def ajuste():
    global BASE
    w=sum(v["win"] for v in MEM.values())
    l=sum(v["loss"] for v in MEM.values())
    t=w+l
    if t<20: return BASE
    wr=w/t
    BASE = 6 if wr<0.55 else 4 if wr>0.65 else 5
    return BASE

# =========================
def sessao():
    h=datetime.now().hour
    if 8<=h<12: return "m"
    if 14<=h<18: return "t"
    if h>=20 or h<=6: return "a"
    return None

def permitido():
    s=sessao()
    if s=="m" and OPS_M<6: return True
    if s=="t" and OPS_T<6: return True
    if s=="a" and OPS_A<2: return True
    return False

# =========================
# MODELOS
# =========================
def liquidez(c):
    highs=[x["high"] for x in c[-10:]]
    lows=[x["low"] for x in c[-10:]]

    topo=max(highs)
    fundo=min(lows)
    u=c[-1]

    if u["high"]>topo and u["close"]<topo:
        return "PUT",3

    if u["low"]<fundo and u["close"]>fundo:
        return "CALL",3

    return None,0

def tendencia(c):
    altas=sum(1 for x in c[-20:] if x["close"]>x["open"])
    if altas>=14: return "CALL",2
    if (20-altas)>=14: return "PUT",2
    return None,0

def momentum(d):
    o,cl,h,l=d["open"],d["close"],d["high"],d["low"]
    corpo=abs(cl-o)
    r=h-l
    if r>0 and corpo>r*0.6:
        return ("CALL" if cl>o else "PUT"),2
    return None,0

def volatilidade(c):
    ranges=[x["high"]-x["low"] for x in c[-10:]]
    m=sum(ranges)/len(ranges)
    if 0.0002 < m < 0.02:
        return 1
    return 0

# =========================
def gerar(d):
    global OPS_M, OPS_T, OPS_A, ULTIMA

    if LOSS>=2 or not permitido():
        return None

    c=d.get("candles",[])
    if len(c)<20: return None

    dir_final=None
    score=0

    # liquidez
    d1,w1=liquidez(c)
    if d1:
        dir_final=d1
        score+=w1

    # tendencia
    d2,w2=tendencia(c)
    if d2 and (not dir_final or d2==dir_final):
        dir_final=d2
        score+=w2

    # momentum
    d3,w3=momentum(d)
    if d3 and (not dir_final or d3==dir_final):
        dir_final=d3
        score+=w3

    score+=volatilidade(c)

    if not dir_final:
        return None

    limite=ajuste()
    if score < limite:
        return None

    chave=f"{dir_final}_{score}"
    p=prob(chave)

    se=sessao()
    if se=="m": OPS_M+=1
    elif se=="t": OPS_T+=1
    elif se=="a": OPS_A+=1

    ULTIMA=chave

    return dir_final,p,score

# =========================
def enviar(par,direcao,p,score):
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

    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
    json={"chat_id":CHAT_ID,"text":msg,"reply_markup":kb})

# =========================
@app.route("/telegram",methods=["POST"])
def telegram():
    global ULTIMA
    d=request.json
    if "callback_query" in d:
        r=d["callback_query"]["data"]
        if ULTIMA: reg(ULTIMA,r)
    return {"ok":True}

# =========================
@app.route("/multi",methods=["POST"])
def multi():
    ativos=request.json.get("ativos",[])

    sinais=[]
    for a in ativos:
        r=gerar(a)
        if r:
            sinais.append((a["symbol"],r[0],r[1],r[2]))

    sinais.sort(key=lambda x:x[3],reverse=True)

    for s in sinais[:2]:
        enviar(s[0],s[1],s[2],s[3])

    return {"ok":True}

# =========================
@app.route("/")
def home():
    return "FUNDO QUANTITATIVO ATIVO 🏦"

# =========================
if __name__=="__main__":
    app.run(host="0.0.0.0",port=3000)
