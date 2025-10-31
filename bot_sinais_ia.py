import json
import asyncio
import random
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "8126373920:AAEdRJ48gNqflX-M3kcihod4xegf314iup0"

USUARIOS_FILE = "usuarios_autorizados.json"
CODIGOS_FILE = "codigos_acesso.json"


# ---------- Funções de Arquivo ----------
def carregar_json(caminho):
    try:
        with open(caminho, "r") as f:
            return json.load(f)
    except:
        return {}


def salvar_json(caminho, dados):
    with open(caminho, "w") as f:
        json.dump(dados, f, indent=4)


# ---------- Sistema de Códigos ----------
def gerar_codigo():
    letras = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "IA-" + "".join(random.choices(letras, k=6))


def criar_codigos(qtd=5):
    codigos = carregar_json(CODIGOS_FILE)
    for _ in range(qtd):
        codigo = gerar_codigo()
        codigos[codigo] = {"usado": False}
    salvar_json(CODIGOS_FILE, codigos)


# ---------- IA de Previsão ----------
def previsao_ia():
    opcoes = ["🔴 Grande", "🟢 Pequeno"]
    return random.choice(opcoes)


# ---------- Comandos ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    usuarios = carregar_json(USUARIOS_FILE)

    if user_id in usuarios:
        await update.message.reply_text("✅ Acesso já autorizado!\nAguarde o próximo sinal...")
    else:
        await update.message.reply_text("🔒 Envie seu código de acesso com o comando:\n\n`/acesso SEUCODIGO`")


async def acesso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    usuarios = carregar_json(USUARIOS_FILE)
    codigos = carregar_json(CODIGOS_FILE)

    if len(context.args) == 0:
        await update.message.reply_text("⚠️ Use: `/acesso SEUCODIGO`")
        return

    codigo = context.args[0].strip().upper()

    if codigo in codigos and not codigos[codigo]["usado"]:
        codigos[codigo]["usado"] = True
        usuarios[user_id] = {"codigo": codigo, "data": datetime.now().strftime("%d/%m/%Y %H:%M:%S")}
        salvar_json(CODIGOS_FILE, codigos)
        salvar_json(USUARIOS_FILE, usuarios)
        await update.message.reply_text("✅ Acesso autorizado! Você receberá os sinais automaticamente.")
    else:
        await update.message.reply_text("❌ Código inválido ou já usado.")


# ---------- Envio Automático de Sinais ----------
async def enviar_sinais(app):
    while True:
        usuarios = carregar_json(USUARIOS_FILE)
        if not usuarios:
            await asyncio.sleep(5)
            continue

        sinal = previsao_ia()
        periodo = datetime.now().strftime("%H:%M:%S")

        for user_id in usuarios:
            try:
                await app.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"🎯 *Sinal Gerado pela IA - 2025*\n"
                        f"⏱️ Período: `{periodo}`\n"
                        f"👉 Entrada: {sinal}\n\n"
                        f"💡 Use gerenciamento adequado!"
                    ),
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"Erro ao enviar para {user_id}: {e}")

        await asyncio.sleep(5)  # atualiza a cada 5 segundos


# ---------- Inicialização ----------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("acesso", acesso))

    print("🤖 Bot IA 2025 iniciado com sucesso!")
    asyncio.create_task(enviar_sinais(app))
    await app.run_polling()


if __name__ == "__main__":
    criar_codigos(10)  # cria 10 códigos novos se não existirem
    asyncio.run(main())
