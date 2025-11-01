import asyncio
import sqlite3
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# ==============================
# 🔧 CONFIGURAÇÕES PRINCIPAIS
# ==============================
TOKEN = "8126373920:AAEdRJ48gNqflX-M3kcihod4xegf314iup0"
VALID_CODES = ["IA-ALFA-001", "IA-ALFA-002", "IA-ALFA-003", "IA-ALFA-004", "IA-ALFA-005"]

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# ==============================
# 📦 BANCO DE DADOS (SQLite)
# ==============================
conn = sqlite3.connect("usuarios.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE,
    nome TEXT,
    codigo TEXT,
    data_registro TEXT
)
""")
conn.commit()

# ==============================
# 🧭 FUNÇÕES AUXILIARES
# ==============================
def usuario_existe(user_id):
    cursor.execute("SELECT 1 FROM usuarios WHERE user_id = ?", (user_id,))
    return cursor.fetchone() is not None

def registrar_usuario(user_id, nome, codigo):
    data = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT OR IGNORE INTO usuarios (user_id, nome, codigo, data_registro) VALUES (?, ?, ?, ?)",
                   (user_id, nome, codigo, data))
    conn.commit()

def listar_usuarios():
    cursor.execute("SELECT user_id FROM usuarios")
    return [row[0] for row in cursor.fetchall()]

# ==============================
# 🤖 COMANDOS DO BOT
# ==============================
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    texto = (
        "👋 Olá! Envie seu código de acesso com:\n\n"
        "`/redeem <CÓDIGO>`\n"
        "Exemplo: `/redeem IA-ALFA-001`\n\n"
        "Após aceitar, você começará a receber sinais automáticos."
    )
    await message.answer(texto, parse_mode="Markdown")

@dp.message_handler(commands=['redeem'])
async def redeem_cmd(message: types.Message):
    try:
        codigo = message.text.split()[1].strip().upper()
    except IndexError:
        await message.reply("⚠️ Use o formato correto: `/redeem IA-ALFA-001`", parse_mode="Markdown")
        return

    if codigo in VALID_CODES:
        if not usuario_existe(message.from_user.id):
            registrar_usuario(message.from_user.id, message.from_user.first_name, codigo)
            await message.reply("✅ Código aceito! Você será incluído na lista para receber sinais automáticos.")
        else:
            await message.reply("ℹ️ Você já está registrado e receberá sinais normalmente.")
    else:
        await message.reply("❌ Código inválido. Peça ao administrador um código válido.")

# ==============================
# 🚀 ENVIO AUTOMÁTICO DE SINAIS
# ==============================
async def enviar_sinais():
    while True:
        usuarios = listar_usuarios()
        if not usuarios:
            logging.info("Nenhum usuário registrado para receber sinais.")
            await asyncio.sleep(30)
            continue

        # Exemplo de sinal
        agora = datetime.now().strftime("%H:%M:%S")
        sinal = (
            f"🎯 *Sinal Gerado automaticamente pelo BOT SINAIS IA ALFA*\n"
            f"🕒 {agora}\n\n"
            f"👉 Entrada: 🟠 Grande\n"
            f"💰 Estratégia: Martingale (1, 2, 6, 18, 54, 162)\n"
            f"🚀 Boa sorte!"
        )

        for user_id in usuarios:
            try:
                await bot.send_message(chat_id=user_id, text=sinal, parse_mode="Markdown")
            except Exception as e:
                logging.warning(f"Erro ao enviar para {user_id}: {e}")

        await asyncio.sleep(60)  # ⏱️ intervalo entre sinais (1 min)

# ==============================
# ⚙️ INÍCIO DO BOT
# ==============================
async def on_startup(_):
    asyncio.create_task(enviar_sinais())
    logging.info("BOT SINAIS IA ALFA iniciado com sucesso.")

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
