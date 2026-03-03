# -*- coding: utf-8 -*-
import os
import io
import re
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file

from marketplace_specialist.agent import run_agent
from marketplace_specialist.docx_builder import build_docx

# PDF parsing (opcional)
try:
    import pdfplumber
except Exception:
    pdfplumber = None


app = Flask(__name__)

# --- Security / Sessions ---
IS_PRODUCTION = "RENDER" in os.environ

# Usa FLASK_SECRET_KEY (como no patch do Gemini). Mantém fallback só no dev.
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.environ.get("SECRET_KEY")
if not app.secret_key:
    if not IS_PRODUCTION:
        app.secret_key = "unsafe-dev-key-for-local-testing-only"
    else:
        raise ValueError("FLASK_SECRET_KEY é obrigatória em produção.")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=IS_PRODUCTION,
    MAX_CONTENT_LENGTH=20 * 1024 * 1024,  # 20MB
)

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


# --- Missing fields contract (front-end expects these keys) ---
FIELDS_REQUIRED = [
    "nome_produto",
    "marca_linha",
    "materiais",
    "dimensoes",
    "peso_suportado",
    "conteudo_embalagem",
    "necessita_montagem",
    "empresa",
    "marketplace_alvo",
]

QUESTIONS_MAP_FALLBACK = {
    "nome_produto": "Qual é o nome do produto?",
    "marca_linha": "Qual é a marca ou linha do produto?",
    "materiais": "Do que o produto é feito (estrutura, pés, estofamento)?",
    "dimensoes": "Quais são as dimensões (L x A x P)?",
    "peso_suportado": "Quanto peso o produto suporta (kg)?",
    "conteudo_embalagem": "O que vem na embalagem?",
    "necessita_montagem": "Precisa de montagem? (sim/não)",
    "tempo_montagem": "Se sim, qual o tempo estimado para montar?",
    "nivel_montagem": "E qual o nível de dificuldade (fácil, médio, difícil)?",
    "empresa": "Qual é o nome da sua empresa (vendedor)?",
    "marketplace_alvo": "Para qual marketplace este anúncio se destina?",
}


def _normalize_yes_no(v):
    t = str(v or "").strip().lower()
    if t in ("s", "sim", "yes", "y"):
        return "sim"
    if t in ("n", "nao", "não", "no"):
        return "nao"
    return v


