import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "chave-secreta-alfa")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///users.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8126373920:AAEdRJ48gNqflX-M3kcihod4xegf314iup0")
