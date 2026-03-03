
import os
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session

# This import assumes the structure where app.py is in 'my-agent/marketplace-specialist'
# and the agent code is in the 'marketplace_specialist' sub-package.
from marketplace_specialist.agent import run_agent

app = Flask(__name__)

# --- Configuration ---
# SECRET_KEY is mandatory for session management.
# In production, this MUST be a long, random, and secret string set as an environment variable.
app.secret_key = os.environ.get("SECRET_KEY", "a-very-insecure-development-secret-key")

# --- Authentication ---
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            # For API endpoints, return a JSON error
            if request.path == '/generate':
                return jsonify({"status": "error", "message": "Não autenticado."}), 401
            # For web pages, redirect to the login page
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not ADMIN_EMAIL or not ADMIN_PASSWORD:
             return render_template('login.html', error="Credenciais de administrador não configuradas no servidor.")

        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session['user_email'] = email
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error="Email ou senha inválidos.")
    
    # For GET request, just show the login page
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- Main Application Routes ---

@app.route('/')
@login_required
def home():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
@login_required
def generate():
    product_data = request.get_json(silent=True)
    if not isinstance(product_data, dict):
        return jsonify({"status": "error", "message": "Payload inválido. Um objeto JSON era esperado."}), 400

    result = run_agent(product_data)
    
    # If the agent signals an internal error, return a 500 status code
    if result.get("status") == "error":
        return jsonify(result), 500
        
    return jsonify(result)

if __name__ == '__main__':
    # Debug mode should be disabled in production. It is enabled here if FLASK_DEBUG=1 or True
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    
    # For Cloud Run compatibility, the port is retrieved from the PORT environment variable.
    port = int(os.environ.get('PORT', 8080))
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)

# app.py (exemplo)
from flask import Flask, request, send_file, jsonify
import io
from marketplace_specialist.agent import run_agent
from marketplace_specialist.docx_builder import build_docx

app = Flask(__name__)

@app.post("/generate-docx")
def generate_docx():
    product_data = request.get_json(force=True) or {}

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