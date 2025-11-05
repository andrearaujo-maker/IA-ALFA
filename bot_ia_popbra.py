import json
import os
import time
import requests
import threading
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ==========================================================
# CONFIGURAÇÕES
# ==========================================================

BOT_TOKEN = "8126373920:AAEdRJ48gNqflX-M3kcihod4xegf314iup0"
API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json"

USE_REAL_API = True      # ✅ Se a API real falhar → cai para simulado
FETCH_INTERVAL = 12      # Segundos entre verificações

STATE_FILE = "state.json"
CODES_FILE = "codes.json"

# ==========================================================
# SIMULADO (backup se API falhar)
# ==========================================================

SIMULATED_JSON = {
    "data": {
        "list": [
            {"period": "20250001", "number": "7"},
            {"period": "20250002", "number": "2"},
            {"period": "20250003", "number": "8"},
            {"period": "20250004", "number": "3"},
        ]
    }
}

# ==========================================================
# BANCO EM ARQUIVOS
# ==========================================================

if not os.path.exists(STATE_FILE):
    with open(STATE_FILE, "w") as f:
        json.dump({"history": [], "subscribers": {}}, f)

if not os.path.exists(CODES_FILE):
    with open(CODES_FILE, "w") as f:
        json.dump({}, f)


def load_state():
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def save_state():
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def load_codes():
    with open(CODES_FILE, "r") as f:
        return json.load(f)


def save_codes():
    with open(CODES_FILE, "w") as f:
        json.dump(access_codes, f, indent=2)


state = load_state()
history = state["history"]
subscribers = state["subscribers"]

access_codes = load_codes()

# ==========================================================
# API
# ==========================================================

def fetch_api_list():
    """Força fallback para SIMULATED se a API não tiver valores."""
    if USE_REAL_API:
        try:
            r = requests.get(API_URL, timeout=6)
            if r.status_code == 200:
                data = r.json().get("data", {}).get("list", [])
                if data:
                    return data
                else:
                    print("[API] vazio → usando simulado")
                    return list(SIMULATED_JSON["data"]["list"])
        except Exception as e:
            print("[API] erro → usando simulado:", e)
            return list(SIMULATED_JSON["data"]["list"])
    return list(SIMULATED_JSON["data"]["list"])

# ==========================================================
# PREVISÃO
# ==========================================================

def predict(history):
    if not history:
        return "Grande", 50
    last = int(history[-1]["number"])
    if last > 4:
        return "Pequeno", 52
    else:
        return "Grande", 53

# ==========================================================
# ENVIO
# ==========================================================

async def send_prediction_to_chat(app, chat_id, pred, conf, next_period):
    text = (
        "🎯 *SINAL GERADO!*\n\n"
        f"👉 Entrada: *{pred}*\n"
        f"📈 Confiança: *{conf}%*\n"
        f"⏱️ Período: *{next_period}*\n"
        "🎯 Estratégia: *Martingale (1, 2, 6, 18, 54, 162)*\n"
        "🚀 Boa sorte!"
    )
    await app.bot.send_message(chat_id, text, parse_mode="Markdown")


# ==========================================================
# LOOP AUTOMÁTICO
# ==========================================================

def loop_fetch_and_send(app):
    global history

    while True:
        lst = fetch_api_list()
        lst_sorted = sorted(lst, key=lambda x: x["period"])
        added = False

        known = {x["period"] for x in history}

        for item in lst_sorted:
            if item["period"] not in known:
                history.append(item)
                added = True

        state["history"] = history
        save_state()

        pred, conf = predict(history)

        # Define próximo período
        if history:
            next_period = str(int(history[-1]["period"]) + 1)
        else:
            next_period = "???"

        # ✅ Mesmo se NÃO vier número novo, vai gerar SINAL!
        # Antes era: if added and signals
        print(f"[IA] Nova previsão gerada → {pred} ({conf}%)")

        for chat_id in subscribers.keys():
            app.create_task(send_prediction_to_chat(app, chat_id, pred, conf, next_period))

        time.sleep(FETCH_INTERVAL)


# ==========================================================
# COMANDOS
# ==========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Olá! Envie /codigo <seu código> para ativar.")


async def codigo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global subscribers
    if len(context.args) == 0:
        await update.message.reply_text("❌ Use: /codigo ABC123")
        return

    code = context.args[0].strip()

    if code not in access_codes or access_codes[code] is not None:
        await update.message.reply_text("❌ Código inválido ou já utilizado.")
        return

    access_codes[code] = update.effective_chat.id
    subscribers[str(update.effective_chat.id)] = True
    save_codes()
    save_state()

    await update.message.reply_text("✅ Código aceito! Você está ativo e receberá sinais automáticos.")


# ==========================================================
# MAIN
# ==========================================================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("codigo", codigo))

    th = threading.Thread(target=loop_fetch_and_send, args=(app,), daemon=True)
    th.start()

    print("✅ BOT ONLINE")
    app.run_polling()


if __name__ == "__main__":
    main()
