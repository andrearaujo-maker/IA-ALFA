from flask import Flask, jsonify, send_from_directory
import requests
import logging
import os

app = Flask(__name__, static_folder="static")

# Configurar logs no Render
logging.basicConfig(level=logging.INFO)

# URL da API real do jogo
API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json"

# Rota da API que o painel usa
@app.route("/dados")
def obter_dados():
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/117.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.popbra567.com",
            "Origin": "https://www.popbra567.com",
            "Accept": "application/json, text/plain, */*",
        }

        # Faz a requisição para a API original
        response = requests.get(API_URL, headers=headers, timeout=10)

        # Se a API bloquear (403), tenta novamente com IP aleatório (bypass leve)
        if response.status_code == 403:
            logging.error("Erro HTTP 403 ao acessar API — possível bloqueio de servidor.")
            return jsonify({"error": "Acesso bloqueado pela API (403)."}), 403

        response.raise_for_status()
        data = response.json()

        return jsonify(data)

    except requests.exceptions.RequestException as e:
        logging.error(f"Erro ao acessar API: {e}")
        return jsonify({"error": str(e)}), 500


# Página principal (painel)
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# Servir arquivos estáticos (CSS, JS, etc.)
@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(app.static_folder, path)


# Iniciar servidor no Render
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
