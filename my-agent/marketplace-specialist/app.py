# -*- coding: utf-8 -*-
import os
import io
import re
import logging
from functools import wraps

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file

# Mantém seus módulos do projeto
from marketplace_specialist.agent import run_agent
from marketplace_specialist.docx_builder import build_docx

# PDF (opcional, mas recomendado)
try:
    import pdfplumber
except Exception:  # pragma: no cover
    pdfplumber = None

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# --- Configuration ---
app.secret_key = os.environ.get("SECRET_KEY", "a-very-insecure-development-secret-key")
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25MB

# --- Authentication ---
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

# Campos obrigatórios (espelhado do seu fluxo)
REQUIRED_FIELDS = [
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

QUESTIONS = {
    "nome_produto": "Qual é o nome do produto?",
    "marca_linha": "Qual é a marca ou linha do produto?",
    "materiais": "Quais são os materiais principais? (estrutura/pés/estofamento)",
    "dimensoes": "Quais são as dimensões (L x A x P)?",
    "peso_suportado": "Qual é o peso máximo suportado?",
    "conteudo_embalagem": "O que vem na embalagem?",
    "necessita_montagem": "Precisa de montagem? (sim/não)",
    "tempo_montagem": "Qual o tempo médio de montagem?",
    "nivel_montagem": "Qual o nível da montagem? (fácil/médio/difícil)",
    "empresa": "Qual é a empresa/vendedor?",
    "marketplace_alvo": "Em qual canal/marketplace será o anúncio?",
}


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_email" not in session:
            if request.path in ("/generate", "/generate-docx"):
                return jsonify({"status": "error", "message": "Não autenticado."}), 401
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


@app.route("/")
@login_required
def home():
    return render_template("index.html")


@app.get("/healthz")
def healthz():
    return "ok", 200


def _normalize_yes_no(v: str) -> str:
    t = str(v or "").strip().lower()
    if t in ("s", "sim", "yes", "y"):
        return "sim"
    if t in ("n", "nao", "não", "no"):
        return "não"
    return str(v or "").strip()


def _extract_pdf_text(file_storage) -> str:
    if not pdfplumber:
        app.logger.warning("pdfplumber não está instalado; pulando extração de PDF.")
        return ""
    try:
        # file_storage é werkzeug FileStorage
        with pdfplumber.open(file_storage.stream) as pdf:
            parts = []
            for page in pdf.pages:
                txt = page.extract_text() or ""
                if txt.strip():
                    parts.append(txt)
        return "\n".join(parts).strip()
    except Exception as e:
        app.logger.exception("Falha ao ler PDF: %s", e)
        return ""


def _pick_first(patterns, text):
    for p in patterns:
        m = re.search(p, text, flags=re.IGNORECASE | re.MULTILINE)
        if m:
            return (m.group(1) or "").strip()
    return ""


def _extract_fields_from_text(text: str) -> dict:
    """
    Extração simples por regex.
    (Não precisa ser perfeita; a meta é reduzir ao máximo as perguntas.)
    """
    if not text:
        return {}

    clean = re.sub(r"[ \t]+", " ", text)
    out = {}

    # Nome
    out["nome_produto"] = _pick_first(
        [
            r"(?:Produto|Nome do produto|Nome)\s*[:\-]\s*(.+)",
        ],
        clean,
    )

    # Marca/Linha
    out["marca_linha"] = _pick_first(
        [
            r"(?:Marca|Linha|Marca\/Linha)\s*[:\-]\s*(.+)",
            r"(?:Fabricante)\s*[:\-]\s*(.+)",
        ],
        clean,
    )

    # Materiais
    out["materiais"] = _pick_first(
        [
            r"(?:Materiais?|Composição|Estrutura)\s*[:\-]\s*(.+)",
        ],
        clean,
    )

    # Dimensões (muitos PDFs trazem "L x A x P" ou "CxLxA")
    out["dimensoes"] = _pick_first(
        [
            r"(?:Dimens(?:ões|oes)|Medidas)\s*[:\-]\s*([0-9., ]+\s*[xX]\s*[0-9., ]+\s*[xX]\s*[0-9., ]+\s*(?:cm|mm|m)?)",
            r"(?:Largura|L)\s*[:\-]\s*([0-9., ]+)\s*(?:cm|mm|m).{0,80}?(?:Altura|A)\s*[:\-]\s*([0-9., ]+)\s*(?:cm|mm|m).{0,80}?(?:Profundidade|P)\s*[:\-]\s*([0-9., ]+)\s*(?:cm|mm|m)",
        ],
        clean,
    )
    # Se pegou L/A/P separado (3 grupos), monta
    m_lap = re.search(
        r"(?:Largura|L)\s*[:\-]\s*([0-9., ]+)\s*(cm|mm|m).{0,80}?(?:Altura|A)\s*[:\-]\s*([0-9., ]+)\s*(cm|mm|m).{0,80}?(?:Profundidade|P)\s*[:\-]\s*([0-9., ]+)\s*(cm|mm|m)",
        clean,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if m_lap and not out.get("dimensoes"):
        out["dimensoes"] = f"{m_lap.group(1)}x{m_lap.group(3)}x{m_lap.group(5)} {m_lap.group(2)}"

    # Peso suportado
    out["peso_suportado"] = _pick_first(
        [
            r"(?:Peso suportado|Peso máximo|Peso maximo)\s*[:\-]\s*([0-9., ]+\s*kg)",
            r"(?:Suporta)\s*[:\-]?\s*([0-9., ]+\s*kg)",
        ],
        clean,
    )

    # Conteúdo da embalagem
    out["conteudo_embalagem"] = _pick_first(
        [
            r"(?:Conteúdo da embalagem|Conteudo da embalagem|Itens inclusos|Conteúdo)\s*[:\-]\s*(.+)",
        ],
        clean,
    )

    # Montagem
    montagem = _pick_first(
        [
            r"(?:Montagem|Requer montagem|Necessita montagem)\s*[:\-]\s*(sim|não|nao)",
        ],
        clean,
    )
    if montagem:
        out["necessita_montagem"] = _normalize_yes_no(montagem)

    # Tempo / nível (se existir no PDF)
    out["tempo_montagem"] = _pick_first(
        [
            r"(?:Tempo de montagem|Tempo estimado|Tempo médio)\s*[:\-]\s*(.+)",
        ],
        clean,
    )
    out["nivel_montagem"] = _pick_first(
        [
            r"(?:Nível de montagem|Nivel de montagem|Dificuldade)\s*[:\-]\s*(fácil|facil|médio|medio|difícil|dificil)",
        ],
        clean,
    )

    # Limpa valores muito longos (linha inteira)
    for k, v in list(out.items()):
        if isinstance(v, str):
            v = v.strip()
            if "\n" in v:
                v = v.split("\n")[0].strip()
            if len(v) > 200:
                v = v[:200].strip()
            out[k] = v

    # remove vazios
    return {k: v for k, v in out.items() if v}


def _get_payload_and_files():
    """
    Suporta:
    - multipart/form-data (FormData do script.js)
    - application/json
    """
    # multipart
    if request.form and len(request.form) > 0:
        data = request.form.to_dict(flat=True)
        files = request.files
        return data, files

    # json
    j = request.get_json(silent=True)
    if isinstance(j, dict):
        return j, {}

    return {}, {}


def _validate_minimum(data: dict):
    missing = []
    for f in REQUIRED_FIELDS:
        if not data.get(f) or str(data.get(f)).strip() == "":
            missing.append(f)

    # regra: se montagem = sim, tempo/nivel viram obrigatórios
    if _normalize_yes_no(data.get("necessita_montagem", "")) == "sim":
        if not data.get("tempo_montagem"):
            missing.append("tempo_montagem")
        if not data.get("nivel_montagem"):
            missing.append("nivel_montagem")

    if missing:
        return {
            "status": "missing_fields",
            "missing": missing,
            "questions": {k: QUESTIONS.get(k, k) for k in missing},
        }
    return None


def _merge_extracted_with_manual(extracted: dict, manual: dict) -> dict:
    # manual sempre vence (o que o usuário digitou é a verdade)
    merged = {}
    merged.update(extracted or {})
    merged.update({k: v for k, v in (manual or {}).items() if v is not None})
    # normalizações pontuais
    if "necessita_montagem" in merged:
        merged["necessita_montagem"] = _normalize_yes_no(merged["necessita_montagem"])
    return merged


@app.route("/generate", methods=["POST"])
@login_required
def generate():
    manual_data, files = _get_payload_and_files()

    # tenta extrair do PDF
    extracted = {}
    pdf_file = files.get("file_pdf") if files else None
    if pdf_file and getattr(pdf_file, "filename", ""):
        text = _extract_pdf_text(pdf_file)
        extracted = _extract_fields_from_text(text)
        app.logger.info("PDF extraído: campos=%s", list(extracted.keys()))

    merged = _merge_extracted_with_manual(extracted, manual_data)

    # valida mínimo
    error = _validate_minimum(merged)
    if error:
        return jsonify(error), 200

    # roda agente
    result = run_agent(merged)

    if not isinstance(result, dict):
        return jsonify({"status": "error", "message": "Resposta inválida do agente."}), 500

    if result.get("status") == "error":
        return jsonify(result), 500

    # garante status ok
    result.setdefault("status", "ok")
    return jsonify(result), 200


@app.post("/generate-docx")
@login_required
def generate_docx():
    manual_data, files = _get_payload_and_files()

    extracted = {}
    pdf_file = files.get("file_pdf") if files else None
    if pdf_file and getattr(pdf_file, "filename", ""):
        text = _extract_pdf_text(pdf_file)
        extracted = _extract_fields_from_text(text)

    merged = _merge_extracted_with_manual(extracted, manual_data)

    error = _validate_minimum(merged)
    if error:
        return jsonify(error), 200

    result = run_agent(merged)
    if not isinstance(result, dict) or result.get("status") != "ok":
        return jsonify(result if isinstance(result, dict) else {"status": "error", "message": "Falha ao gerar."}), 400

    docx_bytes = build_docx(result, merged)

    filename = f"anuncio_{re.sub(r'[^a-zA-Z0-9]+','_', (merged.get('nome_produto','anuncio'))).lower()}.docx"
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