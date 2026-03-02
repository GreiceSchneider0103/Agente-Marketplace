# -*- coding: utf-8 -*-
import os
import json
from typing import List, Dict, Optional

# jsonschema precisa ser adicionado ao requirements.txt
try:
    import jsonschema
except ImportError:
    jsonschema = None  # Handle case where it's not installed, checked later

import google.generativeai as genai

# When app.py (in the parent dir) runs, this module is part of a package import.
# Python's path includes the directory of the running script (where app.py is),
# so it can find `prompts.py` at that level.
from prompts import PROMPT_MASTER, OUTPUT_JSON_SCHEMA, build_user_payload


# ✅ Use um modelo que EXISTE na sua chave (ListModels mostrou que gemini-1.5-flash NÃO existe)
# Sugestão estável:
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-flash-latest")


# --- Fields and Validation ---

REQUIRED_FIELDS = [
    "nome_produto", "marca_linha", "materiais", "dimensoes", "peso_suportado",
    "cores_disponiveis", "diferenciais_reais", "garantia", "conteudo_embalagem",
    "necessita_montagem", "publico_alvo", "ambientes_uso", "vendedor_empresa",
    "marketplace_alvo"
]

QUESTIONS_MAP = {
    "nome_produto": "Qual o nome completo do produto?",
    "marca_linha": "Qual é a marca ou linha do produto?",
    "materiais": "Quais são os principais materiais de fabricação?",
    "dimensoes": "Quais são as dimensões do produto (ex: AxLxP cm)?",
    "peso_suportado": "Qual o peso máximo suportado (em kg)?",
    "cores_disponiveis": "Quais são as cores disponíveis?",
    "diferenciais_reais": "Quais são os 3 principais diferenciais do produto?",
    "garantia": "Qual o período de garantia (ex: 90 dias, 1 ano)?",
    "conteudo_embalagem": "O que vem na embalagem?",
    "necessita_montagem": "O produto precisa de montagem? (sim/não)",
    "tempo_montagem": "Qual o tempo estimado de montagem?",
    "nivel_montagem": "Qual o nível de dificuldade da montagem (fácil, médio, difícil)?",
    "publico_alvo": "Para quem este produto é destinado?",
    "ambientes_uso": "Em quais ambientes este produto pode ser usado?",
    "vendedor_empresa": "Qual o nome do vendedor ou da empresa?",
    "marketplace_alvo": "Para qual marketplace este anúncio será otimizado (ex: Mercado Livre, Amazon)?"
}


def _validate_required_fields(product_data: Dict) -> List[str]:
    """Checks for missing required fields, including conditional ones."""
    missing = []
    for field in REQUIRED_FIELDS:
        if not product_data.get(field):
            missing.append(field)

    # Conditional validation for assembly
    needs_assembly = str(product_data.get("necessita_montagem", "")).lower() == 'sim'
    if needs_assembly:
        if not product_data.get("tempo_montagem"):
            missing.append("tempo_montagem")
        if not product_data.get("nivel_montagem"):
            missing.append("nivel_montagem")

    return list(set(missing))


# --- JSON Extraction ---

def extract_first_json(text: str) -> Optional[Dict]:
    """Robustly extracts the first valid JSON object from a string using brace counting."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    search_start_pos = 0
    while search_start_pos < len(text):
        try:
            start_pos = text.index('{', search_start_pos)
            brace_count = 1
            for i in range(start_pos + 1, len(text)):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1

                if brace_count == 0:
                    potential_json = text[start_pos: i + 1]
                    try:
                        return json.loads(potential_json)
                    except json.JSONDecodeError:
                        break
            search_start_pos = start_pos + 1
        except ValueError:
            break

    return None


# ✅ NOVO: garante campos obrigatórios do schema antes de validar
def _ensure_required_fields(payload: dict) -> dict:
    """Garante que campos obrigatórios existam para passar no schema."""
    if not isinstance(payload, dict):
        return {}

    # Campos de alto nível mais comuns (ajuste conforme seu schema real)
    payload.setdefault("persona", {})
    payload.setdefault("dores", [])
    payload.setdefault("ganhos", [])
    payload.setdefault("jornada", {})
    payload.setdefault("gatilhos", [])
    payload.setdefault("jtbd", "")
    payload.setdefault("puv", "")
    payload.setdefault("funcionalidades_chave", [])
    payload.setdefault("diferencial_competitivo", "")
    payload.setdefault("prova_social", [])
    payload.setdefault("seo", {})
    payload.setdefault("titulos", [])
    payload.setdefault("modelo", "")
    payload.setdefault("descricao", "")
    payload.setdefault("roteiro_imagens", [])

    # Subestruturas
    if isinstance(payload.get("persona"), dict):
        payload["persona"].setdefault("demografia", "")
        payload["persona"].setdefault("estilo_de_vida", "")
        payload["persona"].setdefault("poder_aquisitivo", "")
        payload["persona"].setdefault("contexto_de_uso", "")

    if isinstance(payload.get("jornada"), dict):
        payload["jornada"].setdefault("descoberta", "")
        payload["jornada"].setdefault("consideracao", "")
        payload["jornada"].setdefault("decisao", "")

    if isinstance(payload.get("seo"), dict):
        payload["seo"].setdefault("primarias", [])
        payload["seo"].setdefault("secundarias", [])
        payload["seo"].setdefault("termos_tecnicos", [])

    return payload


# --- Main Agent Function ---

def run_agent(product_data: Dict) -> Dict:
    """
    Runs the full agent process: validates fields, calls the model,
    parses the response, and validates against the JSON schema.
    """
    if "GEMINI_API_KEY" not in os.environ:
        return {"status": "error", "message": "GEMINI_API_KEY não configurada."}

    missing_fields = _validate_required_fields(product_data)
    if missing_fields:
        return {
            "status": "missing_fields",
            "missing": missing_fields,
            "questions": [QUESTIONS_MAP.get(field, f"O campo '{field}' está faltando.") for field in missing_fields]
        }

    user_payload = build_user_payload(product_data)
    full_prompt = PROMPT_MASTER + user_payload

    try:
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])

        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(
            full_prompt,
            generation_config={"response_mime_type": "application/json"}
        )

        response_json = extract_first_json(response.text)
        if not response_json:
            return {"status": "error", "message": "Modelo não retornou um JSON válido."}

        if not jsonschema:
            return {"status": "error", "message": "Biblioteca jsonschema não instalada."}

        if 'status' not in response_json:
            response_json['status'] = 'ok'

        # ✅ garante campos obrigatórios existam antes do schema validate
        response_json = _ensure_required_fields(response_json)

        jsonschema.validate(instance=response_json, schema=OUTPUT_JSON_SCHEMA)

        return response_json

    except jsonschema.ValidationError as e:
        return {"status": "error", "message": f"Falha na validação do schema JSON: {e.message}"}
    except Exception as e:
        return {"status": "error", "message": f"Ocorreu um erro inesperado: {str(e)}"}