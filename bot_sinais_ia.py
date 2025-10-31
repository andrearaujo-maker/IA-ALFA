import telebot
import json
import time
import threading
import random
import os

# ==============================
# CONFIGURAÇÕES DO BOT
# ==============================
TOKEN = os.getenv("BOT_TOKEN", "8126373920:AAEdRJ48gNqflX-M3kcihod4xegf314iup0")
bot = telebot.TeleBot(TOKEN, skip_pending=True)

# ==============================
# ARQUIVOS DE DADOS
# ==============================
CODIGOS_FILE = "codigos_validos.json"
USUARIOS_FILE = "usuarios_ativos.json"

# ==============================
# CRIA OS ARQUIVOS SE NÃO EXISTIREM
# ==============================
if not os.path.exists(CODIGOS_FILE):
    codigos = [f"IA-ALFA-{i:03d}" for i in range(1, 11)]
    json.dump(codigos, open(CODIGOS_FILE, "w"))

if not os.path.exists(USUARIOS_FILE):
    json.dump([], open(USUARIOS_FILE, "w"))


# ==============================
# FUNÇÕES DE SUPORTE
# ==============================
def carregar_codigos():
    with open(CODIGOS_FILE, "r") as f:
        return json.load(f)

def salvar_codigos(codigos):
    with open(CODIGOS_FILE, "w") as f:
        json.dump(codigos, f)

def carregar_usuarios():
    with open(USUARIOS_FILE, "r") as f:
        return json.load(f)

def salvar_usuarios(usuarios):
    with open(USUARIOS_FILE, "w") as f:
        json.dump(usuarios, f)


# ==============================
# COMANDOS DO BOT
# ==============================
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(
        message,
        "👋 Olá! Envie seu código de acesso com:\n"
        "`/redeem <CÓDIGO>`\n\n"
        "Exemplo: `/redeem IA-ALFA-001`",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['redeem'])
def redeem(message):
    try:
        codigo = message.text.split(" ")[1].strip().upper()
    except:
        bot.reply_to(message, "❌ Use o formato correto: `/redeem IA-ALFA-001`", parse_mode="Markdown")
        return

    codigos = carregar_codigos()
    usuarios = carregar_usuarios()
    user_id = message.chat.id

    if codigo not in codigos:
        bot.reply_to(message, "❌ Código inválido ou já utilizado.")
        return

    if user_id in usuarios:
        bot.reply_to(message, "⚠️ Você já está na lista de acesso.")
        return

    usuarios.append(user_id)
    salvar_usuarios(usuarios)
    codigos.remove(codigo)
    salvar_codigos(codigos)

    bot.reply_to(
        message,
        "✅ Código aceito! Você será incluído na lista para receber sinais automáticos."
    )


# ==============================
# ENVIO AUTOMÁTICO DE SINAIS
# ==============================
def gerar_sinal():
    opcoes = ["🔴 Grande", "🔵 Pequeno"]
    escolha = random.choice(opcoes)
    gerenciamento = "Martingale (1, 2, 6, 18, 54, 162)"
    return f"🎯 Sinal gerado!\n👉 Entrada: {escolha}\n💰 Gerenciamento: {gerenciamento}\n⏱️ Estratégia: IA-2025\n🚀 Boa sorte!"

def enviar_sinal_para_todos():
    usuarios = carregar_usuarios()
    if not usuarios:
        print("Nenhum usuário ativo para receber sinais.")
        return
    sinal = gerar_sinal()
    print(f"Enviando sinal: {sinal}")
    for user_id in usuarios:
        try:
            bot.send_message(user_id, sinal)
        except Exception as e:
            print(f"Erro ao enviar sinal para {user_id}: {e}")

def loop_sinais():
    while True:
        enviar_sinal_para_todos()
        time.sleep(180)  # a cada 3 minutos


# ==============================
# INICIALIZAÇÃO DO BOT
# ==============================
def iniciar_bot():
    print("🚀 Iniciando BOT SINAIS IA ALFA...")
    threading.Thread(target=loop_sinais, daemon=True).start()
    bot.infinity_polling(timeout=60, long_polling_timeout=60)

if __name__ == "__main__":
    iniciar_bot()