def _extract_structured_data_from_text(text: str) -> dict:
    """
    Extração leve (regex) para preencher campos se o usuário deixou em branco.
    Mantém simples e seguro.
    """
    if not text:
        return {}

    data = {}

    # tenta capturar "Dimensões: 60 x 110 x 50 cm" (variações)
    m = re.search(
        r"(dimens(?:o|õ)es|medidas)\s*[:\-]?\s*([\d.,]+\s*[xX]\s*[\d.,]+\s*[xX]\s*[\d.,]+\s*(?:cm|mm|m))",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        data["dimensoes"] = m.group(2).strip()

    m = re.search(
        r"(peso\s*suportado|suporta\s*at(?:e|é))\s*[:\-]?\s*([\d.,]+\s*kg)",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        data["peso_suportado"] = m.group(2).strip()

    m = re.search(
        r"(conte(?:u|ú)do\s*(?:da|de)\s*embalagem|itens?\s*inclusos?)\s*[:\-]?\s*(.+)",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        # pega a primeira linha
        data["conteudo_embalagem"] = m.group(2).strip().split("\n")[0].strip()

    return data


def _process_uploads(files):
    """
    Retorna:
      - upload_text_context: texto extraído/descrição de uploads p/ contexto do agente
      - extracted_data: dados estruturados (regex)
    """
    upload_text_context = ""
    extracted_data = {}

    pdf = files.get("file_pdf")
    if pdf and getattr(pdf, "filename", ""):
        if pdfplumber is None:
            upload_text_context += "PDF anexado, mas pdfplumber não está disponível no servidor.\n"
        else:
            try:
                with pdfplumber.open(pdf) as p:
                    full_text = "\n".join(
                        page.extract_text() for page in p.pages if page.extract_text()
                    )
                if full_text:
                    upload_text_context += f"DADOS EXTRAÍDOS DO PDF:\n---\n{full_text[:4000]}\n---\n"
                    extracted_data.update(_extract_structured_data_from_text(full_text))
            except Exception:
                upload_text_context += "PDF anexado, mas falhou ao ser processado.\n"

    photo = files.get("file_photo")
    if photo and getattr(photo, "filename", ""):
        upload_text_context += "Uma foto do produto foi anexada para referência visual.\n"

    return upload_text_context.strip(), extracted_data


def _merge_data(extracted: dict, manual: dict) -> dict:
    """
    Manual tem prioridade.
    """
    merged = dict(extracted or {})
    for k, v in (manual or {}).items():
        if v is None:
            continue
        merged[k] = v
    merged["necessita_montagem"] = _normalize_yes_no(merged.get("necessita_montagem"))
    return merged


def _validate_missing_fields(data: dict):
    missing = [f for f in FIELDS_REQUIRED if not str(data.get(f, "")).strip()]

    # Condicional de montagem
    if str(data.get("necessita_montagem", "")).strip().lower() == "sim":
        if not str(data.get("tempo_montagem", "")).strip():
            missing.append("tempo_montagem")
        if not str(data.get("nivel_montagem", "")).strip():
            missing.append("nivel_montagem")

    if missing:
        return {
            "status": "missing_fields",
            "message": "Campos obrigatórios estão faltando.",
            "missing": missing,
            "questions": {f: QUESTIONS_MAP_FALLBACK.get(f, f) for f in missing},
        }

    return None


def _handle_request(req):
    """
    Pipeline obrigatório:
      UPLOAD -> EXTRACT -> MERGE -> VALIDATE -> RUN_AGENT
    """
    upload_text, extracted_data = _process_uploads(req.files)

    # Front envia multipart/form-data (FormData)
    if req.content_type and req.content_type.startswith("multipart/form-data"):
        manual_data = req.form.to_dict()
    else:
        manual_data = req.get_json(silent=True) or {}

    merged = _merge_data(extracted_data, manual_data)

    # Validar antes de rodar o agente (pra só perguntar o que falta)
    miss = _validate_missing_fields(merged)
    if miss:
        return None, miss

    # Passa o contexto do upload sem quebrar contratos existentes
    # (se o agente ignorar, ok)
    if upload_text:
        merged["_upload_context"] = upload_text

    result = run_agent(merged)

    # Se o agente devolver missing_fields, respeita o contrato do front
    if isinstance(result, dict) and result.get("status") == "missing_fields":
        # Normaliza chaves para o que o front espera
        missing = result.get("missing") or result.get("missing_fields") or []
        questions = result.get("questions") or result.get("questions_by_field") or {}
        return None, {
            "status": "missing_fields",
            "message": result.get("message") or "Campos obrigatórios estão faltando.",
            "missing": missing,
            "questions": questions,
        }

    return result, None


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if not ADMIN_EMAIL or not ADMIN_PASSWORD:
            return render_template(
                "login.html",
                error="Credenciais de administrador não configuradas no servidor.",
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
    result, error = _handle_request(request)

    # Contrato: missing_fields SEMPRE 200
    if error:
        status_code = 200 if error.get("status") == "missing_fields" else 500
        return jsonify(error), status_code

    if not isinstance(result, dict):
        return jsonify({"status": "error", "message": "Resposta inválida do agente."}), 500

    # Se o agente retornar erro, mantém 500
    if result.get("status") == "error":
        return jsonify(result), 500

    return jsonify(result), 200


@app.post("/generate-docx")
@login_required
def generate_docx():
    result, error = _handle_request(request)

    # Contrato: missing_fields SEMPRE 200 (frontend trata isso)
    if error:
        status_code = 200 if error.get("status") == "missing_fields" else 500
        return jsonify(error), status_code

    if not isinstance(result, dict) or result.get("status") != "ok":
        return jsonify(result or {"status": "error", "message": "Falha ao gerar conteúdo."}), 500

    # Para build_docx você usava: build_docx(result, product_data)
    # Agora product_data é a fusão final (inclui extraídos + manuais)
    # Vamos reconstruir o "product_data" do mesmo jeito do _handle_request:
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        manual_data = request.form.to_dict()
    else:
        manual_data = request.get_json(silent=True) or {}
    _, extracted_data = _process_uploads(request.files)
    product_data = _merge_data(extracted_data, manual_data)

    docx_bytes = build_docx(result, product_data)

    filename = "anuncio_completo.docx"
    return send_file(
        io.BytesIO(docx_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=filename,
    )


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() in ("true", "1", "t")
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)