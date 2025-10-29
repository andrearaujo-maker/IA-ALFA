from flask import Flask, jsonify, render_template
import requests
import random
import logging

app = Flask(name)

# 🔗 API do Wingo
API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json"

# 🌎 Lista de proxies gratuitos brasileiros (rotativos)
PROXIES_BR = [
    "http://177.93.45.156:999",
    "http://201.91.82.155:3128",
    "http://177.234.245.243:999",
    "http://170.81.78.32:8080",
    "http://187.49.191.61:999"
]

# 🚀 Função para buscar dados com fallback de proxy
def get_api_data():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    for attempt in range(3):  # tenta até 3 vezes
        proxy = random.choice(PROXIES_BR)
        try:
            response = requests.get(API_URL, headers=headers, proxies={"http": proxy, "https": proxy}, timeout=10)

            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"Erro HTTP {response.status_code} com proxy {proxy}")
        except Exception as e:
            logging.error(f"Tentativa {attempt+1} falhou com proxy {proxy}: {e}")
    return None

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

if name == "main":
    app.run(host="0.0.0.0", port=5000)
