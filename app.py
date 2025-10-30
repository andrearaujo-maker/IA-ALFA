# app.py
# Flask app que serve o painel e obtém dados da API POPBRA
import os
import time
import json
from datetime import datetime
from collections import deque, Counter

import requests
from flask import Flask, jsonify, render_template_string, request

API_URL = os.environ.get("API_URL", "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json")
# opcional proxy (ex: http://meu-proxy:port). Suporta env var PROXY_URL
PROXY_URL = os.environ.get("PROXY_URL", "")  # se vazio, sem proxy

FETCH_COUNT = int(os.environ.get("FETCH_COUNT", 10))  # quantos últimos pegar
UPDATE_INTERVAL = int(os.environ.get("UPDATE_INTERVAL", 5))  # segundos (front-end)
# memória em runtime (simples)
history = deque(maxlen=200)  # armazena tuplas (periodo, number, gp, timestamp, outcome_ok)
# onde gp = 'G' ou 'P'

app = Flask(__name__, static_folder="static", static_url_path="/static")

# template HTML (inline). Mantive estrutura simples e estilo próximo ao seu design.
# Você pode substituir por arquivo Jinja separado se desejar.
INDEX_HTML = """
<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Painel IA WinGo</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#071327; --card:#071b2a; --neon:#00e6ff; --accent:#ff8a00;
    --glass: rgba(255,255,255,0.03);
  }
  body{font-family:Inter,system-ui,Segoe UI,Arial;background:linear-gradient(180deg,#001021 0%, #021425 100%);margin:0;color:#cfeff6}
  .wrap{max-width:420px;margin:20px auto;padding:18px}
  .card{background:linear-gradient(180deg,rgba(255,255,255,0.02), rgba(255,255,255,0.01));border-radius:18px;padding:18px;box-shadow:0 8px 30px rgba(0,0,0,0.6);border:1px solid rgba(0,255,255,0.03)}
  h1{color:var(--neon);text-align:center;margin:6px 0;font-weight:800}
  .big{font-size:36px;text-align:center;margin:10px 0;font-weight:800;color:var(--neon);text-shadow:0 0 14px rgba(0,230,255,0.12)}
  .sub{color:#9adbe6;text-align:center;margin-bottom:6px}
  .meta{color:#9adbe6;text-align:center;margin:6px 0}
  .box{background:linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));border-radius:12px;padding:12px;margin:12px 0;border:1px solid rgba(0,255,255,0.03)}
  .row{display:flex;gap:8px;justify-content:center;align-items:center}
  .dotG{width:36px;height:36px;border-radius:50%;background:linear-gradient(180deg,#ff9b38,#ff6a00);display:inline-block;line-height:36px;text-align:center;color:#fff;font-weight:700}
  .dotP{width:36px;height:36px;border-radius:50%;background:linear-gradient(180deg,#2db7ff,#007bff);display:inline-block;line-height:36px;text-align:center;color:#fff;font-weight:700}
  .hist-list{list-style:none;padding:0;margin:0}
  .hist-list li{display:flex;justify-content:space-between;padding:8px 6px;border-bottom:1px dashed rgba(255,255,255,0.02);font-size:14px;color:#bfeff8}
  .error{color:#ff6b6b;text-align:center;margin-top:8px}
  .small{font-size:12px;color:#9adbe6;text-align:center}
  button{background:var(--neon);border:none;padding:8px 12px;border-radius:8px;color:#003;cursor:pointer}
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <div style="display:flex;align-items:center;gap:10px">
      <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='36' height='36' viewBox='0 0 24 24'><circle cx='12' cy='12' r='10' fill='%2300e6ff'/><rect x='7' y='7' width='10' height='10' rx='2' fill='%23001f2b'/></svg>" alt="" />
      <h1>Painel IA WinGo</h1>
    </div>

    <div class="box">
      <div class="sub">Próximo Sinal Automático</div>
      <div id="pred" class="big">Carregando...</div>
      <div id="conf" class="meta">Confiança IA: --%</div>
      <div id="next" class="meta">Próximo Período: --</div>
    </div>

    <div class="box">
      <div style="font-weight:700;margin-bottom:8px">Últimos Resultados (API)</div>
      <div id="lasts" class="row" style="flex-wrap:wrap;gap:8px;justify-content:flex-start"></div>
    </div>

    <div class="box">
      <div style="font-weight:700;margin-bottom:8px">Histórico de Sinais (recente → antigo)</div>
      <ul id="history" class="hist-list"></ul>
    </div>

    <div class="small">Atualizações automáticas: <span id="interval">5s</span> — Obs: se a API mudar, ajuste o script.</div>
    <div id="err" class="error" style="display:none">❌ Erro ao buscar dados da API.</div>
  </div>
</div>

<script>
const INTERVAL = {{interval}};
document.getElementById('interval').innerText = INTERVAL + 's';
async function fetchPredict(){
  try{
    const r = await fetch('/predict');
    if(!r.ok) throw new Error('network');
    const j = await r.json();
    if(j.error){
      showError(j.error);
      return;
    }
    hideError();
    // preencher UI
    document.getElementById('pred').innerText = j.prediction === 'G' ? 'Grande' : 'Pequeno';
    document.getElementById('conf').innerText = 'Confiança IA: ' + Math.round(j.confidence*100) + '%';
    document.getElementById('next').innerText = 'Próximo Período: ' + (j.next_period || '--');
    // últimos resultados (API)
    const lasts = document.getElementById('lasts');
    lasts.innerHTML = '';
    (j.last_results || []).slice(0, 20).forEach(it=>{
      const el = document.createElement('div');
      el.style.display='inline-block';
      el.style.marginRight='6px';
      el.innerHTML = it === 'G' ? "<div class='dotG'>G</div>" : "<div class='dotP'>P</div>";
      lasts.appendChild(el);
    });
    // histórico
    const hist = document.getElementById('history');
    hist.innerHTML = '';
    (j.history || []).forEach(item=>{
      const li = document.createElement('li');
      li.innerHTML = "<span>"+item.period+" → "+item.num+" (" + (item.gp==='G' ? 'Grande' : 'Pequeno') +")</span><span style='color:#9efea6'>"+item.ts+"</span>";
      hist.appendChild(li);
    });
  }catch(err){
    showError('Erro ao buscar dados da API.');
    console.error(err);
  }
}
function showError(m){
  const e = document.getElementById('err'); e.innerText = '❌ ' + m; e.style.display = 'block';
  document.getElementById('pred').innerText = 'Carregando...';
  document.getElementById('conf').innerText = 'Confiança IA: --%';
  document.getElementById('next').innerText = 'Próximo Período: --';
}
function hideError(){ document.getElementById('err').style.display='none'; }
fetchPredict();
setInterval(fetchPredict, INTERVAL*1000);
</script>
</body>
</html>
"""

