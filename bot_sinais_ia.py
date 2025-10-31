# bot_sinais_ia.py
# BOT SINAIS IA ALFA
# Requisitos: requests
# Rodar: python3 bot_sinais_ia.py

import requests
import threading
import time
import json
import os
from collections import defaultdict

# ---------------- CONFIG ----------------
TELEGRAM_TOKEN = "8126373920:AAEdRJ48gNqflX-M3kcihod4xegf314iup0"
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
USE_REAL_API = True
API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json"
FETCH_INTERVAL = 5            # segundos entre buscas e previsões
LOOKBACK_MAX = 200
ANALYZE_WINDOW_SIZES = [3,4,5,6]
STATE_FILE = "estado_ia_alfa.json"
CODES_FILE = "access_codes.json"
# ----------------------------------------

# In-memory state
numeric_history = []   # oldest -> newest
gp_history = []        # 'G'/'P'
last_issue = None
subscribers = {}       # chat_id (str) -> {"last_sent": None, "active": True, "code": CODE, "activated_at": ts}
signals = []           # recent signals
stats = {"total":0, "correct":0, "accuracy":0.0}

# ---------- persistence ----------
def load_state():
    global subscribers, signals, stats
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            subscribers = data.get("subscribers", {})
            signals = data.get("signals", [])
            stats.update(data.get("stats", {}))
            print("[state] carregado", STATE_FILE)
        except Exception as e:
            print("[state] falha ao carregar:", e)

def save_state():
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"subscribers": subscribers, "signals": signals[-1000:], "stats": stats}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[state] falha ao salvar:", e)

