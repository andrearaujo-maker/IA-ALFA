#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import threading
import time
import json
import os
from collections import defaultdict

########################################################
# CONFIG
########################################################
TELEGRAM_TOKEN = "8126373920:AAEdRJ48gNqflX-M3kcihod4xegf314iup0"
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

USE_REAL_API = True
API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json"

FETCH_INTERVAL = 5
LOOKBACK_MAX = 200
ANALYZE_WINDOW_SIZES = [3,4,5,6]

STATE_FILE = "state.json"
CODES_FILE = "codes.json"


########################################################
# ESTADOS EM MEMÓRIA
########################################################
numeric_history = []
gp_history = []
last_issue = None

subscribers = {}        # chat_id → {last_sent:"G"/"P"}
signals = []            # registros
stats = {"total":0, "correct":0, "accuracy":0.0}

access_codes = {}       # código → True/False


########################################################
# PERSISTÊNCIA
########################################################
def load_state():
    global subscribers, signals, stats, access_codes
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE,"r",encoding="utf-8") as f:
                data = json.load(f)
                subscribers.update({int(k):v for k,v in data.get("subscribers",{}).items()})
                signals.extend(data.get("signals",[]))
                stats.update(data.get("stats",{}))
            print("[state] OK")
        except:
            print("[state] falhou")

    if os.path.exists(CODES_FILE):
        try:
            with open(CODES_FILE,"r",encoding="utf-8") as f:
                data = json.load(f)
                access_codes.update(data.get("CODES",{}))
            print("[codes] OK")
        except:
            print("[codes] falhou")


def save_state():
    try:
        with open(STATE_FILE,"w",encoding="utf-8") as f:
            obj = {
                "subscribers": subscribers,
                "signals": signals[-2000:],
                "stats": stats
            }
            json.dump(obj,f,ensure_ascii=False,indent=2)
    except:
        pass

    try:
        with open(CODES_FILE,"w",encoding="utf-8") as f:
            obj={"CODES":access_codes}
            json.dump(obj,f,ensure_ascii=False,indent=2)
    except:
        pass


########################################################
# TELEGRAM
########################################################
def tg_send(chat_id,text):
    try:
        r = requests.post(f"{TELEGRAM_API}/sendMessage",json={"chat_id":chat_id,"text":text})
        return r.ok
    except:
        return False


last_update_id = None
def telegram_updates_loop():
    global last_update_id
    print("[tg] listening...")

    while True:
        try:
            params={"timeout":10}
            if last_update_id:
                params["offset"] = last_update_id+1

            r = requests.get(f"{TELEGRAM_API}/getUpdates",params=params,timeout=15)
            if r.status_code!=200:
                time.sleep(2)
                continue

            data=r.json()
            if not data.get("ok"):
                continue

            for up in data.get("result",[]):
                last_update_id = up["update_id"]

                msg = up.get("message") or up.get("edited_message")
                if not msg:
                    continue

                chat_id = msg["chat"]["id"]
                text = msg.get("text","").strip()

                # /start
                if text.startswith("/start"):
                    tg_send(chat_id,"🤖 Envie seu CÓDIGO DE ACESSO:")
                    continue

                # Se não é /start → precisa validar código
                if chat_id not in subscribers:
                    # se for /status sem acesso
                    if text.startswith("/status"):
                        tg_send(chat_id,"❌ Você não tem acesso.\nEnvie seu código primeiro.")
                        continue

                    code = text
                    if code in access_codes and access_codes[code]:
                        access_codes[code] = true
                        subscribers[chat_id] = {"last_sent":None}
                        save_state()
                        tg_send(chat_id,"✅ Código aceito! Você está ativo e receberá sinais automáticos.")
                        # envia último
                        pred,conf,nxt = current_prediction_payload()
                        send_pred_to_chat(chat_id,pred,conf,nxt)
                    else:
                        tg_send(chat_id,"❌ Código inválido ou já utilizado.")
                    continue

                # /stop
                if text.startswith("/stop"):
                    subscribers.pop(chat_id,None)
                    save_state()
                    tg_send(chat_id,"🛑 Parou. Use /start para voltar.")
                    continue

                # /status
                if text.startswith("/status"):
                    pred,conf,nxt = current_prediction_payload()
                    st = "📍 Status\n"
                    st+=f"Próximo período: {nxt}\n"
                    st+=f"Próximo sinal: {pred}\n"
                    st+=f"Confiança: {conf}%\n"
                    st+=f"Assinantes: {len(subscribers)}\n"
                    st+=f"Acertos: {stats['correct']} / {stats['total']} ({stats['accuracy']}%)"
                    tg_send(chat_id,st)
        except:
            time.sleep(2)