def gp_from_number(n):
    """Classifica número 0-9 -> P ou G (Pequeno <=4, Grande >=5)"""
    try:
        val = int(n)
    except:
        return None
    return 'P' if val <= 4 else 'G'

def fetch_api_history():
    """Busca API externa e retorna lista de dicts (issueNumber, number, time, gp)."""
    try:
        params = {"pageIndex": 1, "pageSize": FETCH_COUNT}
        proxies = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None
        resp = requests.get(API_URL, params=params, timeout=8, proxies=proxies)
        if resp.status_code == 403:
            return {"error": "HTTP 403 ao acessar API"}
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", {}).get("list", []) if isinstance(data, dict) else []
        results = []
        for it in items:
            num = it.get("number") or it.get("num") or it.get("premium") or it.get("result") or ""
            gp = gp_from_number(num)
            period = it.get("issueNumber") or it.get("period") or ""
            results.append({"period": period, "number": num, "gp": gp})
        return {"items": results}
    except requests.exceptions.RequestException as e:
        return {"error": f"Erro de conexão: {str(e)}"}
    except ValueError:
        return {"error": "Resposta da API não é JSON válido"}
    except Exception as e:
        return {"error": f"Erro ao buscar resultados da API: {str(e)}"}

def simple_predict(last_gps):
    """
    Modelo simples:
    - Conta frequência G vs P nos últimos N
    - Se diferença >=2 usa maior como previsão
    - Caso empate, usa último resultado invertido (tenta reversão)
    - confidence = proporção do vencedor (0..1) com um mínimo
    """
    if not last_gps:
        return {"pred": None, "conf": 0.0}
    c = Counter(last_gps)
    g = c.get('G', 0)
    p = c.get('P', 0)
    total = g + p
    if total == 0:
        return {"pred": None, "conf": 0.0}
    if abs(g - p) >= 2:
        winner = 'G' if g > p else 'P'
        conf = max(0.2, (max(g,p) / total))
        return {"pred": winner, "conf": conf}
    # empate ou próximo -> apostar na reversão do último (mais conservador)
    last = last_gps[-1]
    pred = 'G' if last == 'P' else 'P'
    conf = 0.5  # confiança menor em caso de empate
    return {"pred": pred, "conf": conf}

