import telebot
import requests
import time
import json
import threading

# 🔹 Token do seu bot
BOT_TOKEN = "8126373920:AAEdRJ48gNqflX-M3kcihod4xegf314iup0"

# 🔹 Lista de códigos válidos
CODIGOS_VALIDOS = ["IA-ALFA-001", "IA-ALFA-002", "IA-ALFA-003", "IA-ALFA-004", "IA-ALFA-005"]

# 🔹 Dicionário para armazenar usuários ativos
usuarios_ativos = {}

# 🔹 Função para pegar últimos resultados
def obter_resultados():
    try:
        url = "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json"
        response = requests.get(url)
        data = response.json()
        return data["data"]["list"]
    except Exception as e:
        print("Erro ao obter resultados:", e)
        return []

# 🔹 Função de previsão simples (exemplo)
def prever_sinal(dados):
    ultimos = [int(x["number"]) for x in dados[:5]]
    soma = sum(ultimos)
    if soma % 2 == 0:
        return "🔴 Grande"
    else:
        return "🔵 Pequeno"

# 🔹 Bot principal
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=["start"])
def start(msg):
    texto = (
        "👋 Olá! Envie seu código de acesso com:\n\n"
        "`/redeem <CÓDIGO>`\n"
        "Exemplo: `/redeem IA-ALFA-001`\n\n"
        "Assim você será incluído para receber sinais automáticos."
    )
    bot.reply_to(msg, texto, parse_mode="Markdown")

@bot.message_handler(commands=["redeem"])
def redeem(msg):
    try:
        codigo = msg.text.split(" ")[1].strip()
    except:
        bot.reply_to(msg, "❌ Formato incorreto. Use `/redeem IA-ALFA-001`", parse_mode="Markdown")
        return

    if codigo in CODIGOS_VALIDOS:
        usuarios_ativos[msg.chat.id] = codigo
        bot.reply_to(msg, "✅ Código aceito! Você será incluído na lista para receber sinais automáticos.")
    else:
        bot.reply_to(msg, "❌ Código inválido ou expirado.")

# 🔹 Função de envio automático
def enviar_sinais():
    ultimo_id = None
    while True:
        dados = obter_resultados()
        if not dados:
            time.sleep(10)
            continue

        atual = dados[0]["issueNumber"]

        if atual != ultimo_id:
            ultimo_id = atual
            previsao = prever_sinal(dados)
            prox = str(int(atual) + 1)
            msg = (
                "🎯 *BOT SINAIS IA ALFA*\n\n"
                f"📊 Último Resultado: `{dados[0]['number']}`\n"
                f"🕒 Próximo Período: `{prox}`\n"
                f"💡 Próximo Sinal: {previsao}\n\n"
                "🚀 IA 2025 - Previsão Automática"
            )

            for user in list(usuarios_ativos.keys()):
                try:
                    bot.send_message(user, msg, parse_mode="Markdown")
                except:
                    pass

            print("Sinal enviado:", previsao)

        time.sleep(20)

# 🔹 Thread paralela para envio de sinais
threading.Thread(target=enviar_sinais, daemon=True).start()

