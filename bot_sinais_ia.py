import requests
import time
import random
import json
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ============= CONFIGURAÇÕES =====================
TOKEN = "8126373920:AAEdRJ48gNqflX-M3kcihod4xegf314iup0"
API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json"
CODIGOS_ARQUIVO = "codigos.txt"
USUARIOS_ARQUIVO = "usuarios_autorizados.json"
INTERVALO_ATUALIZACAO = 5  # segundos
# ==================================================

# ---------- Funções auxiliares ----------
def carregar_codigos():
    try:
        with open(CODIGOS_ARQUIVO, "r") as f:
            return [linha.strip() for linha in f.readlines() if linha.strip()]
    except FileNotFoundError:
        return []

def salvar_codigos(codigos):
    with open(CODIGOS_ARQUIVO, "w") as f:
        for c in codigos:
            f.write(c + "\n")

def carregar_usuarios():
    try:
        with open(USUARIOS_ARQUIVO, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def salvar_usuarios(usuarios):
    with open(USUARIOS_ARQUIVO, "w") as f:
        json.dump(usuarios, f)

def obter_resultados():
    try:
        response = requests.get(API_URL, timeout=5)
        data = response.json()
        if "data" in data and "list" in data["data"]:
            return data["data"]["list"][:10]  # últimos 10 resultados
    except Exception as e:
        print("Erro API:", e)
    return []

# ---------- IA preditiva simples ----------
def prever_proximo(resultados):
    if not resultados:
        return random.choice(["Grande 🟠", "Pequeno 🔵"])

    grandes = sum(1 for r in resultados if int(r["number"]) >= 5)
    pequenos = len(resultados) - grandes
    tendencia = "Grande 🟠" if grandes > pequenos else "Pequeno 🔵"

    # leve variação para simular aprendizado
    if random.random() < 0.15:
        tendencia = "Grande 🟠" if tendencia == "Pequeno 🔵" else "Pequeno 🔵"

    return tendencia

# ---------- Comandos Telegram ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    usuarios = carregar_usuarios()

    if user_id in usuarios:
        await update.message.reply_text("✅ Acesso liberado!\nUse /sinal para ver o último sinal IA.")
        return

    await update.message.reply_text("🔐 Envie seu código de acesso (ex: IA-2025):")

async def handle_codigo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    codigo = update.message.text.strip()
    user_id = update.effective_user.id

    codigos = carregar_codigos()
    usuarios = carregar_usuarios()

    if codigo in codigos:
        usuarios.append(user_id)
        codigos.remove(codigo)
        salvar_codigos(codigos)
        salvar_usuarios(usuarios)
        await update.message.reply_text("✅ Acesso concedido!\nUse /sinal para receber previsões automáticas.")
    else:
        await update.message.reply_text("❌ Código inválido ou já usado.")

async def sinal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    usuarios = carregar_usuarios()

    if user_id not in usuarios:
        await update.message.reply_text("🚫 Você não tem acesso. Envie um código válido.")
        return

    resultados = obter_resultados()
    proximo_sinal = prever_proximo(resultados)
    ultimo_periodo = resultados[0]["issueNumber"] if resultados else "Desconhecido"

    await update.message.reply_text(
        f"🎯 *Previsão IA*\n\n"
        f"📅 Último Período: {ultimo_periodo}\n"
        f"📊 Próximo Sinal: {proximo_sinal}",
        parse_mode="Markdown"
    )

# ---------- Atualização automática ----------
async def loop_sinais(bot: Bot):
    ultimo_periodo = ""
    while True:
        resultados = obter_resultados()
        if resultados:
            periodo = resultados[0]["issueNumber"]
            if periodo != ultimo_periodo:
                ultimo_periodo = periodo
                sinal = prever_proximo(resultados)
                usuarios = carregar_usuarios()
                for uid in usuarios:
                    try:
                        await bot.send_message(
                            chat_id=uid,
                            text=f"🎯 *Novo Sinal IA*\n📅 Período: {periodo}\n📊 Entrada: {sinal}",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        print(f"Erro envio {uid}:", e)
        time.sleep(INTERVALO_ATUALIZACAO)

# ---------- Inicialização ----------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sinal", sinal))
    app.add_handler(CommandHandler("codigo", handle_codigo))

    bot = Bot(TOKEN)
    app.create_task(loop_sinais(bot))

    print("🤖 Bot IA iniciado com sucesso!")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
