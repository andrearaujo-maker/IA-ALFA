#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# bot_ia_popbra.py
# Bot Telegram individual com IA probabilística adaptativa (simulação por padrão)
# Requisitos: requests
# Rodar: python bot_ia_popbra.py

import requests
import threading
import time
import json
import os
from collections import defaultdict

# ---------------- CONFIG ----------------
TELEGRAM_TOKEN = "8126373920:AAEdRJ48gNqflX-M3kcihod4xegf314iup0"  # seu token
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
USE_REAL_API = True   # False = usa dados simulados; True = buscar a API real
API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json"
FETCH_INTERVAL = 5     # segundos entre checagens
LOOKBACK_MAX = 200
ANALYZE_WINDOW_SIZES = [3, 4, 5, 6]
PERSIST_FILE = "aprendizado_bot.json"
# ----------------------------------------

# Estado em memória
numeric_history = []   # lista de ints (oldest->newest)
gp_history = []        # lista de 'G'/'P'
last_issue = None
signals = []           # lista de dicts de sinais gerados (opcional)
subscribers = {}       # chat_id (int) -> {"last_sent": 'G'/'P' or None}
stats = {"total": 0, "correct": 0, "accuracy": 0.0}

# ---------------- Persistence ----------------
def load_state():
    global subscribers, signals, stats, last_issue, numeric_history, gp_history
    if os.path.exists(PERSIST_FILE):
        try:
            with open(PERSIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # load subscribers
            subs = data.get("subscribers", {})
            # normalize keys to int
            subscribers = {int(k): v for k, v in subs.items()}
            # load signals, stats
            signals[:] = data.get("signals", []) if isinstance(data.get("signals", []), list) else []
            stats.update(data.get("stats", {}))
            # last_issue and history
            last_issue_val = data.get("last_issue")
            if last_issue_val:
                last_issue = str(last_issue_val)
            numeric_history = data.get("numeric_history", []) or numeric_history
            gp_history = data.get("gp_history", []) or gp_history
            print("[state] carregado", PERSIST_FILE)
        except Exception as e:
            print("[state] falha ao carregar:", e)

def save_state():
    try:
        obj = {
            "subscribers": subscribers,
            "signals": signals[-1000:],
            "stats": stats,
            "last_issue": last_issue,
            "numeric_history": numeric_history[-LOOKBACK_MAX:],
            "gp_history": gp_history[-LOOKBACK_MAX:]
        }
        with open(PERSIST_FILE, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[state] falha ao salvar:", e)

# ---------------- Telegram helpers ----------------
def telegram_send_message(chat_id, text):
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
            {"issueNumber": "20251006100011135", "number": "4"},
            {"issueNumber": "20251006100011134", "number": "4"},
            {"issueNumber": "20251006100011133", "number": "4"},
            {"issueNumber": "20251006100011132", "number": "3"},
            {"issueNumber": "20251006100011131", "number": "5"},
            {"issueNumber": "20251006100011130", "number": "5"},
            {"issueNumber": "20251006100011129", "number": "5"},
            {"issueNumber": "20251006100011128", "number": "2"},
            {"issueNumber": "20251006100011127", "number": "9"},
            {"issueNumber": "20251006100011126", "number": "2"}
        ]
    }
}

def fetch_api_list():
    """Tenta usar API real; se falhar, retorna simulado."""
    if USE_REAL_API:
        try:
            r = requests.get(API_URL, timeout=8)
            if r.status_code == 200:
                data = r.json()
                # Accept different shapes; prefer data->list
                lst = data.get("data", {}).get("list", [])
                if lst:
                    return lst
                # fallback: try top-level list
                if isinstance(data, list) and data:
                    return data
                # empty: fallback to simulated
                print("[api] retorno vazio -> usando simulado")
                return list(SIMULATED_JSON["data"]["list"])
            else:
                print("[api] status", r.status_code, "-> usando simulado")
                return list(SIMULATED_JSON["data"]["list"])
        except Exception as e:
            print("[api] fetch error:", e, "-> usando simulado")
            return list(SIMULATED_JSON["data"]["list"])
    else:
        return list(SIMULATED_JSON["data"]["list"])

# ---------------- Adaptive predictor ----------------
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
            if seq_str[i:i + w] == pattern:
                if i + w < n:
                    nxt = seq_str[i + w]
                    weight = w * (1 + (i / max(1, n)))
                    candidates.append((nxt, weight))
    return candidates

