# -*- coding: utf-8 -*-
import os
import json
import traceback
from typing import List, Dict, Optional

# jsonschema precisa estar no requirements.txt
try:
    import jsonschema
except ImportError:
    jsonschema = None

import google.generativeai as genai

from prompts import PROMPT_MASTER, OUTPUT_JSON_SCHEMA, build_user_payload

# Use um modelo que exista (na sua lista do ListModels)
MODEL_NAME = os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash")

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
    missing = []
    for field in REQUIRED_FIELDS:
        if not product_data.get(field):
            missing.append(field)

    needs_assembly = str(product_data.get("necessita_montagem", "")).strip().lower() == "sim"
    if needs_assembly:
        if not product_data.get("tempo_montagem"):
            missing.append("tempo_montagem")
        if not product_data.get("nivel_montagem"):
            missing.append("nivel_montagem")

    return sorted(list(set(missing)))


def extract_first_json(text: str) -> Optional[Dict]:
    # tenta direto
    try:
        return json.loads(text)
    except Exception:
        pass

    # tenta por contagem de chaves
    search_start_pos = 0
    while search_start_pos < len(text):
        try:
            start_pos = text.index("{", search_start_pos)
            brace_count = 1
            for i in range(start_pos + 1, len(text)):
                if text[i] == "{":
                    brace_count += 1
                elif text[i] == "}":
                    brace_count -= 1
                if brace_count == 0:
                    candidate = text[start_pos : i + 1]
                    try:
                        return json.loads(candidate)
                    except Exception:
                        break
            search_start_pos = start_pos + 1
        except ValueError:
            break
    return None


def _pad_or_slice(lst, size, fill=""):
    lst = lst if isinstance(lst, list) else []
    lst = [str(x) for x in lst if x is not None]
    if len(lst) >= size:
        return lst[:size]
    return lst + [fill] * (size - len(lst))

def _normalize_analise_estrategica(payload: dict) -> dict:
    """
    Ajusta o retorno do modelo para bater com OUTPUT_JSON_SCHEMA.
    Resolve: dores/ganhos aninhados, jornada em dict, nomes diferentes (jtbd/puv/prova_social).
    """
    if not isinstance(payload, dict):
        return payload

    ae = payload.get("analise_estrategica")
    if not isinstance(ae, dict):
        return payload

    # 1) dores/ganhos podem vir em dores_e_ganhos
    deg = ae.get("dores_e_ganhos")
    if isinstance(deg, dict):
        if "dores" not in ae and isinstance(deg.get("dores"), list):
            ae["dores"] = deg.get("dores")
        if "ganhos" not in ae and isinstance(deg.get("ganhos"), list):
            ae["ganhos"] = deg.get("ganhos")

    # 2) jornada pode vir como dict (jornada_de_compra) mas o schema quer string (jornada_compra)
    if "jornada_compra" not in ae:
        jdc = ae.get("jornada_de_compra")
        if isinstance(jdc, dict):
            descoberta = str(jdc.get("descoberta", "")).strip()
            consideracao = str(jdc.get("consideracao", "")).strip()
            decisao = str(jdc.get("decisao", "")).strip()
            ae["jornada_compra"] = (
                f"Descoberta: {descoberta}\n"
                f"Consideração: {consideracao}\n"
                f"Decisão: {decisao}"
            ).strip()
        else:
            # fallback
            ae["jornada_compra"] = str(ae.get("jornada_compra", "")).strip()

    # 3) mapear nomes alternativos -> nomes do schema
    if "jtbd" not in ae and ae.get("job_to_be_done"):
        ae["jtbd"] = ae.get("job_to_be_done")

    if "puv" not in ae and ae.get("proposta_unica_de_valor"):
        ae["puv"] = ae.get("proposta_unica_de_valor")

    if "prova_social" not in ae and ae.get("prova_social_e_evidencias"):
        ae["prova_social"] = ae.get("prova_social_e_evidencias")

    # 4) garantir tipos e tamanhos conforme schema (min/max)
    ae["persona"] = str(ae.get("persona", "")).strip()

    ae["dores"] = _pad_or_slice(ae.get("dores"), 3, fill="Não informado.")
    ae["ganhos"] = _pad_or_slice(ae.get("ganhos"), 3, fill="Não informado.")

    ae["gatilhos_mentais"] = _pad_or_slice(ae.get("gatilhos_mentais"), 3, fill="Não informado.")

    # funcionalidades_chave: min 3, max 5
    fc = ae.get("funcionalidades_chave")
    fc = fc if isinstance(fc, list) else []
    fc = [str(x) for x in fc if x is not None]
    if len(fc) < 3:
        fc = fc + ["Não informado."] * (3 - len(fc))
    ae["funcionalidades_chave"] = fc[:5]

    ae["jtbd"] = str(ae.get("jtbd", "")).strip()
    ae["puv"] = str(ae.get("puv", "")).strip()
    ae["diferencial_competitivo"] = str(ae.get("diferencial_competitivo", "")).strip()
    ae["prova_social"] = str(ae.get("prova_social", "")).strip()

    payload["analise_estrategica"] = ae
    return payload

