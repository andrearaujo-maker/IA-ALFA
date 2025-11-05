#!/usr/bin/env python3
# bot_ia_popbra.py
# Envia sinais automáticos para o ÚLTIMO usuário que ativou o código (uso único).
# Dependências:
#   pip install python-telegram-bot==20.3 requests

import json
import time
import requests
import threading
import os
import random
from typing import Optional

# ---------------- CONFIG ----------------
TELEGRAM_TOKEN = "8126373920:AAEdRJ48gNqflX-M3kcihod4xegf314iup0"  # <<-- coloque seu token aqui
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json"
USE_REAL_API = True        # se quiser apenas simular, troque para False
FETCH_INTERVAL = 30        # segundos entre envios (você pediu 30s)
# ----------------------------------------

CODES_FILE = "codes.json"
STATE_FILE = "state.json"

# ---------------- Helpers de arquivo ----------------
def load_json_safe(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json_safe(path, obj):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[file] erro ao salvar", path, e)

# ---------------- Inicializa arquivos se faltarem ----------------
if not os.path.exists(CODES_FILE):
    save_json_safe(CODES_FILE, {})    # você deve colar codes.json manualmente se quiser códigos
if not os.path.exists(STATE_FILE):
    save_json_safe(STATE_FILE, {"active_user": None, "last_sent_prediction": None, "stats": {"total":0,"correct":0,"accuracy":0.0}})

# ---------------- Carrega estado e códigos ----------------
codes_map = load_json_safe(CODES_FILE, {})
state = load_json_safe(STATE_FILE, {"active_user": None, "last_sent_prediction": None, "stats": {"total":0,"correct":0,"accuracy":0.0}})

# normalize codes_map shape: support both { "CODE": {"used":false} } and { "CODES": {...} }
if "CODES" in codes_map and isinstance(codes_map["CODES"], dict):
    codes_map = {k: v for k, v in codes_map["CODES"].items()}
# if values are like {"used": false}, keep same; else if plain bool, convert to dict
for k,v in list(codes_map.items()):
    if isinstance(v, bool):
        codes_map[k] = {"used": not v}  # if earlier we used true=available, normalize to {"used":false}
    elif isinstance(v, dict) and "used" in v:
        pass
    else:
        # unknown, mark used False by default
        codes_map[k] = {"used": False}

# ---------------- Utilitários Telegram ----------------
def tg_send(chat_id: int, text: str) -> bool:
    try:
        r = requests.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": text})
        return r.ok
    except Exception as e:
        print("[tg] send error:", e)
        return False

# ---------------- API (com fallback simulada) ----------------
SIMULATED = {
  "data": {
    "list": [
      {"issueNumber":"20251020100050196","number":"3"},
      {"issueNumber":"20251020100050195","number":"6"},
      {"issueNumber":"20251020100050194","number":"2"}
    ]
  }
}

def fetch_api():
    if not USE_REAL_API:
        return list(SIMULATED["data"]["list"])
    try:
        r = requests.get(API_URL, timeout=6)
        if r.status_code == 200:
            lst = r.json().get("data", {}).get("list", [])
            if lst:
                return lst
            else:
                print("[api] retorno vazio — usando simulado")
                return list(SIMULATED["data"]["list"])
        else:
            print("[api] status", r.status_code, "— usando simulado")
            return list(SIMULATED["data"]["list"])
    except Exception as e:
        print("[api] erro:", e, "— usando simulado")
        return list(SIMULATED["data"]["list"])

def interpret_number_to_entry(n):
    try:
        n = int(n)
    except:
        return "Pequeno 🔵"
    return "Grande 🟠" if n >= 5 else "Pequeno 🔵"

# ---------------- Lógica de previsão (simples/adaptativa) ----------------
def make_prediction_from_history(lst):
    # lst is newest-first usually; use first element
    if not lst:
        return None, 0, "?"
    # we'll predict same rule: number >=5 -> G else P, but you can replace with IA later
    last = lst[0]
    num = int(last.get("number", 0))
    # simple heuristic: flip (example). You can use full adaptive model here.
    pred_entry = interpret_number_to_entry(num)
    # confidence randomish for presentation
    conf = random_confidence = random.randint(60, 95)
    next_period = last.get("issueNumber") or last.get("issue") or "unknown"
    # represent prediction internally as 'G'/'P'
    pred_gp = 'G' if num >= 5 else 'P'
    return pred_gp, conf, str(next_period)

# ---------------- Envio de sinal ao usuário ATIVO (apenas o último) ----------------
def send_signal_to_active():
    # load fresh state to be safe with file changes
    st = load_json_safe(STATE_FILE, {"active_user": None})
    active = st.get("active_user")
    if not active:
        return False
    lst = fetch_api()
    pred_gp, conf, next_period = make_prediction_from_history(lst)
    if pred_gp is None:
        return False
    # message formatted
    msg = (
        "🎯 SINAL AUTOMÁTICO\n"
        f"🔮 Próxima Entrada: {'🟠 Grande' if pred_gp=='G' else '🔵 Pequeno'}\n"
        f"📅 Período: {next_period}\n"
        f"🤖 Confiança: {conf}%\n\n"
        "🔔 Para cancelar: /stop"
    )
    ok = tg_send(active, msg)
    if ok:
        # store last_sent_prediction
        st["last_sent_prediction"] = {"pred": pred_gp, "conf": conf, "period": next_period, "ts": int(time.time())}
        save_json_safe(STATE_FILE, st)
    return ok

# ---------------- Telegram polling loop (getUpdates) ----------------
last_update_id = None

def telegram_polling_loop():
    global last_update_id, codes_map
    print("[tg] iniciar polling getUpdates")
    while True:
        try:
            params = {"timeout": 10}
            if last_update_id:
                params["offset"] = last_update_id + 1
            r = requests.get(f"{TELEGRAM_API}/getUpdates", params=params, timeout=15)
            if r.status_code != 200:
                time.sleep(1)
                continue
            data = r.json()
            if not data.get("ok"):
                time.sleep(1); continue
            for item in data.get("result", []):
                last_update_id = item["update_id"]
                msg = item.get("message") or item.get("edited_message")
                if not msg:
                    continue
                chat_id = msg["chat"]["id"]
                text = (msg.get("text") or "").strip()
                if not text:
                    continue
                # commands
                if text.lower().startswith("/start"):
                    tg_send(chat_id, "🤖 Olá! Cole seu *CÓDIGO DE ACESSO* (ex.: ALFA-903S).")
                    continue
                if text.lower().startswith("/stop"):
                    # remove active if matches
                    st = load_json_safe(STATE_FILE, {"active_user": None})
                    if st.get("active_user") == chat_id:
                        st["active_user"] = None
                        save_json_safe(STATE_FILE, st)
                        tg_send(chat_id, "🛑 Você foi desativado. Para voltar envie /start e cole um código.")
                    else:
                        tg_send(chat_id, "Você não está recebendo sinais automáticos.")
                    continue
                if text.lower().startswith("/status"):
                    st = load_json_safe(STATE_FILE, {"active_user": None, "last_sent_prediction": None, "stats": {}})
                    active = st.get("active_user")
                    last_sent = st.get("last_sent_prediction")
                    s = f"Status:\nUsuário ativo: {active}\nÚltimo sinal: {last_sent}\nEstatísticas: {st.get('stats',{})}"
                    tg_send(chat_id, s)
                    continue
                # if not command, treat as code attempt if user not active
                st = load_json_safe(STATE_FILE, {"active_user": None})
                if st.get("active_user") != chat_id:
                    code_try = text.upper()
                    # refresh codes_map from disk
                    codes_map = load_json_safe(CODES_FILE, {})
                    # normalize shapes
                    if "codes" in codes_map:
                        codes_map = codes_map["codes"]
                    # codes_map expected shape: CODE -> {"used": false}
                    if code_try in codes_map and isinstance(codes_map[code_try], dict) and not codes_map[code_try].get("used", False):
                        # mark used True and set active_user = chat_id
                        codes_map[code_try]["used"] = True
                        save_json_safe(CODES_FILE, {"codes": codes_map})
                        st["active_user"] = chat_id
                        save_json_safe(STATE_FILE, st)
                        tg_send(chat_id, "✅ Código aceito! Você é o usuário ativo e vai receber sinais automáticos (a cada 30s).")
                        # send immediate signal
                        send_signal_to_active()
                    else:
                        tg_send(chat_id, "❌ Código inválido ou já utilizado.")
                else:
                    tg_send(chat_id, "Você já é o usuário ativo. Use /stop para parar.")
        except Exception as e:
            print("[tg] erro polling:", e)
            time.sleep(2)

# ---------------- Main loop que envia sinais a cada período (30s) ----------------
def periodic_sender_loop():
    print("[sender] loop iniciado: envia sinal a cada", FETCH_INTERVAL, "s ao usuário ativo (último).")
    while True:
        try:
            send_signal_to_active()
        except Exception as e:
            print("[sender] erro ao enviar sinal:", e)
        time.sleep(FETCH_INTERVAL)

# ---------------- Start ----------------
if __name__ == "__main__":
    print("Iniciando bot_ia_popbra...")
    # ensure files exist
    if not os.path.exists(CODES_FILE):
        save_json_safe(CODES_FILE, {"codes": codes_map})
    if not os.path.exists(STATE_FILE):
        save_json_safe(STATE_FILE, state)
    # load fresh
    codes_map = load_json_safe(CODES_FILE, {})
    state = load_json_safe(STATE_FILE, {"active_user": None})
    # start polling and sender in threads
    t1 = threading.Thread(target=telegram_polling_loop, daemon=True)
    t1.start()
    t2 = threading.Thread(target=periodic_sender_loop, daemon=True)
    t2.start()
    print("Bot rodando. Use /start no Telegram para começar.")
    while True:
        time.sleep(60)signals = []       # histórico de sinais gerados
stats = {"total":0, "correct":0, "accuracy":0.0}

# codes map (code -> bool available)
codes_map = {}

# ---------------- Persistence ----------------
def ensure_files_exist():
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"subscribers": {},"signals": [], "stats": stats}, f)
    if not os.path.exists(CODES_FILE):
        with open(CODES_FILE, "w", encoding="utf-8") as f:
            # default empty structure
            json.dump({"codes": {}}, f)

