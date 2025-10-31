# BOT SINAIS IA ALFA

Este repositório contém o bot Telegram "BOT SINAIS IA ALFA" pronto para deploy no Render.

Arquivos:
- bot_sinais_ia.py
- access_codes.json
- requirements.txt
- Procfile
- start.sh

Deploy rápido no Render:
1) Faça push do repositório no GitHub (nome: bot-sinais-ia).
2) No Render, crie um novo Web Service e conecte o repo.
3) Build command: pip install -r requirements.txt
4) Start command: bash start.sh
5) (Opcional) Defina TELEGRAM_TOKEN nas Environment Variables do Render.
6) Deploy.

Uso:
- Usuário envia /start e depois /redeem <CÓDIGO>.
- Código é consumido e usuário passa a receber previsões automáticas.
