import telebot
import json
import time
import threading
import random
from datetime import datetime

TOKEN = "8126373920:AAEdRJ48gNqflX-M3kcihod4xegf314iup0"
bot = telebot.TeleBot(TOKEN)

# Arquivos de controle
CODIGOS_FILE = "codigos.txt"
USUARIOS_ATIVOS_FILE = "usuarios_ativos.json"

# Função para carregar e salvar usuários
def carregar_usuarios_ativos():
    try:
        with open(USUARIOS_ATIVOS_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def salvar_usuarios_ativos(lista):
    with open(USUARIOS_ATIVOS_FILE, "w") as f:
        json.dump(lista, f)

# Carregar códigos de acesso
def carregar_codigos():
    try:
        with open(CODIGOS_FILE, "r") as f:
            return [linha.strip() for linha in f.readlines()]
    except:
        return []

# Função de previsão da IA (simulação com lógica inteligente)
def gerar_previsao():
    numero = random.randint(0, 9)
    if numero >= 5:
        sinal = "🟠 Grande"
    else:
        sinal = "🔵 Pequeno"
    return sinal, numero

# Função para enviar sinal automaticamente
def enviar_sinal_automatico():
    while True:
        usuarios = carregar_usuarios_ativos()
        if usuarios:
            sinal, numero = gerar_previsao()
            periodo = datetime.now().strftime("%Y%m%d%H%M%S")
            mensagem = (
                f"🎯 *Sinal Gerado!*\n\n"
                f"👉 Entrada: {sinal}\n"
                f"🔢 Número base: {numero}\n"
                f"📅 Período: `{periodo}`\n"
                f"💰 Estratégia: Martingale (1, 2, 6, 18, 54, 162)\n\n"
                f"👉 Use /green se ganhar\n"
                f"👉 Use /red se perder\n\n"
                f"🚀 Boa sorte!"
            )
            for user_id in usuarios:
                try:
                    bot.send_message(user_id, mensagem, parse_mode="Markdown")
                except Exception as e:
                    print(f"Erro ao enviar para {user_id}: {e}")
        time.sleep(30)  # envia a cada 30s

# Comando /start
@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.chat.id
    bot.reply_to(
        message,
        "🔐 Olá! Bem-vindo ao *Bot de Sinais IA*.\n\n"
        "Para ativar o acesso, envie seu código com o comando:\n\n"
        "`/codigo SEU_CODIGO_AQUI`",
        parse_mode="Markdown"
    )

# Comando /codigo
@bot.message_handler(commands=["codigo"])
def verificar_codigo(message):
    partes = message.text.split()
    if len(partes) < 2:
        bot.reply_to(message, "❌ Envie o código assim: `/codigo SEU_CODIGO`", parse_mode="Markdown")
        return

    codigo = partes[1].strip()
    codigos = carregar_codigos()
    usuarios = carregar_usuarios_ativos()

    if codigo in codigos:
        if message.chat.id not in usuarios:
            usuarios.append(message.chat.id)
            salvar_usuarios_ativos(usuarios)
            codigos.remove(codigo)
            with open(CODIGOS_FILE, "w") as f:
                f.write("\n".join(codigos))
            bot.reply_to(message, "✅ *Código aceito!* Você está ativo e receberá sinais automáticos.", parse_mode="Markdown")
        else:
            bot.reply_to(message, "⚠️ Você já está ativo.", parse_mode="Markdown")
    else:
        bot.reply_to(message, "❌ Código inválido ou já utilizado.", parse_mode="Markdown")

# Inicia a thread de envio de sinais
threading.Thread(target=enviar_sinal_automatico, daemon=True).start()

# Mantém o bot ativo
print("🤖 Bot de Sinais IA iniciado e rodando...")
bot.polling(none_stop=True)# ---------------- Persistence ----------------
def load_state():
    global state
    if os.path.exists(PERSIST_FILE):
        try:
            with open(PERSIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                state.update(data)
            print("[state] carregado", PERSIST_FILE)
        except Exception as e:
            print("[state] falha ao carregar estado:", e)

def save_state():
    try:
        with open(PERSIST_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[state] falha ao salvar estado:", e)

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

# ---------------- Codes file helpers ----------------
def load_codes():
    """Return a set of codes currently available (uppercase, stripped)."""
    if not os.path.exists(CODES_FILE):
        return set()
    with open(CODES_FILE, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]
    return set([l.upper() for l in lines])

def remove_code_from_file(code):
    """Remove a used code (modify codigos.txt)"""
    code = code.strip().upper()
    if not os.path.exists(CODES_FILE):
        return False
    with open(CODES_FILE, "r", encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f.readlines()]
    new_lines = [l for l in lines if l.strip().upper() != code]
    try:
        with open(CODES_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines) + ("\n" if new_lines else ""))
        return True
    except Exception as e:
        print("[codes] remove error:", e)
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
                return r.json().get("data", {}).get("list", [])
            else:
                print("[api] status", r.status_code)
                return []
        except Exception as e:
            print("[api] fetch error:", e)
            return []
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
        acc = state.get("stats", {}).get("accuracy", 0.0)
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

# ---------------- Send logic ----------------
def send_prediction_to_chat(chat_id, prediction, confidence, next_issue):
    if prediction not in ('G','P'):
        return False
    sub = state["subscribers"].get(str(chat_id))
    if not sub or not sub.get("active"):
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
    ok = telegram_send_message(chat_id, text)
    if ok:
        state["subscribers"][str(chat_id)]["last_sent"] = prediction
        save_state()
    return ok

# ---------------- Telegram getUpdates loop (commands handling) ----------------
last_update_id = None
def telegram_updates_loop():
    global last_update_id
    print("[tg] iniciando loop de updates (usuários devem enviar /start e depois /redeem <CÓDIGO>)")
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
                    telegram_send_message(chat_id,
                        "Bem-vindo! Para ativar seu acesso envie: /redeem <CÓDIGO>\n"
                        "Exemplo: /redeem ALFA-ACCESS-9321\n\nSe você já tem código, cole aqui.")
                elif cmd == "/redeem":
                    if len(parts) < 2:
                        telegram_send_message(chat_id, "Envie: /redeem <CÓDIGO>")
                        continue
                    code = parts[1].strip().upper()
                    available = load_codes()
                    if code not in available:
                        telegram_send_message(chat_id, "❌ Código inválido ou já utilizado.")
                        continue

                    # 🔹 Remove o código usado e registra o assinante
                    ok = remove_code_from_file(code)
                    if not ok:
                        telegram_send_message(chat_id, "Erro ao processar o código. Tente novamente.")
                        continue

                    # 🔹 Marca o usuário como ativo imediatamente
                    state["subscribers"][str(chat_id)] = {
                        "last_sent": None,
                        "active": True,
                        "code": code,
                        "activated_at": int(time.time())
                    }
                    save_state()

                    telegram_send_message(chat_id, "✅ Código aceito! Você está ativo e receberá sinais automáticos.")

                    # 🔹 Envia uma previsão imediata
                    pred, conf, next_issue = current_prediction_payload()
                    if pred in ("G", "P"):
                        send_prediction_to_chat(chat_id, pred, conf, next_issue)
                elif cmd == "/stop":
                    if str(chat_id) in state["subscribers"]:
                        state["subscribers"].pop(str(chat_id), None)
                        save_state()
                        telegram_send_message(chat_id, "🛑 Você foi desregistrado. Para voltar, envie /redeem <CÓDIGO> novamente.")
                    else:
                        telegram_send_message(chat_id, "Você não está registrado.")
                elif cmd == "/status":
                    pred, conf, next_issue = current_prediction_payload()
                    s = f"Status:\nPeríodo: {next_issue}\nSinal: {'🟠 Grande' if pred=='G' else '🔵 Pequeno' if pred=='P' else '-'}\nConfiança: {conf}%\nAssinantes: {sum(1 for v in state['subscribers'].values() if v.get('active'))}\nAcertos: {state['stats'].get('correct',0)} / {state['stats'].get('total',0)} ({state['stats'].get('accuracy',0)}%)"
                    telegram_send_message(chat_id, s)
                elif cmd == "/admin":
                    telegram_send_message(chat_id, "Comandos admin não disponíveis neste script público.")
                else:
                    pass
        except Exception as e:
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
                items = list(reversed(lst[:take]))
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
                    del numeric_history[0: len(numeric_history)-LOOKBACK_MAX]
                    del gp_history[0: len(gp_history)-LOOKBACK_MAX]
                if added_new and state.get("signals"):
                    last_sig = state["signals"][-1]
                    if not last_sig.get("evaluated") and gp_history:
                        actual = gp_history[-1]
                        last_sig["actual"] = actual
                        last_sig["evaluated"] = True
                        last_sig["correct"] = (last_sig["prediction"] == actual)
                        state["stats"]["total"] = state["stats"].get("total",0) + 1
                        if last_sig["correct"]:
                            state["stats"]["correct"] = state["stats"].get("correct",0) + 1
                        total = state["stats"].get("total",0)
                        correct = state["stats"].get("correct",0)
                        state["stats"]["accuracy"] = round((correct/total)*100,2) if total>0 else 0.0
                        save_state()
                pred, conf, next_issue = current_prediction_payload()
                sig = {"ts": int(time.time()), "prediction": pred, "confidence": conf, "next_issue": next_issue, "evaluated": False}
                state.setdefault("signals", []).append(sig)
                for chat_id_str, info in list(state["subscribers"].items()):
                    try:
                        cid = int(chat_id_str)
                        if info.get("active"):
                            send_prediction_to_chat(cid, pred, conf, next_issue)
                    except Exception as e:
                        print("[send] error to", chat_id_str, e)
                save_state()
        except Exception as e:
            print("[main] loop error:", e)
        time.sleep(FETCH_INTERVAL)

# --------------- Start ----------------
if __name__ == "__main__":
    load_state()
    t1 = threading.Thread(target=telegram_updates_loop, daemon=True)
    t1.start()
    t2 = threading.Thread(target=main_loop, daemon=True)
    t2.start()
    print("Bot iniciado. Peça para clientes enviarem /start e depois /redeem <CÓDIGO>.")
    while True:
        time.sleep(30)
