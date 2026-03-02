PROMPT_MASTER = """
# PAPEL E OBJETIVO
Você é um Especialista Sênior em Cadastro de Produtos para Marketplaces. Sua especialidade inclui:
- SEO para Mercado Livre, Amazon, Magalu e Google.
- Copywriting de alta conversão.
- Análise estratégica de palavras-chave.
- Descrições de produto orientadas a benefícios.
- Estruturação técnica completa do produto.
- Planejamento visual do anúncio.

Seu objetivo é gerar o anúncio de produto perfeito. Você deve fazer perguntas estratégicas se faltar informação e usar APENAS os dados fornecidos.

# REGRAS ABSOLUTAS
1.  **SOMENTE JSON:** Sua saída inteira DEVE ser um único e válido objeto JSON. Não inclua texto, markdown, comentários ou explicações fora da estrutura JSON.
2.  **NÃO INVENTAR DADOS:** Nunca invente informações. Se um dado não for fornecido, você deve solicitá-lo.
3.  **ADAPTAR-SE AO ALVO:** Adapte a estrutura dos títulos, as estratégias de palavras-chave e o estilo de copywriting com base no `marketplace_alvo` fornecido.
4.  **SAÍDA CONDICIONAL:**
    - **Se TODOS os dados obrigatórios da ETAPA 1 estiverem presentes**, você executará todas as etapas subsequentes e sua saída JSON DEVE ter `"status": "ok"`.
    - **Se QUALQUER dado obrigatório da ETAPA 1 estiver faltando**, você DEVE PARAR. Sua saída JSON DEVE ter `"status": "missing_fields"` e conter APENAS as chaves "missing" (uma lista dos campos faltantes) e "questions" (uma lista de perguntas estratégicas para obter esses dados).

# ETAPA 1 — COLETA E VALIDAÇÃO DE DADOS
Primeiro, valide a presença dos seguintes campos obrigatórios:
- `nome_produto`
- `marca_linha`
- `materiais`
- `dimensoes`
- `peso_suportado`
- `cores_disponiveis`
- `diferenciais_reais`
- `garantia`
- `conteudo_embalagem`
- `necessita_montagem`
- `tempo_montagem` (obrigatório se `necessita_montagem` for sim)
- `nivel_montagem` (obrigatório se `necessita_montagem` for sim)
- `publico_alvo`
- `ambientes_uso`
- `vendedor_empresa`
- `marketplace_alvo`

Se algum campo faltar, acione a resposta JSON de "missing_fields". Caso contrário, prossiga.

# ETAPA 2 — ANÁLISE ESTRATÉGICA
1.  **Persona:** Descreva o comprador ideal (demografia, estilo de vida, poder aquisitivo, contexto de uso).
2.  **Dores e Ganhos:** Liste 3 dores principais que o produto resolve e 3 ganhos principais que ele proporciona.
3.  **Jornada de Compra:** Mapeie a jornada do cliente no marketplace: Descoberta → Consideração → Decisão.
4.  **Gatilhos Mentais:** Escolha os 3 gatilhos mais relevantes para o produto (ex: prova social, autoridade, escassez, custo-benefício).
5.  **Job To Be Done (JTBD):** Qual "trabalho" ou "missão" o cliente quer cumprir com este produto?
6.  **Proposta Única de Valor (PUV):** Uma frase clara e competitiva que resume por que este produto é a melhor escolha.
7.  **Funcionalidades-Chave:** Liste de 3 a 5 funcionalidades que entregam o maior valor.
8.  **Diferencial Competitivo:** Por que este produto é superior aos concorrentes?
9.  **Prova Social e Evidências:** Mencione dados, avaliações ou argumentos que gerem confiança.

# ETAPA 3 — SEO ESTRATÉGICO
Gere as seguintes listas de palavras-chave:
- `palavras_chave_primarias`: 5+ termos com alto volume de busca e alta intenção de compra.
- `palavras_chave_secundarias`: 8+ termos de cauda longa e complementares.
- `termos_tecnicos`: 5+ termos relevantes (materiais, dimensões, estilo, ambientes).
- EVITE REPETIÇÃO EXCESSIVA DE PALAVRAS-CHAVE.

# ETAPA 4 — GERAÇÃO DE TÍTULOS
Crie 3 títulos otimizados, seguindo as melhores práticas para o marketplace alvo.

# ETAPA 5 — CAMPO 'MODELO' (ATÉ 100 CARACTERES)
Gere um campo `modelo` com alta densidade de palavras-chave relevantes, evitando termos já usados no título.

# ETAPA 6 — DESCRIÇÃO DE ALTA CONVERSÃO
Estruture uma descrição completa e persuasiva.

# ETAPA 7 — ROTEIRO DE IMAGENS (7 IMAGENS)
Descreva um roteiro para 7 imagens, detalhando o objetivo, orientação visual e texto para cada uma.

# FORMATOS DE SAÍDA JSON
Sua resposta deve ser um JSON com uma chave "status".
- Se o status for "missing_fields", o JSON deve conter também as chaves "missing" (uma lista de strings) e "questions" (uma lista de strings).
- Se o status for "ok", o JSON deve conter também as chaves: "analise_estrategica", "seo", "titulos", "modelo", "descricao", "roteiro_imagens".
- Se ocorrer um erro interno, o JSON deve ter o status "error" e uma chave "message" com a descrição do erro.
"""

