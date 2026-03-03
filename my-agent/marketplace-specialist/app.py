# -*- coding: utf-8 -*-
import os
import io
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file

from marketplace_specialist.agent import run_agent
from marketplace_specialist.docx_builder import build_docx

app = Flask(__name__)

# --- Configuration ---
app.secret_key = os.environ.get("SECRET_KEY", "a-very-insecure-development-secret-key")

# --- Authentication ---
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_email" not in session:
            # API endpoints
            if request.path in ("/generate", "/generate-docx"):
                return jsonify({"status": "error", "message": "Não autenticado."}), 401
            # Web pages
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if not ADMIN_EMAIL or not ADMIN_PASSWORD:
            return render_template(
                "login.html",
                error="Credenciais de administrador não configuradas no servidor."
            )

        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session["user_email"] = email
            return redirect(url_for("home"))

        return render_template("login.html", error="Email ou senha inválidos.")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --- Main Application Routes ---

@app.route("/")
@login_required
def home():
    return render_template("index.html")


@app.get("/healthz")
def healthz():
    return "ok", 200


@app.route("/generate", methods=["POST"])
@login_required
def generate():
    product_data = request.get_json(silent=True)
    if not isinstance(product_data, dict):
        return jsonify({"status": "error", "message": "Payload inválido. Um objeto JSON era esperado."}), 400

    result = run_agent(product_data)

    if result.get("status") == "error":
        return jsonify(result), 500

    return jsonify(result)


@app.post("/generate-docx")
@login_required
def generate_docx():
    product_data = request.get_json(silent=True) or {}
    if not isinstance(product_data, dict):
        return jsonify({"status": "error", "message": "Payload inválido. Um objeto JSON era esperado."}), 400

    result = run_agent(product_data)
    if result.get("status") != "ok":
        return jsonify(result), 400

    docx_bytes = build_docx(result, product_data)

    filename = "anuncio_completo.docx"
    return send_file(
        io.BytesIO(docx_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=filename
    )


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() in ("true", "1", "t")
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)