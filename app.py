from flask import Flask, render_template, jsonify
import requests
import logging
from datetime import datetime

app = Flask(__name__)

# Configuração do log
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# URL da API via proxy (evita bloqueio CORS no Render)
API_URL = "https://api.allorigins.win/raw?url=https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json"

# Função para buscar resultados
def buscar_resultados():
    try:
        logging.info("🔍 Buscando resultados da API via proxy...")
        resposta = requests.get(API_URL, timeout=10)
        resposta.raise_for_status()
        dados = resposta.json()
        logging.info("✅ Resultados recebidos com sucesso.")
        return dados
    except Exception as e:
        logging.error(f"Erro ao buscar API: {e}")
        return None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/dados")
def dados():
    resultados = buscar_resultados()
    if resultados:
        return jsonify(resultados)
    return jsonify({"erro": "Falha ao buscar dados da API"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)