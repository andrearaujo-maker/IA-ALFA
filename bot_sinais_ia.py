import telebot
import requests
import json
import time
import threading

TOKEN = "8126373920:AAEdRJ48gNqflX-M3kcihod4xegf314iup0"
bot = telebot.TeleBot(TOKEN)

CODIGOS_FILE = "codigos.txt"
API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json"

usuarios_autorizados = set()

def carregar_codigos():
    with open(CODIGOS_FILE, "r") as f:
        return [c.strip() for c in f.readlines() if c.strip()]

def remover_codigo(codigo):
    with open(CODIGOS_FILE, "r") as f:
        linhas = f.readlines()
    with open(CODIGOS_FILE, "w") as f:
        for linha in linhas:
            if linha.strip() != codigo:
                f.write(linha)

def obter_resultados():
    try:
        r = requests.get(API_URL, timeout=10)
        data = r.json()["data"]["list"]
        return data
    except Exception as e:
        print("Erro ao obter dados:", e)
        return []

def prever_sinal(dados):
    if not dados: return "Aguardando dados..."
    numeros = [int(i["number"]) for i in dados[:10]]
    media = sum(numeros)/len(numeros)
    return "🔵 Pequeno" if media < 5 else "🟠 Grande"

def loop_envio(chat_id):
    while chat_id in usuarios_autorizados:
        dados = obter_resultados()
        if dados:
            ultimo = dados[0]
            previsao = prever_sinal(dados)
            prox_periodo = str(int(ultimo["issueNumber"]) + 1)
            msg = f"🤖 *IA 2025 - Previsão Automática*"

"📊" Último Resultado: {ultimo["number"]}
"🧠" Próximo Período: `{prox_periodo}`
"🎯" Próximo Sinal: {previsao}"
            bot.send_message(chat_id, msg, parse_mode="Markdown")
        time.sleep(5)

@bot.message_handler(commands=["start"])
def start(msg):
    bot.reply_to(msg, "🤖 Olá! Envie seu *código de acesso* para liberar os sinais da IA 2025.", parse_mode="Markdown")

@bot.message_handler(func=lambda m: True)
def handle(msg):
    chat_id = msg.chat.id
    codigo = msg.text.strip()
    codigos = carregar_codigos()
    if codigo in codigos:
        usuarios_autorizados.add(chat_id)
        remover_codigo(codigo)
        bot.send_message(chat_id, "✅ Acesso liberado! Você receberá os sinais automaticamente a cada 5 segundos.")
        threading.Thread(target=loop_envio, args=(chat_id,), daemon=True).start()
    elif chat_id in usuarios_autorizados:
        bot.send_message(chat_id, "⏳ Você já está recebendo os sinais automáticos.")
    else:
        bot.send_message(chat_id, "❌ Código inválido ou já utilizado.")

print("🤖 Bot IA 2025 iniciado...")
bot.infinity_polling()