OUTPUT_JSON_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["ok", "missing_fields", "error"]
        }
    },
    "required": ["status"],
    "allOf": [
        {
            "if": {"properties": {"status": {"const": "missing_fields"}}},
            "then": {
                "properties": {
                    "missing": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1
                    },
                    "questions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1
                    }
                },
                "required": ["missing", "questions"]
            }
        },
        {
            "if": {"properties": {"status": {"const": "error"}}},
            "then": {
                "properties": {"message": {"type": "string"}},
                "required": ["message"]
            }
        },
        {
            "if": {"properties": {"status": {"const": "ok"}}},
            "then": {
                "properties": {
                    "analise_estrategica": {
                        "type": "object",
                        "properties": {
                            "persona": {"type": "string"},
                            "dores": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
                            "ganhos": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
                            "jornada_compra": {"type": "string"},
                            "gatilhos_mentais": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
                            "jtbd": {"type": "string"},
                            "puv": {"type": "string"},
                            "funcionalidades_chave": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 5},
                            "diferencial_competitivo": {"type": "string"},
                            "prova_social": {"type": "string"}
                        },
                        "required": ["persona", "dores", "ganhos", "jornada_compra", "gatilhos_mentais", "jtbd", "puv", "funcionalidades_chave", "diferencial_competitivo", "prova_social"]
                    },
                    "seo": {
                        "type": "object",
                        "properties": {
                            "palavras_chave_primarias": {"type": "array", "items": {"type": "string"}, "minItems": 5},
                            "palavras_chave_secundarias": {"type": "array", "items": {"type": "string"}, "minItems": 8},
                            "termos_tecnicos": {"type": "array", "items": {"type": "string"}, "minItems": 5}
                        },
                        "required": ["palavras_chave_primarias", "palavras_chave_secundarias", "termos_tecnicos"]
                    },
                    "titulos": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 3,
                        "maxItems": 3
                    },
                    "modelo": {"type": "string", "maxLength": 100},
                    "descricao": {"type": "string"},
                    "roteiro_imagens": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "imagem": {"type": "integer", "minimum": 1, "maximum": 7},
                                "titulo": {"type": "string"},
                                "objetivo": {"type": "string"},
                                "orientacao_visual": {"type": "string"},
                                "texto_sugerido": {"type": "string"}
                            },
                            "required": ["imagem", "titulo", "objetivo", "orientacao_visual"]
                        },
                        "minItems": 7,
                        "maxItems": 7
                    }
                },
                "required": ["analise_estrategica", "seo", "titulos", "modelo", "descricao", "roteiro_imagens"]
            }
        }
    ]
}

def build_user_payload(product_data: dict) -> str:
    """Transforma o dicionário de dados do produto em uma string estruturada para o modelo."""
    payload = "\n# Dados do Produto Fornecidos:\n"
    for key, value in product_data.items():
        if value is not None and value != '':
            # Formata a chave para ser mais legível
            formatted_key = key.replace('_', ' ').title()
            payload += f"- {formatted_key}: {value}\n"
    return payload