def _ensure_required_fields(payload: dict) -> dict:
    """
    Garante que campos obrigatórios do JSON existam para evitar quebra no schema,
    mesmo que o modelo omita alguma parte.
    OBS: não mexe em analise_estrategica (isso é função do _normalize_analise_estrategica).
    """
    if not isinstance(payload, dict):
        return {}

    # top-level comuns do seu schema
    payload.setdefault("seo", {})
    payload.setdefault("titulos", [])
    payload.setdefault("modelo", "")
    payload.setdefault("descricao", "")
    payload.setdefault("roteiro_imagens", [])

    # se seu schema tiver outras chaves de topo, adicione aqui
    if isinstance(payload.get("seo"), dict):
        payload["seo"].setdefault("primarias", [])
        payload["seo"].setdefault("secundarias", [])
        payload["seo"].setdefault("termos_tecnicos", [])

    # garante analise_estrategica existir (o normalize faz o resto)
    payload.setdefault("analise_estrategica", {})

    return payload

def run_agent(product_data: Dict) -> Dict:
    if "GEMINI_API_KEY" not in os.environ:
        return {"status": "error", "message": "GEMINI_API_KEY não configurada."}

    missing_fields = _validate_required_fields(product_data)
    if missing_fields:
        return {
            "status": "missing_fields",
            "missing": missing_fields,
            "questions": [QUESTIONS_MAP.get(f, f"O campo '{f}' está faltando.") for f in missing_fields],
        }

    user_payload = build_user_payload(product_data)
    full_prompt = PROMPT_MASTER + user_payload

    try:
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])

        model = genai.GenerativeModel(MODEL_NAME)

        # Forma simples e compatível
        response = model.generate_content(
            full_prompt,
            generation_config={"response_mime_type": "application/json"},
        )

        raw_text = getattr(response, "text", "") or ""
        response_json = extract_first_json(raw_text)

        if not response_json:
            # loga um pedaço do retorno pra debugar no Render
            print("MODEL_RAW_TEXT_START")
            print(raw_text[:2000])
            print("MODEL_RAW_TEXT_END")
            return {"status": "error", "message": "Modelo não retornou um JSON válido."}

        # Completa campos antes do schema
        response_json = _ensure_required_fields(response_json)
        response_json = _normalize_analise_estrategica(response_json)

        if "status" not in response_json:
            response_json["status"] = "ok"

        if not jsonschema:
            return {"status": "error", "message": "Biblioteca jsonschema não instalada."}

        jsonschema.validate(instance=response_json, schema=OUTPUT_JSON_SCHEMA)

        return response_json

    except Exception as e:
        # stack trace no log do Render
        print("RUN_AGENT_EXCEPTION")
        traceback.print_exc()
        return {"status": "error", "message": f"Ocorreu um erro inesperado: {str(e)}"}