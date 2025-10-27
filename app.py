from flask import Flask, render_template, jsonify
import requests, threading, time, os, json, math
from collections import defaultdict

app = Flask(__name__, template_folder="templates")

# -------------- CONFIG --------------
API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json"
FETCH_INTERVAL = 5                # segundos
KEEP_LAST = 300                   # quantos resultados históricos manter na memória
STATE_FILE = "state_wingo.json"   # arquivo para persistir aprendizado

# -------------- ESTADO --------------
numeric_history = []   # lista de números (ordem antiga -> nova)
gp_history = []        # 'G' ou 'P' (ordem antiga -> nova)
last_issue = None

# pattern_db armazena contagens de transições por padrão
pattern_db = defaultdict(lambda: {"G": 0.0, "P": 0.0})

# signals grava previsões com timestamp para histórico/avaliação
signals = []   # cada item: {ts, prediction, confidence, next_issue, actual, evaluated, correct}

stats = {"total": 0, "correct": 0, "accuracy": 0.0}

# perceptron simples para aprendizado online
perceptron = {"weights": None, "n_features": None}
FEATURE_WINDOW = 12
K_ONEHOT = 8
LEARNING_RATE = 0.05
REGULARIZATION = 0.0001
MAX_SIGNALS_KEEP = 1000

# ---------------- PERSISTÊNCIA ----------------
def load_state():
    global pattern_db, signals, stats, perceptron
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                obj = json.load(f)
            pdb = obj.get("pattern_db", {})
            for k, v in pdb.items():
                pattern_db[k] = {"G": float(v.get("G", 0.0)), "P": float(v.get("P", 0.0))}
            signals[:] = obj.get("signals", [])
            stats.update(obj.get("stats", {}))
            p = obj.get("perceptron", None)
            if p:
                perceptron["weights"] = p.get("weights")
                perceptron["n_features"] = p.get("n_features")
            print("[STATE] loaded")
        except Exception as e:
            print("[STATE] load error:", e)

def save_state():
    try:
        pdb_plain = {k: {"G": v["G"], "P": v["P"]} for k, v in pattern_db.items()}
        obj = {"pattern_db": pdb_plain,
               "signals": signals[-MAX_SIGNALS_KEEP:],
               "stats": stats,
               "perceptron": {"weights": perceptron["weights"], "n_features": perceptron["n_features"]}}
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[STATE] save error:", e)

# ---------------- API ----------------
def fetch_api_list():
    try:
        r = requests.get(API_URL, timeout=8)
        if r.status_code == 200:
            js = r.json()
            lst = js.get("data", {}).get("list", [])
            return lst
        else:
            print("[API] status", r.status_code)
            return []
    except Exception as e:
        print("[API] error:", e)
        return []

# ---------------- HISTÓRICO ----------------
def update_history():
    global numeric_history, gp_history, last_issue
    lst = fetch_api_list()
    if not lst:
        return False
    # API vem mais recente primeiro, pegamos os N e revert queremos antiga->nova
    take = min(len(lst), KEEP_LAST)
    slice_items = lst[:take]
    slice_items = list(reversed(slice_items))
    changed = False
    for item in slice_items:
        try:
            n = int(item.get("number", item.get("num", 0)))
        except:
            continue
        issue = item.get("issueNumber") or item.get("issue") or None
        # se histórico vazio, preenche
        if not numeric_history:
            numeric_history.append(n)
            gp_history.append('G' if n >= 5 else 'P')
            last_issue = issue or last_issue
            changed = True
        else:
            # evita duplicar se mesmo issue
            if issue and issue == last_issue:
                continue
            # se issue for maior (mais novo) adiciona
            if issue:
                try:
                    if last_issue is None or int(issue) > int(last_issue):
                        numeric_history.append(n)
                        gp_history.append('G' if n >= 5 else 'P')
                        last_issue = issue
                        changed = True
                        continue
                except:
                    pass
            # se número diferente do último, adiciona (fallback)
            if n != numeric_history[-1]:
                numeric_history.append(n)
                gp_history.append('G' if n >= 5 else 'P')
                last_issue = issue or last_issue
                changed = True
    # truncar histórico
    if len(numeric_history) > KEEP_LAST:
        numeric_history = numeric_history[-KEEP_LAST:]
        gp_history = gp_history[-KEEP_LAST:]
    return changed