def load_state():
    global subscribers, signals, stats
    ensure_files_exist()
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        subs = data.get("subscribers", {})
        # normalize keys to int
        subscribers = {int(k): v for k,v in subs.items()}
        signals[:] = data.get("signals", [])
        stats.update(data.get("stats", {}))
        print("[state] carregado")
    except Exception as e:
        print("[state] falha ao carregar:", e)

def save_state():
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            obj = {"subscribers": subscribers, "signals": signals[-2000:], "stats": stats}
            json.dump(obj, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[state] falha ao salvar:", e)

def load_codes():
    global codes_map
    ensure_files_exist()
    try:
        with open(CODES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # accept several shapes: {"codes": {...}} or {"CODES": {...}} or raw dict
        if isinstance(data, dict):
            if "codes" in data and isinstance(data["codes"], dict):
                codes_map = {k.upper(): bool(v) for k,v in data["codes"].items()}
            elif "CODES" in data and isinstance(data["CODES"], dict):
                codes_map = {k.upper(): bool(v) for k,v in data["CODES"].items()}
            else:
                # maybe it's already a flat map
                codes_map = {k.upper(): bool(v) for k,v in data.items()}
        else:
            codes_map = {}
        print("[codes] carregados:", len(codes_map))
    except Exception as e:
        print("[codes] falha ao carregar:", e)
        codes_map = {}

def save_codes():
    try:
        with open(CODES_FILE, "w", encoding="utf-8") as f:
            # write in standard shape {"codes": {...}}
            data = {"codes": {k: v for k,v in codes_map.items()}}
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[codes] falha ao salvar:", e)

# ---------------- Telegram helpers ----------------
def tg_send_message(chat_id, text):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        r = requests.post(url, json=payload, timeout=8)
        return r.ok
    except Exception as e:
        print("[tg] send error:", e)
        return False

# ---------------- Data source ----------------
SIMULATED_JSON = {
  "data": {
    "list": [
      {"issueNumber":"20251006100011135","number":"4"},
      {"issueNumber":"20251006100011134","number":"4"},
      {"issueNumber":"20251006100011133","number":"4"},
      {"issueNumber":"20251006100011132","number":"3"},
      {"issueNumber":"20251006100011131","number":"5"},
      {"issueNumber":"20251006100011130","number":"5"},
      {"issueNumber":"20251006100011129","number":"5"},
      {"issueNumber":"20251006100011128","number":"2"},
      {"issueNumber":"20251006100011127","number":"9"},
      {"issueNumber":"20251006100011126","number":"2"}
    ]
  }
}

def fetch_api_list():
    if USE_REAL_API:
        try:
            r = requests.get(API_URL, timeout=8)
            if r.status_code == 200:
                data = r.json().get("data", {}).get("list", [])
                if data:
                    return data
                else:
                    print("[api] vazio → usando simulado")
                    return list(SIMULATED_JSON["data"]["list"])
            else:
                print("[api] status", r.status_code, "→ usando simulado")
                return list(SIMULATED_JSON["data"]["list"])
        except Exception as e:
            print("[api] fetch error:", e, "→ simulando")
            return list(SIMULATED_JSON["data"]["list"])
    else:
        return list(SIMULATED_JSON["data"]["list"])

# ---------------- Predictor ----------------
def find_pattern_candidates_seq(seq_str):
    candidates = []
    n = len(seq_str)
    if n < 2:
        return candidates
    for w in ANALYZE_WINDOW_SIZES:
        if n <= w:
            continue
        pattern = seq_str[-w:]
        for i in range(0, n - w):
            if seq_str[i:i+w] == pattern:
                if i + w < n:
                    nxt = seq_str[i+w]
                    weight = w * (1 + (i / max(1, n)))
                    candidates.append((nxt, weight))
    return candidates

def adaptive_predict_from_seq(seq_str):
    if not seq_str:
        return None, 0
    candidates = find_pattern_candidates_seq(seq_str)
    if candidates:
        agg = defaultdict(float)
        for val,w in candidates:
            agg[val] += w
        total = sum(agg.values())
        if total <= 0:
            return None, 0
        probG = agg.get('G',0.0)/total
        probP = agg.get('P',0.0)/total
        # transition evidence
        last = seq_str[-1]
        trans_counts = {'G':0,'P':0}
        for i in range(len(seq_str)-1):
            if seq_str[i] == last:
                trans_counts[seq_str[i+1]] += 1
        trans_total = trans_counts['G'] + trans_counts['P']
        if trans_total > 0:
            tG = trans_counts['G']/trans_total
            tP = trans_counts['P']/trans_total
            probG = 0.7*probG + 0.3*tG
            probP = 0.7*probP + 0.3*tP
        s = probG + probP
        if s <= 0:
            return None, 0
        probG/=s; probP/=s
        # adjust by accuracy
        acc = stats.get("accuracy", 0.0)
        acc_factor = max(0.6, min(1.2, 1.0 + (acc - 50)/200))
        probG *= acc_factor; probP *= acc_factor
        s2 = probG + probP
        if s2 <= 0:
            return None, 0
        probG/=s2; probP/=s2
        return ('G', int(round(probG*100))) if probG>probP else ('P', int(round(probP*100)))
    # fallback heuristics
    g_count = seq_str.count('G'); p_count = seq_str.count('P')
    if g_count + p_count == 0:
        return None, 0
    last = seq_str[-1]
    trans_counts = {'G':0,'P':0}
    for i in range(len(seq_str)-1):
        if seq_str[i] == last:
            trans_counts[seq_str[i+1]] += 1
    trans_total = trans_counts['G'] + trans_counts['P']
    if trans_total > 0:
        pred = 'G' if trans_counts['G'] > trans_counts['P'] else 'P'
        conf = int(round((max(trans_counts['G'], trans_counts['P'])/trans_total)*60))
        return pred, conf
    if g_count > p_count:
        return 'P', int(round((g_count/(g_count+p_count))*40))
    elif p_count > g_count:
        return 'G', int(round((p_count/(g_count+p_count))*40))
    else:
        return ('G' if int(time.time())%2==0 else 'P'), 20

def current_prediction_payload():
    seq = ''.join(gp_history[-LOOKBACK_MAX:]) if gp_history else ""
    pred, conf = adaptive_predict_from_seq(seq)
    next_issue = None
    if last_issue:
        try:
            next_issue = str(int(last_issue) + 1)
        except:
            next_issue = (last_issue or "") + "+1"
    return pred, conf, next_issue

# ---------------- Send logic ----------------
def send_prediction_to_chat(chat_id, prediction, confidence, next_issue):
    if prediction not in ('G','P'):
        return False
    sub = subscribers.get(int(chat_id))
    if not sub:
        return False
    if sub.get("last_sent") == prediction:
        return False
    text = (
        "🎯 Sinal Automático\n"
        f"🔮 Próxima Entrada: {'🟠 Grande' if prediction=='G' else '🔵 Pequeno'}\n"
        f"📅 Período: {next_issue}\n"
        f"🤖 Confiança: {confidence}%\n\n"
        "🔔 Para cancelar: /stop"
    )
    ok = tg_send_message(chat_id, text)
    if ok:
        subscribers[int(chat_id)]["last_sent"] = prediction
        save_state()
    return ok

# ---------------- Telegram getUpdates loop (commands handling) ----------------
last_update_id = None
def telegram_updates_loop():
    global last_update_id
    print("[tg] iniciando loop de updates (envie /start, depois cole o CÓDIGO)")
    while True:
        try:
            url = f"{TELEGRAM_API}/getUpdates"
            params = {"timeout": 10}
            if last_update_id:
                params["offset"] = last_update_id + 1
            r = requests.get(url, params=params, timeout=15)
            if r.status_code != 200:
                time.sleep(1)
                continue
            data = r.json()
            if not data.get("ok"):
                time.sleep(1); continue
            for item in data.get("result", []):
                last_update_id = item["update_id"]
                msg = item.get("message") or item.get("edited_message")
                if not msg:
                    continue
                chat_id = msg["chat"]["id"]
                text = (msg.get("text") or "").strip()
                if not text:
                    continue
                parts = text.split()
                cmd = parts[0].lower()
                if cmd == "/start":
                    tg_send_message(chat_id,
                        "Bem-vindo! Envie seu CÓDIGO DE ACESSO (cole o código):\nEx: ALFA-9O3S")
                elif cmd == "/stop":
                    if int(chat_id) in subscribers:
                        subscribers.pop(int(chat_id), None)
                        save_state()
                        tg_send_message(chat_id, "🛑 Você foi desregistrado. Para voltar, envie /start e cole seu código.")
                    else:
                        tg_send_message(chat_id, "Você não está registrado.")
                elif cmd == "/status":
                    pred, conf, next_issue = current_prediction_payload()
                    s = f"Status:\nPeríodo: {next_issue}\nSinal: {'🟠 Grande' if pred=='G' else '🔵 Pequeno' if pred=='P' else '-'}\nConfiança: {conf}%\nAssinantes: {sum(1 for v in subscribers.values() if v.get('last_sent') is not None)}\nAcertos: {stats.get('correct',0)} / {stats.get('total',0)} ({stats.get('accuracy',0)}%)"
                    tg_send_message(chat_id, s)
                else:
                    # If user is not registered yet, treat the text as a code attempt
                    if int(chat_id) not in subscribers:
                        code_try = text.strip().upper()
                        # check code exists and available
                        if code_try in codes_map and codes_map[code_try]:
                            # mark as used (False)
                            codes_map[code_try] = False
                            # register subscriber
                            subscribers[int(chat_id)] = {"last_sent": None}
                            save_codes()
                            save_state()
                            tg_send_message(chat_id, "✅ Código aceito! Você está ativo e receberá sinais automáticos.")
                            # send current prediction immediately
                            if gp_history:
                                pred, conf, next_issue = current_prediction_payload()
                                send_prediction_to_chat(chat_id, pred, conf, next_issue)
                        else:
                            tg_send_message(chat_id, "❌ Código inválido ou já utilizado.")
                    else:
                        # registered user sent a normal message - ignore or provide help
                        tg_send_message(chat_id, "Comando não reconhecido. Use /stop para cancelar ou /status.")
        except Exception as e:
            # don't spam logs, show brief
            print("[tg] updates loop error:", e)
            time.sleep(2)

# ---------------- Main loop: fetch -> predict -> send ----------------
def main_loop():
    global last_issue
    while True:
        try:
            lst = fetch_api_list()
            if lst:
                take = min(len(lst), LOOKBACK_MAX)
                items = list(reversed(lst[:take]))  # oldest->newest
                added_new = False
                for item in items:
                    try:
                        n = int(item.get("number", item.get("num", 0)))
                    except:
                        continue
                    issue = item.get("issueNumber") or item.get("issue") or None
                    if not numeric_history or (issue and issue != last_issue):
                        numeric_history.append(n)
                        gp_history.append('G' if n >= 5 else 'P')
                        last_issue = issue or last_issue
                        added_new = True
                # trim history
                if len(numeric_history) > LOOKBACK_MAX:
                    del numeric_history[0: len(numeric_history)-LOOKBACK_MAX]
                    del gp_history[0: len(gp_history)-LOOKBACK_MAX]
                # evaluate last pending signal if we have new actual
                if added_new and signals:
                    last_sig = signals[-1]
                    if not last_sig.get("evaluated") and gp_history:
                        actual = gp_history[-1]
                        last_sig["actual"] = actual
                        last_sig["evaluated"] = True
                        last_sig["correct"] = (last_sig["prediction"] == actual)
                        stats["total"] = stats.get("total",0) + 1
                        if last_sig["correct"]:
                            stats["correct"] = stats.get("correct",0) + 1
                        total = stats.get("total",0)
                        correct = stats.get("correct",0)
                        stats["accuracy"] = round((correct/total)*100,2) if total>0 else 0.0
                        save_state()
                # predict next (always try to predict)
                pred, conf, next_issue = current_prediction_payload()
                # store signal
                sig = {"ts": int(time.time()), "prediction": pred, "confidence": conf, "next_issue": next_issue, "evaluated": False}
                signals.append(sig)
                # send to subscribers automatically (only if different from last_sent)
                for chat_id_int, info in list(subscribers.items()):
                    try:
                        send_prediction_to_chat(chat_id_int, pred, conf, next_issue)
                    except Exception as e:
                        print("[send] error to", chat_id_int, e)
                save_state()
        except Exception as e:
            print("[main] loop error:", e)
        time.sleep(FETCH_INTERVAL)

# --------------- Start ----------------
if __name__ == "__main__":
    print("Inicializando bot...")
    ensure_files_exist()
    load_codes()
    load_state()
    # start telegram update loop
    t1 = threading.Thread(target=telegram_updates_loop, daemon=True)
    t1.start()
    # start main loop
    t2 = threading.Thread(target=main_loop, daemon=True)
    t2.start()
    print("Bot iniciado. Peça para clientes enviarem /start e depois COLAREM o código.")
    while True:
        time.sleep(30)
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
