from telegram import Bot
from config import Config

bot = Bot(token=Config.TELEGRAM_TOKEN)

def enviar_sinal(chat_id, sinal):
    mensagem = (
        f"🎯 Sinal Gerado!\n"
        f"👉 Entrada: {sinal}\n"
        f"💰 Estratégia: Martingale (1, 2, 6, 18, 54, 162)\n"
        f"🚀 Boa sorte!"
    )
    bot.send_message(chat_id=chat_id, text=mensagem)
