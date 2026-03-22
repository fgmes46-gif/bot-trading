# 🧠 ARQUITETO_ULTRA_AI_V4_MEMORY_BY_BROTHER

import os, time, json, threading
from datetime import datetime
from flask import Flask
from binance.client import Client
from telegram import Bot

# =========================
# CONFIG
# =========================
API_KEY = os.getenv("BINANCE_KEY")
API_SECRET = os.getenv("BINANCE_SECRET")
TOKEN = os.getenv"8266735750:AAGv7KqoN-nyFi84w7zYs893mzE0CgmTo-I"
CHAT_ID = os.getenv"8342835768"
MODO = os.getenv("MODO", "AUTO")

client = Client(API_KEY, API_SECRET)
bot = Bot(token=TOKEN)
app = Flask(__name__)

# =========================
# ESTADO
# =========================
TRADE_ATIVO = False
SYMBOL = ""
ENTRY = 0
QTD = 0
SIDE_ATUAL = "BUY"
FEATURES_ATUAL = None

RISCO = 0.02
STOP = 0.01
TAKE = 0.02
TRAIL = 0.008

TRADES_DIA = 0
LIMITE_DIA = 12

# =========================
# IA + MEMÓRIA
# =========================
AI_DB = "ai_quant.json"
MEM_DB = "memoria_trades.json"

def load_json(arq):
    try:
        return json.load(open(arq))
    except:
        return {}

def save_json(arq, data):
    json.dump(data, open(arq, "w"))

AI = load_json(AI_DB)
MEM = load_json(MEM_DB)

# =========================
# FEATURE ENGINEERING
# =========================
def features(c):
    closes = [x["close"] for x in c]
    opens = [x["open"] for x in c]
    highs = [x["high"] for x in c]
    lows = [x["low"] for x in c]
    volumes = [x["volume"] for x in c]

    ema5 = sum(closes[-5:]) / 5
    ema14 = sum(closes[-14:]) / 14
    trend = 1 if ema5 > ema14 else -1

    momentum = (closes[-1] - closes[-5]) / closes[-5]
    vol = (max(highs) - min(lows)) / closes[-1]

    vol_media = sum(volumes)/len(volumes)
    vol_spike = 1 if volumes[-1] > vol_media*1.5 else 0

    corpo = abs(closes[-1] - opens[-1])
    pavio = highs[-1] - max(opens[-1], closes[-1])
    rejeicao = 1 if pavio > corpo*1.5 else 0

    return {
        "trend": trend,
        "momentum": round(momentum,5),
        "vol": round(vol,5),
        "vol_spike": vol_spike,
        "rejeicao": rejeicao
    }

def key(f):
    return f"{f['trend']}_{f['vol_spike']}_{f['rejeicao']}_{int(f['momentum']*1000)}"

# =========================
# 🧠 IA + MEMÓRIA
# =========================
def aprender(f, resultado, symbol):
    k = key(f)

    if k not in AI:
        AI[k] = {"win":1,"loss":1}

    AI[k][resultado] += 1
    save_json(AI_DB, AI)

    # 📊 MEMÓRIA INSTITUCIONAL
    if k not in MEM:
        MEM[k] = {"total":0,"win":0,"loss":0,"symbol":symbol}

    MEM[k]["total"] += 1
    MEM[k][resultado] += 1

    save_json(MEM_DB, MEM)

def probabilidade(f):
    k = key(f)
    if k not in AI:
        return 0.5
    d = AI[k]
    return d["win"]/(d["win"]+d["loss"])

def qualidade_memoria(f):
    k = key(f)

    if k not in MEM or MEM[k]["total"] < 5:
        return True  # ainda aprendendo

    taxa = MEM[k]["win"] / MEM[k]["total"]

    return taxa >= 0.55  # bloqueia padrões ruins

# =========================
# DECISÃO
# =========================
def decisao(c):
    global FEATURES_ATUAL

    f = features(c)
    FEATURES_ATUAL = f

    prob = probabilidade(f)

    if not qualidade_memoria(f):
        return "HOLD", prob

    score = 2 if f["trend"] == 1 else -2

    if prob > 0.6:
        score += 2
    elif prob < 0.4:
        score -= 2

    if score >= 2:
        return
