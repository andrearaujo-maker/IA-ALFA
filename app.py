
from flask import Flask, render_template, jsonify
import requests, threading, time, os, json, math
from collections import defaultdict
app = Flask(__name__, template_folder="templates")
API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json"
FETCH_INTERVAL = 5
KEEP_LAST = 300
STATE_FILE = "state_wingo.json"
numeric_history = []; gp_history = []; last_issue = None
pattern_db = defaultdict(lambda: {"G":0.0,"P":0.0})
signals = []; stats = {"total":0,"correct":0,"accuracy":0.0}
# simple perceptron state
perceptron = {"weights":None,"n_features":None}
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE,"r",encoding="utf-8") as f:
                obj = json.load(f)
            for k,v in obj.get("pattern_db",{}).items():
                pattern_db[k] = {"G":float(v.get("G",0.0)),"P":float(v.get("P",0.0))}
            signals[:] = obj.get("signals",[])
            stats.update(obj.get("stats",{}))
            p = obj.get("perceptron",None)
            if p: perceptron.update(p)
        except Exception as e:
            print("load_state error",e)
def save_state():
    try:
        pdb = {k:{"G":v["G"],"P":v["P"]} for k,v in pattern_db.items()}
        obj = {"pattern_db":pdb,"signals":signals[-1000:],"stats":stats,"perceptron":perceptron}
        with open(STATE_FILE,"w",encoding="utf-8") as f:
            json.dump(obj,f,ensure_ascii=False,indent=2)
    except Exception as e:
        print("save_state error",e)
def fetch_api_list():
    try:
        r = requests.get(API_URL,timeout=8)
        if r.status_code==200:
            return r.json().get("data",{}).get("list",[])
    except Exception as e:
        print("api error",e)
    return []
def update_history():
    global numeric_history,gp_history,last_issue
    lst = fetch_api_list()
    if not lst: return False
    take = min(len(lst),KEEP_LAST)
    items = list(reversed(lst[:take]))
    changed = False
    for item in items:
        try:
            n = int(item.get("number",0))
        except: continue
        issue = item.get("issueNumber") or item.get("issue")
        if not numeric_history:
            numeric_history.append(n); gp_history.append('G' if n>=5 else 'P'); last_issue=issue; changed=True
        else:
            if issue and issue==last_issue: continue
            if issue:
                try:
                    if last_issue is None or int(issue)>int(last_issue):
                        numeric_history.append(n); gp_history.append('G' if n>=5 else 'P'); last_issue=issue; changed=True; continue
                except: pass
            if n!=numeric_history[-1]:
                numeric_history.append(n); gp_history.append('G' if n>=5 else 'P'); last_issue=issue or last_issue; changed=True
    if len(numeric_history)>KEEP_LAST:
        numeric_history=numeric_history[-KEEP_LAST:]; gp_history=gp_history[-KEEP_LAST:]
    return changed
# simple pattern + perceptron (compact)
WINDOW_SIZES=[3,4,5]
def record_pattern(p,nxt,w=1.0):
    entry = pattern_db[p]; entry[nxt]=entry.get(nxt,0.0)+float(w)
def find_candidates(seq):
    c=[]; n=len(seq)
    for w in WINDOW_SIZES:
        if n<w: continue
        tail=seq[-w:]; db=pattern_db.get(tail)
        if db:
            total=db.get("G",0)+db.get("P",0)
            if total>0:
                c.append(('G',db.get("G",0)*(1.2+w/10.0))); c.append(('P',db.get("P",0)*(1.2+w/10.0)))
    return c
def predict_from_history(gp_list):
    if not gp_list: return None,0
    seq=''.join(gp_list); cand=find_candidates(seq)
    if cand:
        agg=defaultdict(float)
        for v,w in cand: agg[v]+=w
        total=sum(agg.values()); probG=agg.get('G',0)/total; probP=agg.get('P',0)/total
        pred='G' if probG>probP else 'P'; conf=int(round(max(probG,probP)*100))
        return pred,conf
    g=gp_list.count('G'); p=gp_list.count('P')
    if g+p==0: return None,0
    return ('G' if g>p else 'P'), int(round(max(g,p)/(g+p)*40))
