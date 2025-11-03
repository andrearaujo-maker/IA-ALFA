import telebot
import requests
import json
import random
import time
import threading
from datetime import datetime

# =========================================
# CONFIGURAÇÕES DO BOT
# =========================================
TOKEN = "8126373920:AAEdRJ48gNqflX-M3kcihod4xegf314iup0"
bot = telebot.TeleBot(TOKEN)

API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json"

# Controle de acesso via arquivo externo
CODIGOS_ATIVOS = "codigos_ativos.txt"
CODIGOS_PERMITIDOS = "codigos.txt"

# =========================================
# FUNÇÕES DE SUPORTE
# =========================================
def carregar_codigos_ativos():
    try:
        with open(CODIGOS_ATIVOS, "r") as f:
            return [linha.strip() for linha in f.readlines()]
    except FileNotFoundError:
        return []

def adicionar_codigo_ativo(user_id):
    ativos = carregar_codigos_ativos()
    if str(user_id) not in ativos:
        with open(CODIGOS_ATIVOS, "a") as f:
            f.write(f"{user_id}\n")

def validar_codigo(codigo):
    try:
        with open(CODIGOS_PERMITIDOS, "r") as f:
            codigos = [linha.strip() for linha in f.readlines()]
        if codigo in codigos:
            # remove código após uso
            with open(CODIGOS_PERMITIDOS, "w") as f:
                for c in codigos:
                    if c != codigo:
                        f.write(c + "\n")
            return True
    except FileNotFoundError:
        return False
    return False

# =========================================
# SISTEMA DE PREVISÃO IA SIMPLIFICADO
# =========================================
def gerar_previsao():
    numero = random.randint(0, 9)
    sinal = "🔴 GRANDE" if numero >= 5 else "🟢 PEQUENO"
    return numero, sinal

# =========================================
# CAPTURA RESULTADOS DA POPBRA
# =========================================
def obter_ultimo_resultado():
    try:
        resposta = requests.get(API_URL)
        dados = resposta.json()
        ultimo = dados["data"][0]
        return int(ultimo["Number"])
    except Exception:
        return None

# =========================================
# ENVIO AUTOMÁTICO DE SINAIS
# =========================================
def enviar_sinal():
    numero, sinal = gerar_previsao()
    mensagem = f"""
🎯 *Sinal IA POPBRA*
🔢 Número previsto: {numero}
👉 Entrada: {sinal}
📈 Estratégia: Martingale (1, 2, 6, 18, 54, 162)
⏱️ Use /green se ganhou | /red se perdeu
🚀 Boa sorte!
"""
    ativos = carregar_codigos_ativos()
    for user_id in ativos:
        try:
            bot.send_message(user_id, mensagem, parse_mode="Markdown")
        except Exception:
            pass

def start_all():
    while True:
        enviar_sinal()
        numero = random.randint(0, 9)  # ✅ corrigido aqui
        print(f"Sinal IA enviado: {numero}")
        time.sleep(60)  # Envia um novo sinal a cada 1 minuto

# =========================================
# COMANDOS DO BOT
# =========================================
@bot.message_handler(commands=["start"])
def start(msg):
    user_id = msg.chat.id
    ativos = carregar_codigos_ativos()
    if str(user_id) in ativos:
        bot.reply_to(msg, "✅ Código aceito! Você está ativo e receberá sinais automáticos.")
    else:
        bot.reply_to(msg, "🔐 Envie seu código de acesso para ativar o bot.")

@bot.message_handler(func=lambda m: True)
def verificar_codigo(msg):
    codigo = msg.text.strip()
    if validar_codigo(codigo):
        adicionar_codigo_ativo(msg.chat.id)
        bot.reply_to(msg, "✅ Código aceito! Você está ativo e receberá sinais automáticos.")
    else:
        bot.reply_to(msg, "❌ Código inválido ou já utilizado.")

# =========================================
# EXECUÇÃO PRINCIPAL
# =========================================
if __name__ == "__main__":
    threading.Thread(target=start_all, daemon=True).start()
    print("🤖 BOT IA POPBRA iniciado com sucesso!")
    bot.polling(non_stop=True)
