from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from utils.signals import gerar_sinal
from utils.telegram_bot import enviar_sinal
from utils.database import db, Usuario
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

with app.app_context():
    db.create_all()

# Função automática para enviar sinais a todos os usuários ativos
def enviar_sinais_automaticos():
    with app.app_context():
        usuarios = Usuario.query.filter_by(ativo=True).all()
        sinal = gerar_sinal()
        for u in usuarios:
            if u.chat_id:
                enviar_sinal(u.chat_id, sinal)

scheduler = BackgroundScheduler()
scheduler.add_job(enviar_sinais_automaticos, "interval", minutes=5)
scheduler.start()

@app.route("/")
def home():
    if "user" in session:
        return redirect("/painel")
    return redirect("/login")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]
        user = Usuario.query.filter_by(email=email, senha=senha).first()
        if user:
            session["user"] = user.email
            return redirect("/painel")
    return render_template("login.html")

@app.route("/painel")
def painel():
    if "user" not in session:
        return redirect("/login")
    return render_template("painel.html")

@app.route("/registrar", methods=["GET", "POST"])
def registrar():
    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        senha = request.form["senha"]
        user = Usuario(nome=nome, email=email, senha=senha)
        db.session.add(user)
        db.session.commit()
        return redirect("/login")
    return render_template("register.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
