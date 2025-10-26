from flask import Flask, render_template_string, jsonify
import requests
import threading
import time
import random

app = Flask(__name__)

# =======================
# ⚙️ CONFIGURAÇÕES
# =======================
API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json"
UPDATE_INTERVAL = 5  # segundos
MAX_HISTORY = 10

# =======================
# 📊 DADOS DA IA E RESULTADOS
# =======================
history_data = []
current_prediction = {"signal": "🔵 Pequeno", "period": "----", "confidence": 0.50}


# =======================
# 🤖 FUNÇÃO DE ANÁLISE / IA
# =======================
def analyze_pattern(data):
    """
    IA adaptativa simples baseada em frequência recente e alternância
    """
    if not data:
        return "🔵 Pequeno", 0.5

    grandes = sum(1 for n in data if int(n["number"]) >= 5)
    pequenos = len(data) - grandes
    total = len(data)

    conf = abs(grandes - pequenos) / total
    if grandes > pequenos:
        return "🟠 Grande", 0.6 + conf / 2
    elif pequenos > grandes:
        return "🔵 Pequeno", 0.6 + conf / 2
    else:
        # alternância aleatória para empates
        return random.choice([("🟠 Grande", 0.55), ("🔵 Pequeno", 0.55)])


# =======================
# 🔁 ATUALIZADOR AUTOMÁTICO
# =======================
def update_results():
    global history_data, current_prediction
    while True:
        try:
            resp = requests.get(API_URL, timeout=5)
            json_data = resp.json()
            new_data = json_data["data"]["list"][:MAX_HISTORY]

            if new_data != history_data:
                history_data = new_data
                last_issue = int(history_data[0]["issueNumber"])
                signal, conf = analyze_pattern(history_data)
                next_period = str(last_issue + 1)

                current_prediction = {
                    "signal": signal,
                    "period": next_period,
                    "confidence": round(conf * 100, 1)
                }

        except Exception as e:
            print("Erro ao atualizar:", e)
        time.sleep(UPDATE_INTERVAL)


# =======================
# 🖥️ INTERFACE HTML (painel)
# =======================
HTML_PAGE = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Painel IA WinGo</title>
<style>
  body {
    background: radial-gradient(circle at top, #020024, #090979, #00d4ff);
    font-family: 'Segoe UI', sans-serif;
    color: #fff;
    text-align: center;
    margin: 0; padding: 0;
  }
  h1 {
    font-size: 2.2em;
    margin-top: 20px;
    text-shadow: 0 0 12px cyan;
  }
  .card {
    background: rgba(0,0,0,0.4);
    border-radius: 20px;
    padding: 20px;
    margin: 20px auto;
    width: 90%;
    max-width: 400px;
    box-shadow: 0 0 15px #00ffff55;
  }
  .signal {
    font-size: 2.5em;
    font-weight: bold;
    margin: 10px 0;
  }
  .confidence {
    font-size: 1em;
    color: #00ffff;
  }
  .period {
    font-size: 1.1em;
    margin-top: 10px;
  }
  .history {
    margin-top: 20px;
    font-size: 0.9em;
    line-height: 1.6em;
    background: rgba(255,255,255,0.05);
    border-radius: 10px;
    padding: 10px;
  }
</style>
<script>
  async function refreshData() {
    const res = await fetch('/data');
    const data = await res.json();
    document.getElementById('signal').textContent = data.signal;
    document.getElementById('period').textContent = "Próximo Período: " + data.period;
    document.getElementById('confidence').textContent = "Confiança IA: " + data.confidence + "%";

    let histHTML = "";
    data.history.forEach((h, i) => {
        const tipo = parseInt(h.number) >= 5 ? "🟠 Grande" : "🔵 Pequeno";
        histHTML += `<div>${i+1}. ${h.issueNumber} → ${h.number} (${tipo})</div>`;
    });
    document.getElementById('history').innerHTML = histHTML;
  }
  setInterval(refreshData, 5000);
  window.onload = refreshData;
</script>
</head>
<body>
  <h1>🤖 Painel IA WinGo</h1>
  <div class="card">
    <div id="signal" class="signal">Carregando...</div>
    <div id="confidence" class="confidence">Confiança IA: --%</div>
    <div id="period" class="period">Próximo Período: ----</div>
  </div>

  <div class="card">
    <h3>📈 Histórico de Sinais (recente → antigo)</h3>
    <div id="history" class="history">Carregando...</div>
  </div>
</body>
</html>
"""

# =======================
# 🌐 ROTAS
# =======================
@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/data')
def get_data():
    return jsonify({
        "signal": current_prediction["signal"],
        "period": current_prediction["period"],
        "confidence": current_prediction["confidence"],
        "history": history_data
    })


# =======================
# ▶️ EXECUÇÃO
# =======================
if __name__ == '__main__':
    threading.Thread(target=update_results, daemon=True).start()
    app.run(host='0.0.0.0', port=8000)
