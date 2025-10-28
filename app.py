from flask import Flask, render_template, jsonify
import requests, logging

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/dados")
def dados():
    try:
        url = "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json"
        response = requests.get(url, timeout=5)

        if response.status_code != 200:
            logging.error(f"Erro HTTP {response.status_code} ao acessar API")
            return jsonify({"erro": f"Erro HTTP {response.status_code}"}), 500

        # Evita erro se resposta vier vazia
        if not response.text.strip():
            logging.error("Resposta vazia da API.")
            return jsonify({"erro": "Resposta vazia da API"}), 500

        try:
            data = response.json()
        except ValueError:
            logging.error(f"Erro ao converter resposta em JSON: {response.text[:200]}")
            return jsonify({"erro": "Falha ao ler dados da API"}), 500

        return jsonify(data)

    except Exception as e:
        logging.error(f"Erro ao buscar API: {e}")
        return jsonify({"erro": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
