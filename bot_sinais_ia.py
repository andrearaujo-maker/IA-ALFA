import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, executor, types

# =====================
# CONFIGURAÇÕES DO BOT
# =====================
TOKEN = "8126373920:AAEdRJ48gNqflX-M3kcihod4xegf314iup0"  # <-- Substitua pelo seu token do Telegram
ARQUIVO_DB = "usuarios.db"

# =====================
# CONFIGURAR LOG
# =====================
logging.basicConfig(level=logging.INFO)

# =====================
# INICIALIZAÇÃO DO BOT
# =====================
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# =====================
# CONFIGURAR BANCO DE DADOS
# =====================
def criar_tabelas():
    conn = sqlite3.connect(ARQUIVO_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    ativo INTEGER
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS codigos (
                    codigo TEXT PRIMARY KEY,
                    usado INTEGER
                )''')
    conn.commit()
    conn.close()

# gerar códigos
def gerar_codigos():
    codigos = [f"IA-ALFA-{i:03d}" for i in range(1, 21)]
    conn = sqlite3.connect(ARQUIVO_DB)
    c = conn.cursor()
    for codigo in codigos:
        c.execute("INSERT OR IGNORE INTO codigos (codigo, usado) VALUES (?, ?)", (codigo, 0))
    conn.commit()
    conn.close()

criar_tabelas()
gerar_codigos()

# =====================
# COMANDO /start
# =====================
@dp.message_handler(commands=["start"])
async def start_cmd(message: types.Message):
    await message.answer(
        "👋 Olá! Envie seu código de acesso com:\n\n"
        "`/redeem <CÓDIGO>`\n\nExemplo:\n`/redeem IA-ALFA-001`",
        parse_mode="Markdown"
    )

# =====================
# COMANDO /redeem
# =====================
@dp.message_handler(commands=["redeem"])
async def redeem_cmd(message: types.Message):
    try:
        codigo = message.text.split(" ")[1].strip().upper()
    except IndexError:
        await message.answer("⚠️ Use o formato: `/redeem IA-ALFA-001`", parse_mode="Markdown")
        return

    conn = sqlite3.connect(ARQUIVO_DB)
    c = conn.cursor()
    c.execute("SELECT usado FROM codigos WHERE codigo = ?", (codigo,))
    resultado = c.fetchone()

    if not resultado:
        await message.answer("❌ Código inválido.")
    elif resultado[0] == 1:
        await message.answer("⚠️ Este código já foi usado.")
    else:
        c.execute("UPDATE codigos SET usado = 1 WHERE codigo = ?", (codigo,))
        c.execute("INSERT OR REPLACE INTO usuarios (user_id, username, ativo) VALUES (?, ?, ?)",
                  (message.from_user.id, message.from_user.username, 1))
        conn.commit()
        await message.answer("✅ Código aceito! Você será incluído na lista para receber sinais automáticos.")
    conn.close()

# =====================
# FUNÇÃO PARA ENVIAR SINAIS AUTOMÁTICOS
# =====================
async def enviar_sinais():
    while True:
        await asyncio.sleep(30)  # intervalo entre sinais (30 segundos de exemplo)
        conn = sqlite3.connect(ARQUIVO_DB)
        c = conn.cursor()
        c.execute("SELECT user_id FROM usuarios WHERE ativo = 1")
        usuarios = c.fetchall()
        conn.close()

        sinal = "🎯 Sinal Gerado!\n👉 Entrada: 🔵 Pequeno\n💰 Estratégia: Martingale (1, 2, 6, 18, 54, 162)\n🚀 Boa sorte!"

        for (user_id,) in usuarios:
            try:
                await bot.send_message(user_id, sinal)
            except Exception as e:
                print(f"Erro ao enviar sinal para {user_id}: {e}")

# =====================
# EXECUÇÃO PRINCIPAL
# =====================
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(enviar_sinais())
    executor.start_polling(dp, skip_updates=True)