def adaptive_predict_from_seq(seq_str):
    if not seq_str:
        return None, 0
    candidates = find_pattern_candidates_seq(seq_str)
    if candidates:
        agg = defaultdict(float)
        for val, w in candidates:
            agg[val] += w
        total = sum(agg.values())
        if total <= 0:
            return None, 0
        probG = agg.get('G', 0.0) / total
        probP = agg.get('P', 0.0) / total
        # transition evidence
        last = seq_str[-1]
        trans_counts = {'G': 0, 'P': 0}
        for i in range(len(seq_str) - 1):
            if seq_str[i] == last:
                trans_counts[seq_str[i + 1]] += 1
        trans_total = trans_counts['G'] + trans_counts['P']
        if trans_total > 0:
            tG = trans_counts['G'] / trans_total
            tP = trans_counts['P'] / trans_total
            probG = 0.7 * probG + 0.3 * tG
            probP = 0.7 * probP + 0.3 * tP
        s = probG + probP
        if s <= 0:
            return None, 0
        probG /= s
        probP /= s
        # adjust by accuracy (scale but keep normalization)
        acc = stats.get("accuracy", 0.0)
        acc_factor = max(0.6, min(1.2, 1.0 + (acc - 50) / 200))
        probG *= acc_factor
        probP *= acc_factor
        s2 = probG + probP
        if s2 <= 0:
            return None, 0
        probG /= s2
        probP /= s2
        return ('G', int(round(probG * 100))) if probG > probP else ('P', int(round(probP * 100)))
    # fallback heuristics: transitions / frequency
    g_count = seq_str.count('G')
    p_count = seq_str.count('P')
    if g_count + p_count == 0:
        return None, 0
    last = seq_str[-1]
    trans_counts = {'G': 0, 'P': 0}
    for i in range(len(seq_str) - 1):
        if seq_str[i] == last:
            trans_counts[seq_str[i + 1]] += 1
    trans_total = trans_counts['G'] + trans_counts['P']
    if trans_total > 0:
        pred = 'G' if trans_counts['G'] > trans_counts['P'] else 'P'
        conf = int(round((max(trans_counts['G'], trans_counts['P']) / trans_total) * 60))
        return pred, conf
    # frequency revert
    if g_count > p_count:
        return 'P', int(round((g_count / (g_count + p_count)) * 40))
    elif p_count > g_count:
        return 'G', int(round((p_count / (g_count + p_count)) * 40))
    else:
        return ('G' if int(time.time()) % 2 == 0 else 'P'), 20

def current_prediction_payload():
    seq = ''.join(gp_history[-LOOKBACK_MAX:]) if gp_history else ""
    pred, conf = adaptive_predict_from_seq(seq)
    next_issue = None
    if last_issue:
        try:
            next_issue = str(int(last_issue) + 1)
        except Exception:
            next_issue = (last_issue or "") + "+1"
    return pred, conf, next_issue

# ---------------- Send logic ----------------
def send_prediction_to_chat(chat_id, prediction, confidence, next_issue):
    if prediction not in ('G', 'P'):
        return False
    sub = subscribers.get(int(chat_id))
    if not sub:
        return False
    if sub.get("last_sent") == prediction:
        return False
    text = (
        "🎯 Sinal Automático\n"
        f"🔮 Próxima Entrada: {'🟠 Grande' if prediction == 'G' else '🔵 Pequeno'}\n"
        f"📅 Período: {next_issue}\n"
        f"🤖 Confiança: {confidence}%\n\n"
        "🔔 Para cancelar: /stop"
    )
    ok = telegram_send_message(chat_id, text)
    if ok:
        subscribers[int(chat_id)]["last_sent"] = prediction
        save_state()
    return ok

# ---------------- Telegram getUpdates loop (commands handling) ----------------
last_update_id = None