# ---------------- PATTERNS ----------------
WINDOW_SIZES = [3, 4, 5, 6]

def record_pattern(pattern, next_char, weight=1.0):
    entry = pattern_db[pattern]
    entry[next_char] = entry.get(next_char, 0.0) + float(weight)

def find_candidates(seq_str):
    candidates = []
    n = len(seq_str)
    # use padrão exato do final
    for w in WINDOW_SIZES:
        if n < w: continue
        tail = seq_str[-w:]
        db_entry = pattern_db.get(tail)
        if db_entry:
            total = db_entry.get("G", 0.0) + db_entry.get("P", 0.0)
            if total > 0:
                candidates.append(('G', db_entry.get("G", 0.0) * (1.5 + w / 10.0)))
                candidates.append(('P', db_entry.get("P", 0.0) * (1.5 + w / 10.0)))
    # busca por repetição de padrão no passado
    for w in WINDOW_SIZES:
        if n <= w: continue
        pattern = seq_str[-w:]
        for i in range(0, n - w):
            if seq_str[i:i+w] == pattern and i + w < n:
                nxt = seq_str[i+w]
                recency = 1.0 + (i / max(1, n))
                weight = w * recency
                candidates.append((nxt, weight))
    return candidates

def predict_from_history(gp_list):
    if not gp_list: return None, 0
    seq = ''.join(gp_list)
    candidates = find_candidates(seq)
    if candidates:
        agg = defaultdict(float)
        for v, w in candidates:
            agg[v] += w
        total = sum(agg.values())
        if total <= 0: return None, 0
        probG = agg.get('G', 0.0) / total
        probP = agg.get('P', 0.0) / total
        # ajuste por transição recente do último
        last = seq[-1]
        trans = {'G': 0, 'P': 0}
        for i in range(len(seq)-1):
            if seq[i] == last:
                trans[seq[i+1]] += 1
        trans_total = trans['G'] + trans['P']
        if trans_total > 0:
            tG = trans['G'] / trans_total
            tP = trans['P'] / trans_total
            probG = 0.7 * probG + 0.3 * tG
            probP = 0.7 * probP + 0.3 * tP
        s = probG + probP
        if s <= 0: return None, 0
        probG /= s
        probP /= s
        # ajuste por acurácia atual
        acc = stats.get("accuracy", 50.0)
        acc_factor = max(0.7, min(1.3, 1.0 + (acc - 50) / 200))
        probG *= acc_factor
        probP *= acc_factor
        s2 = probG + probP
        if s2 <= 0: return None, 0
        probG /= s2
        probP /= s2
        pred = 'G' if probG > probP else 'P'
        conf = int(round(max(probG, probP) * 100))
        return pred, conf
    # fallback simples
    g = gp_list.count('G'); p = gp_list.count('P')
    if g + p == 0: return None, 0
    if g > p: return 'G', int(round((g/(g+p))*40))
    elif p > g: return 'P', int(round((p/(g+p))*40))
    else:
        return ('G' if int(time.time()) % 2 == 0 else 'P'), 20

# ---------------- PERCEPTRON ----------------
def init_perceptron(n_features):
    perceptron["n_features"] = n_features
    perceptron["weights"] = [0.0] * (n_features + 1)

def features_from_sequence(gp_list):
    seq = gp_list[-FEATURE_WINDOW:] if gp_list else []
    cntG = seq.count('G'); cntP = seq.count('P')
    diff = (cntG - cntP) / max(1, FEATURE_WINDOW)
    onehot = []
    lastK = seq[-K_ONEHOT:] if seq else []
    pad = K_ONEHOT - len(lastK)
    for _ in range(pad): onehot.append(0.0)
    for s in lastK: onehot.append(1.0 if s == 'G' else -1.0)
    fv = [diff] + onehot
    return fv

def perceptron_predict(fv):
    if perceptron["weights"] is None:
        init_perceptron(len(fv))
    w = perceptron["weights"]
    s = w[0]
    for i, val in enumerate(fv):
        s += w[i+1] * val
    try:
        p = 0.5 * (1.0 + math.tanh(s))
    except:
        p = max(0.01, min(0.99, 0.5 + s*0.1))
    return p