def init_perceptron(nf):
    perceptron["n_features"]=nf; perceptron["weights"]=[0.0]*(nf+1)
def features_from_sequence(gp_list):
    seq=gp_list[-12:]; cntG=seq.count('G'); cntP=seq.count('P'); diff=(cntG-cntP)/12.0
    onehot=[1.0 if s=='G' else -1.0 for s in seq[-8:]]; pad=8-len(onehot)
    onehot=[0.0]*pad+onehot
    return [diff]+onehot
def perceptron_predict(fv):
    if perceptron["weights"] is None: init_perceptron(len(fv))
    w=perceptron["weights"]; s=w[0]
    for i,v in enumerate(fv): s+=w[i+1]*v
    try: p=0.5*(1.0+math.tanh(s))
    except: p=max(0.01,min(0.99,0.5+s*0.1))
    return p
def perceptron_train(fv,label):
    if perceptron["weights"] is None: init_perceptron(len(fv))
    w=perceptron["weights"]; pred=perceptron_predict(fv); err=(label-pred)
    w[0]+=0.05*err
    for i,v in enumerate(fv): w[i+1]+=0.05*(err*v)-0.0001*w[i+1]
def create_pending(pred,conf,next_issue):
    signals.append({"ts":int(time.time()),"prediction":pred,"confidence":conf,"next_issue":next_issue,"actual":None,"evaluated":False,"correct":None})
    if len(signals)>1000: del signals[0:len(signals)-1000]
    save_state()
def evaluate_pending():
    if not signals or not gp_history: return
    last=signals[-1]
    if last.get("evaluated"): return
    actual=gp_history[-1]; last["actual"]=actual; last["evaluated"]=True; last["correct"]= (last["prediction"]==actual)
    stats["total"]=stats.get("total",0)+1
    if last["correct"]: stats["correct"]=stats.get("correct",0)+1
    stats["accuracy"]=round((stats.get("correct",0)/stats.get("total",1))*100,2)
    try:
        seq=''.join(gp_history); n=len(seq)
        for w in WINDOW_SIZES:
            if n<=w: continue
            tail=seq[-(w+1):-1]
            if tail:
                record_pattern(tail, actual, weight=2.0 if last["correct"] else 0.6)
        fv = features_from_sequence(gp_history[:-1] if len(gp_history)>1 else gp_history)
        perceptron_train(fv, 1 if actual=='G' else 0)
    except Exception as e:
        print("eval error",e)
    save_state()
def predict_next():
    p_pred,p_conf = predict_from_history(gp_history[-KEEP_LAST:])
    fv = features_from_sequence(gp_history)
    try: p_prob = perceptron_predict(fv)
    except: p_prob=None
    if p_prob is not None:
        pat_prob_G = p_conf/100.0 if p_pred=='G' else (1.0 - p_conf/100.0 if p_pred=='P' else 0.5)
        combG = 0.6*p_prob + 0.4*pat_prob_G
        combP = 1.0-combG
        pred='G' if combG>=combP else 'P'; conf=int(round(max(combG,combP)*100))
        conf = int(min(99,max(10,conf*(0.8+(stats.get("accuracy",50)/200.0)))))
        return pred,conf
    return p_pred,p_conf
def background_loop():
    global last_issue
    while True:
        changed = update_history()
        if changed: evaluate_pending()
        pred,conf = predict_next()
        next_issue = None
        if last_issue:
            try: next_issue = str(int(last_issue)+1)
            except: next_issue = (last_issue or "") + "+1"
        create_pending(pred,conf,next_issue)
        time.sleep(FETCH_INTERVAL)
@app.route("/")
def index(): return render_template("painel.html")
@app.route("/predicao")
def predicao():
    pred,conf = predict_next(); next_issue=None
    if last_issue:
        try: next_issue=str(int(last_issue)+1)
        except: next_issue=(last_issue or "") + "+1"
    last_results = gp_history[-10:][::-1] if gp_history else []
    recent_signals = signals[-40:] if signals else []
    return jsonify({"prediction":pred,"confidence":conf,"next_issue":next_issue,"last_results":last_results,"signals":recent_signals,"stats":stats})
if __name__=="__main__":
    load_state(); init_perceptron(1+8)
    th = threading.Thread(target=background_loop,daemon=True); th.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT","8000")))