def telegram_updates_loop():
    global last_update_id
    print("[tg] iniciando loop de updates (use /start para se registrar)")
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
                time.sleep(1)
                continue
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
                    subscribers[int(chat_id)] = {"last_sent": None}
                    save_state()
                    telegram_send_message(chat_id, "✅ Registrado! Você receberá o último sinal automático (enviaremos apenas novos sinais).")
                    # send immediate last prediction if exists
                    if gp_history:
                        pred, conf, next_issue = current_prediction_payload()
                        send_prediction_to_chat(chat_id, pred, conf, next_issue)
                elif cmd == "/stop":
                    if int(chat_id) in subscribers:
                        subscribers.pop(int(chat_id), None)
                        save_state()
                        telegram_send_message(chat_id, "🛑 Você foi desregistrado. Envie /start para receber sinais novamente.")
                    else:
                        telegram_send_message(chat_id, "Você não está registrado.")
                elif cmd == "/status":
                    pred, conf, next_issue = current_prediction_payload()
                    s = f"Status:\nPróximo Período: {next_issue}\nPróximo Sinal: {'🟠 Grande' if pred == 'G' else '🔵 Pequeno' if pred == 'P' else '-'}\nConfiança: {conf}%\nAssinantes: {len(subscribers)}\nAcertos: {stats.get('correct', 0)} / {stats.get('total', 0)} ({stats.get('accuracy', 0)}%)"
                    telegram_send_message(chat_id, s)
                else:
                    # unknown message: ignore or treat as simple chat
                    pass
        except Exception as e:
            print("[tg] updates loop error:", e)
            time.sleep(2)

# ---------------- Main loop: fetch -> predict -> send ----------------
def update_history_from_api_and_predict():
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
                    except Exception:
                        continue
                    issue = item.get("issueNumber") or item.get("issue") or None
                    # append if new (issue changed) OR numeric_history empty
                    if not numeric_history or (issue and issue != last_issue):
                        numeric_history.append(n)
                        gp_history.append('G' if n >= 5 else 'P')
                        last_issue = issue or last_issue
                        added_new = True
                # trim history
                if len(numeric_history) > LOOKBACK_MAX:
                    del numeric_history[0: len(numeric_history) - LOOKBACK_MAX]
                    del gp_history[0: len(gp_history) - LOOKBACK_MAX]
                # evaluate last pending signal if we have new actual
                if added_new and signals:
                    last_sig = signals[-1]
                    if not last_sig.get("evaluated") and gp_history:
                        actual = gp_history[-1]
                        last_sig["actual"] = actual
                        last_sig["evaluated"] = True
                        last_sig["correct"] = (last_sig["prediction"] == actual)
                        stats["total"] = stats.get("total", 0) + 1
                        if last_sig["correct"]:
                            stats["correct"] = stats.get("correct", 0) + 1
                        total = stats.get("total", 0)
                        correct = stats.get("correct", 0)
                        stats["accuracy"] = round((correct / total) * 100, 2) if total > 0 else 0.0
                        save_state()
                # predict next (always try to predict)
                pred, conf, next_issue = current_prediction_payload()
                # prevent creating null/None signals
                if pred in ('G', 'P'):
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
    # create/ensure persistence file exists
    if not os.path.exists(PERSIST_FILE):
        save_state()
    load_state()
    # start telegram update loop
    t1 = threading.Thread(target=telegram_updates_loop, daemon=True)
    t1.start()
    # start main loop
    t2 = threading.Thread(target=update_history_from_api_and_predict, daemon=True)
    t2.start()
    print("Bot iniciado. Peça para clientes enviarem /start.")
    try:
        while True:
            time.sleep(30)
    except KeyboardInterrupt:
        print("Encerrando...")    
        if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default