# ---------- access codes ----------
def load_codes():
    if not os.path.exists(CODES_FILE):
        return []
    try:
        with open(CODES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [c.strip().upper() for c in data if isinstance(c, str) and c.strip()]
    except Exception as e:
        print("[codes] erro ao ler:", e)
        return []

def consume_code(code):
    code = code.strip().upper()
    codes = load_codes()
    if code not in codes:
        return False
    codes = [c for c in codes if c != code]
    try:
        with open(CODES_FILE, "w", encoding="utf-8") as f:
            json.dump(codes, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print("[codes] erro ao salvar:", e)
        return False

# ---------- telegram helpers ----------
def telegram_send(chat_id, text):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        r = requests.post(url, json=payload, timeout=8)
        return r.ok
    except Exception as e:
        print("[tg] send error:", e)
        return False

# ---------- data source ----------
SIMULATED = {
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
                return r.json().get("data", {}).get("list", [])
            else:
                print("[api] status", r.status_code)
                return []
        except Exception as e:
            print("[api] fetch error:", e)
            return []
    else:
        return list(SIMULATED["data"]["list"])

# ---------- adaptive predictor ----------
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
        acc = stats.get("accuracy", 0.0)
        acc_factor = max(0.6, min(1.2, 1.0 + (acc - 50)/200))
        probG *= acc_factor; probP *= acc_factor
        s2 = probG + probP
        if s2 <= 0:
            return None, 0
        probG/=s2; probP/=s2
        return ('G', int(round(probG*100))) if probG>probP else ('P', int(round(probP*100)))
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

# ---------- sending logic ----------
def send_prediction_to_chat(chat_id, prediction, confidence, next_issue):
    if not prediction:
        return False
    sub = subscribers.get(str(chat_id))
    if not sub or not sub.get("active"):
        return False
    if sub.get("last_sent") == prediction:
        return False
    text = (
        "🎯 Previsão BOT SINAIS IA ALFA\n"
        f"📅 Período: {next_issue}\n"
        f"📊 Próximo Sinal: {'🟠 Grande' if prediction=='G' else '🔵 Pequeno'}\n"
        "🤖 Inteligência: IA 2025"
    )
    ok = telegram_send(chat_id, text)
    if ok:
        subscribers[str(chat_id)]["last_sent"] = prediction
        save_state()
    return ok

# ---------- getUpdates loop (handles /start and code redemption) ----------
last_update_id = None
def telegram_updates_loop():
    global last_update_id
    print("[tg] getUpdates loop iniciado. Use /start e depois envie o código de acesso.")
    while True:
        try:
            url = f"{TELEGRAM_API}/getUpdates"
            params = {"timeout": 10}
            if last_update_id:
                params["offset"] = last_update_id + 1
            r = requests.get(url, params=params, timeout=15)
            if r.status_code != 200:
                time.sleep(1); continue
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
                    telegram_send(chat_id, "👋 Olá! Envie seu código de acesso com /redeem <CÓDIGO> (ex: /redeem IA-ALFA-001)")
                elif cmd == "/redeem":
                    if len(parts) < 2:
                        telegram_send(chat_id, "Envie: /redeem <CÓDIGO>")
                        continue
                    code = parts[1].strip().upper()
                    codes = load_codes()
                    if code not in codes:
                        telegram_send(chat_id, "❌ Código inválido ou já utilizado.")
                        continue
                    ok = consume_code(code)
                    if not ok:
                        telegram_send(chat_id, "❌ Falha interna ao consumir o código. Tente mais tarde.")
                        continue
                    subscribers[str(chat_id)] = {"last_sent": None, "active": True, "code": code, "activated_at": int(time.time())}
                    save_state()
                    telegram_send(chat_id, "✅ Código aceito! Você será incluído na lista para receber sinais automáticos.")
                    if gp_history:
                        pred, conf, next_issue = current_prediction_payload()
                        send_prediction_to_chat(chat_id, pred, conf, next_issue)
                elif cmd == "/stop":
                    if str(chat_id) in subscribers:
                        subscribers.pop(str(chat_id), None)
                        save_state()
                        telegram_send(chat_id, "🛑 Você foi desregistrado.")
                    else:
                        telegram_send(chat_id, "Você não está registrado.")
                elif cmd == "/status":
                    pred, conf, next_issue = current_prediction_payload()
                    s = f"Status:\\nPeríodo: {next_issue}\\nSinal: {'🟠 Grande' if pred=='G' else '🔵 Pequeno' if pred=='P' else '-'}\\nConfiança: {conf}%\\nAssinantes: {sum(1 for v in subscribers.values() if v.get('active'))}\\nAcertos: {stats.get('correct',0)} / {stats.get('total',0)} ({stats.get('accuracy',0)}%)"
                    telegram_send(chat_id, s)
                else:
                    pass
        except Exception as e:
            print("[tg] loop error:", e)
            time.sleep(2)

# ---------- main loop: fetch -> predict -> send ----------
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
                if len(numeric_history) > LOOKBACK_MAX:
                    numeric_history[:] = numeric_history[-LOOKBACK_MAX:]
                    gp_history[:] = gp_history[-LOOKBACK_MAX:]
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
                        total = stats.get("total",0); correct = stats.get("correct",0)
                        stats["accuracy"] = round((correct/total)*100,2) if total>0 else 0.0
                        save_state()
                pred, conf, next_issue = current_prediction_payload()
                sig = {"ts": int(time.time()), "prediction": pred, "confidence": conf, "next_issue": next_issue, "evaluated": False}
                signals.append(sig)
                for chat_id_str, info in list(subscribers.items()):
                    try:
                        if info.get("active"):
                            send_prediction_to_chat(int(chat_id_str), pred, conf, next_issue)
                    except Exception as e:
                        print("[send] error to", chat_id_str, e)
                save_state()
        except Exception as e:
            print("[main] loop error:", e)
        time.sleep(FETCH_INTERVAL)

# ---------- start ----------
if __name__ == "__main__":
    load_state()
    t1 = threading.Thread(target=telegram_updates_loop, daemon=True)
    t1.start()
    t2 = threading.Thread(target=main_loop, daemon=True)
    t2.start()
    print("BOT SINAIS IA ALFA iniciado. Aguardando usuários e enviando previsões automaticamente.")
    while True:
        time.sleep(60)
