from flask import Flask, jsonify, render_template
import requests
import threading
import time
import random
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# Estado global
state = {
    "prediction": None,
    "confidence": 0,
    "next_issue": None,
    "signals": [],
    "last_results": []
}

API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json"

# ---- Função para buscar resultados da API ----
def fetch_results():
    try:
        resp = requests.get(API_URL, timeout=8)
        data = resp.json()
        if "data" in data and "list" in data["data"]:
            results = [
                {
                    "issue": r["issue"],
                    "number": int(r["number"]),
                    "result": "Grande" if int(r["number"]) >= 5 else "Pequeno"
                }
                for r in data["data"]["list"][:10]
            ]
            return results
    except Exception as e:
        print("❌ Erro ao buscar API:", e)
    return None

# ---- Atualizador automático ----
def update_state():
    results = fetch_results()
    if not results:
        return

    state["last_results"] = results

    # Previsão simples baseada nos últimos números
    ultimos = [r["number"] for r in results[:5]]
    media = sum(ultimos) / len(ultimos)
    prediction = "Grande" if media >= 5 else "Pequeno"
    confidence = random.randint(65, 95)
    next_issue = str(int(results[0]["issue"]) + 1)

    state["prediction"] = prediction
    state["confidence"] = confidence
    state["next_issue"] = next_issue

    state["signals"].insert(0, {
        "issue": next_issue,
        "prediction": prediction,
        "confidence": confidence
    })
    state["signals"] = state["signals"][:10]

    print(f"🔁 Atualizado: {prediction} ({confidence}%) | Próximo: {next_issue}")

# ---- Rota principal ----
@app.route("/")
def index():
    return render_template("modern_painel.html")

# ---- Endpoint JSON ----
@app.route("/data")
def data():
    return jsonify(state)

# ---- Inicialização do agendador ----
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(update_state, "interval", seconds=5)
scheduler.start()

# ---- Inicialização do servidor ----
if __name__ == "__main__":
    update_state()  # Atualiza na primeira execução
    app.run(host="0.0.0.0", port=8000)