# 🔹 Loop do bot
print("✅ BOT SINAIS IA ALFA iniciado com sucesso!")
bot.polling(non_stop=True)            with open(PERSIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            subscribers = {int(k):v for k,v in data.get("subscribers", {}).items()}
            signals = data.get("signals", [])
            stats.update(data.get("stats", {}))
            print("[state] carregado", PERSIST_FILE)
        except Exception as e:
            print("[state] falha ao carregar:", e)

def save_state():
    try:
        with open(PERSIST_FILE, "w", encoding="utf-8") as f:
            obj = {
                "subscribers": subscribers,
                "signals": signals[-1000:],
                "stats": stats
            }
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

# Simple getUpdates loop to detect /start and /stop
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
            if r.status_code == 200:
                data = r.json()
                if data.get("ok"):
                    for item in data.get("result", []):
                        last_update_id = item["update_id"]
                        # handle message
                        msg = item.get("message") or item.get("edited_message")
                        if not msg:
                            continue
                        chat_id = msg["chat"]["id"]
                        text = msg.get("text","").strip()
                        if text.startswith("/start"):
                            subscribers[chat_id] = {"last_sent": None}
                            save_state()
                            telegram_send_message(chat_id, "✅ Registrado! Você receberá o último sinal automático (enviaremos apenas novos sinais).")
                            # send immediate last prediction if exists
                            if gp_history:
                                pred, conf, next_issue = current_prediction_payload()
                                send_prediction_to_chat(chat_id, pred, conf, next_issue)
                        elif text.startswith("/stop"):
                            if chat_id in subscribers:
                                del subscribers[chat_id]
                                save_state()
                            telegram_send_message(chat_id, "🛑 Você foi desregistrado. Envie /start para receber sinais novamente.")
                        elif text.startswith("/status"):
                            # quick status
                            pred, conf, next_issue = current_prediction_payload()
                            st = f"Status:\nPróximo Período: {next_issue}\nPróximo Sinal: {'🟠 Grande' if pred=='G' else '🔵 Pequeno' if pred=='P' else '-'}\nConfiança: {conf}%\nAssinantes: {len(subscribers)}\nAcertos: {stats.get('correct',0)} / {stats.get('total',0)}  ({stats.get('accuracy',0)}%)"
                            telegram_send_message(chat_id, st)
                        # else ignore other messages
        except Exception as e:
            print("[tg] updates loop error:", e)
            time.sleep(2)

# helper to format and send prediction
def send_prediction_to_chat(chat_id, prediction, confidence, next_issue):
    if prediction not in ('G','P'):
        return
    # only send if different from last sent to this chat_id
    last = subscribers.get(chat_id, {}).get("last_sent")
    if last == prediction:
        return False
    text = (
        "🎯 Sinal Automático\n"
        f"🔮 Próxima Entrada: {'🟠 Grande' if prediction=='G' else '🔵 Pequeno'}\n"
        f"📅 Período: {next_issue}\n"
        f"🤖 Confiança: {confidence}%\n\n"
        "🔔 Para parar de receber: /stop"
    )
    ok = telegram_send_message(chat_id, text)
    if ok:
        # update last_sent and persist
        subscribers[chat_id]["last_sent"] = prediction
        save_state()
    return ok

# ---------------- Data source (simulated or real) ----------------
# sample simulated list (most recent first) - using the example you sent
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
                return []
        except Exception as e:
            print("[api] fetch error:", e)
            return []
    else:
        # return simulated copy (fresh copy each time)
        return list(SIMULATED_JSON["data"]["list"])

# ---------------- Adaptive predictor (same idea as before, compacted) ----------------
def find_pattern_candidates(seq_str):
    candidates = []
    n = len(seq_str)
    if n < 2:
        return candidates
    for w in ANAlYZE_WINDOW_SIZES_PLACEHOLDER:  # will be replaced below properly
        pass

# We'll implement predictive functions directly (cleaner)
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
        probG = agg.get('G', 0.0)/total
        probP = agg.get('P', 0.0)/total
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
        probG /= s; probP /= s
        # adjust by accuracy
        acc = stats.get("accuracy", 0.0)
        acc_factor = max(0.6, min(1.2, 1.0 + (acc - 50)/200))
        probG *= acc_factor; probP *= acc_factor
        s2 = probG + probP
        if s2 <= 0:
            return None, 0
        probG /= s2; probP /= s2
        return ('G', int(round(probG*100))) if probG>probP else ('P', int(round(probP*100)))
    # fallback: transition heuristic
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
    # frequency revert
    if g_count > p_count:
        return 'P', int(round((g_count/(g_count+p_count))*40))
    elif p_count > g_count:
        return 'G', int(round((p_count/(g_count+p_count))*40))
    else:
        return ('G' if int(time.time())%2==0 else 'P'), 20

# wrapper to get current prediction
def current_prediction_payload():
    seq = ''.join(gp_history[-LOOKBACK_MAX:]) if gp_history else ""
    pred, conf = adaptive_predict_from_seq(seq)
    # next_issue calculation
    next_issue = None
    if last_issue:
        try:
            next_issue = str(int(last_issue) + 1)
        except:
            next_issue = (last_issue or "") + "+1"
    return pred, conf, next_issue

# ---------------- Main loop: fetch -> predict -> send ----------------
def update_history_from_api_and_predict():
    global last_issue
    while True:
        try:
            lst = fetch_api_list()
            if lst:
                # API returns newest-first -> we will process accordingly
                # take first N then reverse to chronological
                take = min(len(lst), LOOKBACK_MAX)
                items = list(reversed(lst[:take]))
                added_new = False
                for item in items:
                    try:
                        n = int(item.get("number", item.get("num", 0)))
                    except:
                        continue
                    issue = item.get("issueNumber") or item.get("issue") or None
                    # append if new
                    if not numeric_history or (issue and issue != last_issue):
                        numeric_history.append(n)
                        gp_history.append('G' if n >= 5 else 'P')
                        last_issue = issue or last_issue
                        added_new = True
                # trim
                if len(numeric_history) > LOOKBACK_MAX:
                    del numeric_history[0: len(numeric_history)-LOOKBACK_MAX]
                    del gp_history[0: len(gp_history)-LOOKBACK_MAX]
                # if new actuals arrived, evaluate last pending signal:
                if added_new and signals:
                    # evaluate last
                    last_sig = signals[-1]
                    if not last_sig.get("evaluated"):
                        actual = gp_history[-1]
                        last_sig["actual"] = actual
                        last_sig["evaluated"] = True
                        last_sig["correct"] = (last_sig["prediction"] == actual)
                        # update stats
                        stats["total"] += 1
                        if last_sig["correct"]:
                            stats["correct"] += 1
                        stats["accuracy"] = round((stats["correct"]/stats["total"])*100, 2) if stats["total"]>0 else 0.0
                        save_state()
                # predict next
                pred, conf, next_issue = current_prediction_payload()
                # create a pending signal object
                sig = {"ts": int(time.time()), "prediction": pred, "confidence": conf, "next_issue": next_issue, "actual": None, "evaluated": False, "correct": None}
                signals.append(sig)
                # send to subscribers but only if differs from last_sent
                for chat_id in list(subscribers.keys()):
                    try:
                        send_prediction_to_chat(chat_id, pred, conf, next_issue)
                    except Exception as e:
                        print("[send] error to", chat_id, e)
                save_state()
        except Exception as e:
            print("[main loop] error:", e)
        time.sleep(FETCH_INTERVAL)

# -------------- Initialization & run --------------
def start_all():
    load_state()
    # start telegram updates loop
    t1 = threading.Thread(target=telegram_updates_loop, daemon=True)
    t1.start()
    # start main fetch/predict/send loop
    t2 = threading.Thread(target=update_history_from_api_and_predict, daemon=True)
    t2.start()
    print("Bot IA POPBRA iniciado. Aguarde e envie /start no seu bot para receber sinais.")
    # keep main thread alive
    while True:
        time.sleep(60)

if __name__ == "__main__":
    # small fix: ensure ANALYZE_WINDOW_SIZES exists; also import missing names used in functions
    from collections import defaultdict
    # start
    start_all()
