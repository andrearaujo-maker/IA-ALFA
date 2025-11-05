import requests
import time
import threading
import json
import os

# ============================================================
# CONFIG
# ============================================================

TELEGRAM_TOKEN = "8126373920:AAEdRJ48gNqflX-M3kcihod4xegf314iup0"
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json"
FETCH_INTERVAL = 5   # segundos
LOOKBACK_MAX = 200

CODES_FILE = "codes.json"
STATE_FILE = "state.json"

# ============================================================
# VARS
# ============================================================

numeric_history = []
gp_history = []
last_issue = None

signals = []   # histórico de sinais gerados


# ============================================================
# HELPERS
# ============================================================

def load_json_safe(path, default):
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