@app.route("/")
def index():
    return render_template_string(INDEX_HTML, interval=UPDATE_INTERVAL)

@app.route("/predict")
def predict():
    # busca API
    api_res = fetch_api_history()
    if "error" in api_res:
        return jsonify({"error": api_res["error"]}), 500

    items = api_res.get("items", [])
    if not items:
        return jsonify({"error": "API retornou lista vazia"}), 500

    # transformar em lista G/P por ordem do mais recente primeiro (assumindo items vem do mais recente)
    # vamos organizar para último primeiro
    gps = []
    parsed = []
    for it in items:
        gp = it.get("gp")
        if gp:
            gps.append(gp)
        parsed.append({
            "period": it.get("period"),
            "num": it.get("number"),
            "gp": it.get("gp"),
        })

    # garantir ordem cronológica (recente -> antigo)
    # items provavelmente já vem recente->antigo; manter assim
    # atualiza history global (memória)
    ts = datetime.utcnow().strftime("%H:%M:%S")
    # adiciona parsed ao history
    for it in parsed:
        if it["gp"]:
            history.appendleft({
                "period": it["period"],
                "num": it["num"],
                "gp": it["gp"],
                "ts": ts
            })

    # prepare last_results para front (mostrar primeiros N)
    last_results = [it['gp'] for it in parsed if it['gp']][:FETCH_COUNT]

    # roda modelo com os últimos N gps (mais recentes primeiro)
    model_input = [it for it in last_results]  # ex: ['G','P','G',...]
    # inverter para predição (queremos ordem do mais antigo -> mais recente? nosso simple_predict usa recente no final)
    # mas já temos recente primeiro, vamos reordenar para antigo->recent:
    model_input = list(reversed(model_input))
    res = simple_predict(model_input)

    next_period = parsed[0]['period'] if parsed else None
    # compute display history (recente -> antigo) limited to 10
    disp_history = []
    for idx, h in enumerate(list(history)[:10]):
        disp_history.append({"period": h["period"], "num": h["num"], "gp": h["gp"], "ts": h["ts"]})

    return jsonify({
        "prediction": res["pred"],                 # 'G' ou 'P'
        "confidence": res["conf"],                # 0..1
        "next_period": next_period,
        "last_results": last_results,             # mais recentes da API
        "history": disp_history
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)    return None

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/dados")
def dados():
    try:
        data = get_api_data()
        if data:
            return jsonify(data)
        else:
            return jsonify({"error": "Não foi possível obter dados da API"}), 500
    except Exception as e:
        logging.error(f"Erro ao buscar API: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