def save_json_safe(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except:
        pass


def telegram_send(chat_id, text):
    try:
        url = f"{TELEGRAM_API}/sendMessage"
        r = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
        return r.ok
    except:
        return False


# ============================================================
# AI — preditor simples
# ============================================================

def predict_next():
    """
    G: Grande  (>=5)
    P: Pequeno (<5)
    """
    seq = gp_history[-20:]
    if not seq:
        return None, 0

    g = seq.count("G")
    p = seq.count("P")

    if g > p:
        return "P", 60
    elif p > g:
        return "G", 60
    else:
        return ("G" if int(time.time()) % 2 == 0 else "P"), 55


# ============================================================
# FETCH POPBRA
# ============================================================

def fetch_popbra():
    try:
        r = requests.get(API_URL, timeout=10)
        if r.status_code != 200:
            return []
        return r.json().get("data", {}).get("list", [])
    except:
        return []


# ============================================================
# PREDIÇÃO E ENVIO
# ============================================================

def process_data():
    global last_issue

    lst = fetch_popbra()
    if not lst:
        return

    newest = lst[0]

    issue = newest.get("issueNumber")
    num = newest.get("number")

    if not issue or not num:
        return

    try:
        n = int(num)
    except:
        return

    if issue == last_issue:
        return

    last_issue = issue

    gp = "G" if n >= 5 else "P"
    numeric_history.append(n)
    gp_history.append(gp)

    if len(numeric_history) > LOOKBACK_MAX:
        numeric_history.pop(0)
    if len(gp_history) > LOOKBACK_MAX:
        gp_history.pop(0)

    pred, conf = predict_next()

    next_issue = str(int(issue) + 1)

    signals.append({
        "ts": int(time.time()),
        "prediction": pred,
        "confidence": conf,
        "issue": issue,
        "next": next_issue
    })

    state = load_json_safe(STATE_FILE, {"active_user": None})
    chat_id = state.get("active_user")

    if chat_id:
        send_signal(chat_id, pred, conf, next_issue)


def send_signal(chat_id, pred, conf, next_issue):
    txt = (
        "🎯 *Sinal Automático*\n"
        f"🔮 Próxima Entrada: {'🟠 Grande' if pred=='G' else '🔵 Pequeno'}\n"
        f"📅 Período: {next_issue}\n"
        f"🤖 Confiança: {conf}%\n\n"
        "Para parar de receber: /stop"
    )
    telegram_send(chat_id, txt)


# ============================================================
# LOOP PRINCIPAL
# ============================================================

def periodic_sender_loop():
    while True:
        try:
            process_data()
        except Exception as e:
            print("[ERR]", e)
        time.sleep(FETCH_INTERVAL)


# ============================================================
# TELEGRAM
# ============================================================

def telegram_polling_loop():
    last_update = None
    while True:
        try:
            url = f"{TELEGRAM_API}/getUpdates"
            params = {"timeout": 10}
            if last_update:
                params["offset"] = last_update + 1

            r = requests.get(url, params=params, timeout=25)
            if r.status_code != 200:
                continue

            data = r.json()
            if not data.get("ok"):
                continue

            for item in data.get("result", []):
                last_update = item["update_id"]

                msg = item.get("message")
                if not msg:
                    continue

                chat_id = msg["chat"]["id"]
                text = msg.get("text", "").strip()

                if text == "/start":
                    handle_start(chat_id)

                elif text == "/stop":
                    handle_stop(chat_id)

        except Exception:
            time.sleep(2)


def handle_start(chat_id):
    telegram_send(chat_id, "🔐 Envie seu código de acesso:")

    listener = True
    while listener:
        try:
            url = f"{TELEGRAM_API}/getUpdates"
            r = requests.get(url, timeout=10).json()
            for item in r.get("result", []):
                upd_id = item["update_id"]
                msg = item.get("message")
                if not msg:
                    continue
                sender = msg["chat"]["id"]
                txt = msg.get("text", "").strip()

                if sender == chat_id and txt != "/start":
                    validate_code(chat_id, txt)
                    listener = False
                    break
        except:
            pass
        time.sleep(1)


def validate_code(chat_id, code):
    codes = load_json_safe(CODES_FILE, {"codes": []})

    if code not in codes.get("codes", []):
        telegram_send(chat_id, "❌ Código inválido.")
        return

    codes["codes"].remove(code)
    save_json_safe(CODES_FILE, codes)

    state = {"active_user": chat_id}
    save_json_safe(STATE_FILE, state)

    telegram_send(chat_id, "✅ Código aceito! Você receberá sinais automáticos.")


def handle_stop(chat_id):
    st = load_json_safe(STATE_FILE, {"active_user": None})
    if st.get("active_user") == chat_id:
        st["active_user"] = None
        save_json_safe(STATE_FILE, st)
        telegram_send(chat_id, "🛑 Você parou de receber sinais.")
    else:
        telegram_send(chat_id, "⚠️ Você não estava ativo.")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("Iniciando bot...")

    # cria arquivos se não existirem
    if not os.path.exists(CODES_FILE):
        save_json_safe(CODES_FILE, {"codes": ["COD123"]})

    if not os.path.exists(STATE_FILE):
        save_json_safe(STATE_FILE, {"active_user": None})

    # inicia threads
    t1 = threading.Thread(target=telegram_polling_loop, daemon=True)
    t1.start()

    t2 = threading.Thread(target=periodic_sender_loop, daemon=True)
    t2.start()

    print("Bot rodando. Use /start no Telegram.")

    while True:
        time.sleep(60)