########################################################
# SINAL
########################################################
def send_pred_to_chat(chat_id,pred,conf,next_issue):
    if pred not in ("G","P"):
        return

    last = subscribers.get(chat_id,{}).get("last_sent")
    if last == pred:
        return

    text = (
        "🎯 *SINAL AUTOMÁTICO*\n\n"
        f"📌 Período: {next_issue}\n"
        f"✅ Entrada: {'🟠 Grande' if pred=='G' else '🔵 Pequeno'}\n"
        f"🤖 Confiança: {conf}%\n\n"
        "🛑 /stop para cancelar"
    )
    ok = tg_send(chat_id,text)
    if ok:
        subscribers[chat_id]["last_sent"] = pred
        save_state()


########################################################
# API
########################################################
def fetch_api():
    if not USE_REAL_API:
        return []

    try:
        r = requests.get(API_URL,timeout=8)
        if r.status_code==200:
            return r.json().get("data",{}).get("list",[])
    except:
        pass
    return []


########################################################
# IA – Probabilístico Adaptativo
########################################################
def adaptive_predict(seq):
    if not seq:
        return None,0

    # frequência
    Gc = seq.count("G")
    Pc = seq.count("P")
    total = Gc+Pc

    if total==0:
        return None,0

    pG = Gc/total
    pP = Pc/total

    # transição
    last = seq[-1]
    tG=tP=0
    for i in range(len(seq)-1):
        if seq[i]==last:
            if seq[i+1]=="G": tG+=1
            else: tP+=1

    t_sum = tG+tP
    if t_sum>0:
        w = 0.35
        pG = pG*(1-w) + (tG/t_sum)*w
        pP = pP*(1-w) + (tP/t_sum)*w

    # normaliza
    s = pG+pP
    pG/=s; pP/=s

    # accuracy
    acc = stats.get("accuracy",50)/100
    pG *= acc
    pP *= acc
    s = pG+pP
    pG/=s; pP/=s

    pred = "G" if pG>pP else "P"
    conf = int(max(pG,pP)*100)
    return pred,conf


def current_prediction_payload():
    seq = "".join(gp_history[-LOOKBACK_MAX:])
    pred,conf = adaptive_predict(seq)

    nxt = None
    if last_issue:
        try:
            nxt = str(int(last_issue)+1)
        except:
            nxt = last_issue+"+1"
    return pred,conf,nxt


########################################################
# MAIN WORKER
########################################################
def worker():
    global last_issue

    while True:
        try:
            lst = fetch_api()
            if lst:
                items = list(reversed(lst[:LOOKBACK_MAX]))
                new_data=False

                for item in items:
                    issue = item.get("issueNumber")
                    try:
                        n = int(item.get("number",0))
                    except:
                        continue

                    if issue != last_issue:
                        numeric_history.append(n)
                        gp_history.append("G" if n>=5 else "P")
                        last_issue = issue
                        new_data=True

                if len(numeric_history)>LOOKBACK_MAX:
                    numeric_history[:] = numeric_history[-LOOKBACK_MAX:]
                    gp_history[:] = gp_history[-LOOKBACK_MAX:]

                if new_data:
                    # avalia último sinal pendente
                    if signals:
                        last_sig = signals[-1]
                        if not last_sig["evaluated"]:
                            real = gp_history[-1]
                            last_sig["actual"]=real
                            last_sig["evaluated"]=True
                            last_sig["correct"]= (last_sig["prediction"]==real)
                            stats["total"]+=1
                            if last_sig["correct"]: stats["correct"]+=1
                            stats["accuracy"] = round((stats["correct"]/stats["total"])*100,2)

                    pred,conf,nxt = current_prediction_payload()
                    sig={"prediction":pred,"confidence":conf,"next_issue":nxt,"actual":None,"evaluated":False}
                    signals.append(sig)

                    for cid in list(subscribers.keys()):
                        send_pred_to_chat(cid,pred,conf,nxt)

                    save_state()
        except:
            pass

        time.sleep(FETCH_INTERVAL)


########################################################
# START
########################################################
def start():
    load_state()

    t1 = threading.Thread(target=telegram_updates_loop,daemon=True)
    t1.start()

    t2 = threading.Thread(target=worker,daemon=True)
    t2.start()

    print("BOT iniciado!")

    while True:
        time.sleep(30)


if __name__ == "__main__":
    start()