def perceptron_train(fv, label):
    if perceptron["weights"] is None:
        init_perceptron(len(fv))
    w = perceptron["weights"]
    pred_p = perceptron_predict(fv)
    err = (label - pred_p)
    w[0] += LEARNING_RATE * err
    for i, val in enumerate(fv):
        w[i+1] += LEARNING_RATE * (err * val) - REGULARIZATION * w[i+1]

# ---------------- SINAIS & AVALIAÇÃO ----------------
def create_pending_signal(prediction, confidence, next_issue):
    sig = {"ts": int(time.time()), "prediction": prediction, "confidence": confidence,
           "next_issue": next_issue, "actual": None, "evaluated": False, "correct": None}
    signals.append(sig)
    if len(signals) > MAX_SIGNALS_KEEP:
        del signals[0: len(signals)-MAX_SIGNALS_KEEP]
    save_state()

def evaluate_pending():
    if not signals: return
    last_sig = signals[-1]
    if last_sig.get("evaluated"): return
    if not gp_history: return
    actual = gp_history[-1]
    last_sig["actual"] = actual
    last_sig["evaluated"] = True
    last_sig["correct"] = (last_sig["prediction"] == actual)
    stats["total"] = stats.get("total", 0) + 1
    if last_sig["correct"]:
        stats["correct"] = stats.get("correct", 0) + 1
    stats["accuracy"] = round((stats.get("correct", 0) / stats.get("total", 1)) * 100, 2)
    # ajustar pattern_db e treinar perceptron
    try:
        seq = ''.join(gp_history); n = len(seq)
        for w in WINDOW_SIZES:
            if n <= w: continue
            tail = seq[-(w+1):-1]
            if tail:
                if last_sig["correct"]:
                    record_pattern(tail, actual, weight=2.0 * (1 + w/10.0))
                else:
                    record_pattern(tail, actual, weight=0.6 * (1 + w/10.0))
        fv_seq = gp_history[:-1] if len(gp_history) > 1 else gp_history
        fv = features_from_sequence(fv_seq)
        label = 1 if actual == 'G' else 0
        perceptron_train(fv, label)
    except Exception as e:
        print("[EVAL] error:", e)
    save_state()

# ---------------- ENSEMBLE DE PREVISÃO ----------------
def predict_next():
    p_pred, p_conf = predict_from_history(gp_history[-KEEP_LAST:])
    fv = features_from_sequence(gp_history)
    p_prob = None
    try:
        p_prob = perceptron_predict(fv)
    except:
        p_prob = None
    if p_prob is not None:
        pat_prob_G = 0.5
        if p_pred == 'G': pat_prob_G = p_conf / 100.0
        elif p_pred == 'P': pat_prob_G = 1.0 - (p_conf / 100.0)
        w_perc = 0.6; w_pat = 0.4
        combG = w_perc * p_prob + w_pat * pat_prob_G
        combP = 1.0 - combG
        pred = 'G' if combG >= combP else 'P'
        conf = int(round(max(combG, combP) * 100))
        acc = stats.get("accuracy", 50.0)
        conf = int(min(99, max(10, conf * (0.8 + (acc / 200.0)))))
        return pred, conf
    else:
        return p_pred, p_conf

# ---------------- LOOP BACKGROUND ----------------
def background_loop():
    global last_issue
    while True:
        changed = update_history()
        if changed:
            evaluate_pending()
        pred, conf = predict_next()
        next_issue = None
        if last_issue:
            try:
                next_issue = str(int(last_issue) + 1)
            except:
                next_issue = (last_issue or "") + "+1"
        create_pending_signal(pred, conf, next_issue)
        time.sleep(FETCH_INTERVAL)

# ---------------- ROTAS ----------------
from flask import render_template

@app.route("/")
def index():
    return render_template("painel.html")

@app.route("/predicao")
def predicao():
    pred, conf = predict_next()
    next_issue = None
    if last_issue:
        try:
            next_issue = str(int(last_issue) + 1)
        except:
            next_issue = (last_issue or "") + "+1"
    last_results = gp_history[-10:][::-1] if gp_history else []
    recent_signals = signals[-40:] if signals else []
    return jsonify({
        "prediction": pred,
        "confidence": conf,
        "next_issue": next_issue,
        "last_results": last_results,
        "signals": recent_signals,
        "stats": stats
    })

# ---------------- START ----------------
if __name__ == "__main__":
    load_state()
    init_perceptron(1 + K_ONEHOT)
    th = threading.Thread(target=background_loop, daemon=True)
    th.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
