// ═══ INÍCIO: my-agent/marketplace-specialist/static/script.js ═══
(() => {
  const chatBody = document.getElementById("chatBody");
  const composerForm = document.getElementById("composerForm");
  const chatInput = document.getElementById("chatInput");

  const btnRestart = document.getElementById("btnRestart");
  const btnViewJson = document.getElementById("btnViewJson");
  const btnDocx = document.getElementById("btnDocx");
  const finalActions = document.getElementById("finalActions");

  const statusPill = document.getElementById("statusPill");
  const checklist = document.getElementById("checklist");

  const marketplaceQuick = document.getElementById("marketplaceQuick");

  const filePhoto = document.getElementById("file_photo");
  const filePdf = document.getElementById("file_pdf");
  const fileSheet = document.getElementById("file_sheet");
  const btnPhoto = document.getElementById("btnPhoto");
  const btnPdf = document.getElementById("btnPdf");
  const btnSheet = document.getElementById("btnSheet");

  const jsonModal = document.getElementById("jsonModal");
  const jsonPre = document.getElementById("jsonPre");
  const jsonClose = document.getElementById("jsonClose");
  const jsonCloseBtn = document.getElementById("jsonCloseBtn");

  const resume = {
    nome: document.getElementById("r_nome"),
    marca: document.getElementById("r_marca"),
    materiais: document.getElementById("r_materiais"),
    dimensoes: document.getElementById("r_dimensoes"),
    peso: document.getElementById("r_peso"),
    embalagem: document.getElementById("r_embalagem"),
    montagem: document.getElementById("r_montagem"),
    empresa: document.getElementById("r_empresa"),
    marketplace: document.getElementById("r_marketplace"),
  };

  // Campos que o backend exige
  const FIELDS_ORDER = [
    "nome_produto",
    "marca_linha",
    "materiais",
    "dimensoes",
    "peso_suportado",
    "conteudo_embalagem",
    "necessita_montagem",
    "tempo_montagem",
    "nivel_montagem",
    "empresa",
    "marketplace_alvo",
  ];

  // Perguntas base (fallback). O backend também devolve QUESTIONS_MAP quando faltar.
  const QUESTIONS = {
    nome_produto: "Qual é o nome do produto?",
    marca_linha: "Qual é a marca ou linha do produto?",
    materiais: "Do que o produto é feito (estrutura, pés, estofamento)?",
    dimensoes: "Quais são as dimensões (L x A x P)?",
    peso_suportado: "Quanto peso o produto suporta (kg)?",
    conteudo_embalagem: "O que vem na embalagem?",
    necessita_montagem: "Precisa de montagem? (sim/não)",
    tempo_montagem: "Se sim, qual o tempo estimado para montar?",
    nivel_montagem: "E qual o nível de dificuldade (fácil, médio, difícil)?",
    empresa: "Qual é o nome da sua empresa (vendedor)?",
    marketplace_alvo: "Para qual marketplace este anúncio se destina?",
  };

  const state = {
    currentField: null,
    data: {},
    json: null,
    files: { photo: null, pdf: null, sheet: null },
  };

  function setStatus(text) {
    statusPill.textContent = text;
  }

  function setChecklist(activeStep, doneSteps = []) {
    const items = checklist.querySelectorAll("li");
    items.forEach(li => {
      li.classList.remove("active");
      li.classList.remove("done");
      const step = li.getAttribute("data-step");
      if (doneSteps.includes(step)) li.classList.add("done");
      if (step === activeStep) li.classList.add("active");
    });
  }

  function bubble(text, who = "agent") {
    const div = document.createElement("div");
    div.className = `bubble ${who}`;
    div.innerHTML = text;
    chatBody.appendChild(div);
    chatBody.scrollTop = chatBody.scrollHeight;
  }

  function block(title, html, kind = "warn") {
    const div = document.createElement("div");
    div.className = `block ${kind}`;
    div.innerHTML = `<h4>${title}</h4>${html}`;
    chatBody.appendChild(div);
    chatBody.scrollTop = chatBody.scrollHeight;
  }

  function updateResume() {
    resume.nome.textContent = state.data.nome_produto || "—";
    resume.marca.textContent = state.data.marca_linha || "—";
    resume.materiais.textContent = state.data.materiais || "—";
    resume.dimensoes.textContent = state.data.dimensoes || "—";
    resume.peso.textContent = state.data.peso_suportado || "—";
    resume.embalagem.textContent = state.data.conteudo_embalagem || "—";

    if (!state.data.necessita_montagem) {
      resume.montagem.textContent = "—";
    } else if (String(state.data.necessita_montagem).toLowerCase().includes("sim")) {
      const t = state.data.tempo_montagem ? `, ${state.data.tempo_montagem}` : "";
      const n = state.data.nivel_montagem ? `, ${state.data.nivel_montagem}` : "";
      resume.montagem.textContent = `Sim${t}${n}`;
    } else {
      resume.montagem.textContent = "Não";
    }

    resume.empresa.textContent = state.data.empresa || "—";
    resume.marketplace.textContent = state.data.marketplace_alvo || "—";
  }

  function nextMissingField() {
    // regra: se montagem = não, não perguntar tempo/nivel
    for (const f of FIELDS_ORDER) {
      if (f === "tempo_montagem" || f === "nivel_montagem") {
        const m = String(state.data.necessita_montagem || "").toLowerCase();
        if (!m.includes("sim")) continue;
      }
      if (!state.data[f] || String(state.data[f]).trim() === "") return f;
    }
    return null;
  }

  function askForField(field) {
    state.currentField = field;
    const q = QUESTIONS[field] || "Me diga esse dado:";
    bubble(q, "agent");
  }

  function normalizeYesNo(v) {
    const t = String(v || "").trim().toLowerCase();
    if (["s", "sim", "yes", "y"].includes(t)) return "sim";
    if (["n", "nao", "não", "no"].includes(t)) return "não";
    return v;
  }

  async function callGenerate() {
    setStatus("Validando");
    setChecklist("validacao", ["minimo", "uploads"]);
    bubble("Perfeito. Vou validar e gerar o JSON do anúncio…", "agent");

    const fd = new FormData();
    Object.entries(state.data).forEach(([k, v]) => fd.append(k, v));

    if (state.files.pdf) fd.append("file_pdf", state.files.pdf);
    if (state.files.photo) fd.append("file_photo", state.files.photo);
    // o backend atual não usa file_sheet, mas mantemos sem quebrar:
    if (state.files.sheet) fd.append("file_sheet", state.files.sheet);

    try {
      const res = await fetch("/generate", { method: "POST", body: fd });
      const data = await res.json();

      if (data.status === "missing_fields") {
        setStatus("Coleta mínima");
        setChecklist("minimo", []);
        const qs = data.questions || {};
        const missing = (data.missing || []);
        const items = missing.map(f => `<li>${qs[f] || f}</li>`).join("");
        block("Campos Faltantes", `<p>Preciso destes dados para seguir:</p><ul>${items}</ul>`, "warn");

        // pergunta o primeiro faltante
        const first = missing[0] || nextMissingField();
        if (first) askForField(first);
        return;
      }

      if (data.status !== "ok") {
        setStatus("Erro");
        setChecklist("validacao", ["minimo", "uploads"]);
        block("Erro", `<p>${data.message || "Falha ao gerar."}</p>`, "err");
        return;
      }

      // OK
      state.json = data;
      btnViewJson.disabled = false;
      jsonPre.textContent = JSON.stringify(data, null, 2);

      setStatus("JSON pronto");
      setChecklist("json", ["minimo", "uploads", "validacao", "extracao", "fontes"]);
      block("JSON Gerado", `<p>Conteúdo gerado com sucesso. Você pode <strong>Ver JSON</strong> ou gerar o <strong>DOCX</strong>.</p>`, "ok");

      finalActions.style.display = "flex";
    } catch (e) {
      setStatus("Erro");
      setChecklist("validacao", ["minimo", "uploads"]);
      block("Erro inesperado", `<p>Não consegui falar com o servidor. Veja o console.</p>`, "err");
      console.error(e);
    }
  }

  async function downloadDocx() {
    if (!state.json) {
      block("Atenção", "<p>Gere o JSON antes de gerar o DOCX.</p>", "warn");
      return;
    }
    setStatus("Gerando DOCX");
    setChecklist("docx", ["minimo", "uploads", "validacao", "extracao", "fontes", "json"]);
    bubble("Gerando o DOCX agora…", "agent");

    const fd = new FormData();
    Object.entries(state.data).forEach(([k, v]) => fd.append(k, v));
    if (state.files.pdf) fd.append("file_pdf", state.files.pdf);
    if (state.files.photo) fd.append("file_photo", state.files.photo);
    if (state.files.sheet) fd.append("file_sheet", state.files.sheet);

    try {
      const res = await fetch("/generate-docx", { method: "POST", body: fd });
      const contentType = res.headers.get("content-type") || "";

      if (contentType.includes("application/json")) {
        const err = await res.json();
        if (err.status === "missing_fields") {
          const qs = err.questions || {};
          const missing = (err.missing || []);
          const items = missing.map(f => `<li>${qs[f] || f}</li>`).join("");
          block("Campos Faltantes", `<p>Preencha:</p><ul>${items}</ul>`, "warn");
          const first = missing[0] || nextMissingField();
          if (first) askForField(first);
          return;
        }
        block("Erro ao gerar DOCX", `<p>${err.message || "Falha ao criar o DOCX."}</p>`, "err");
        return;
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;

      const nome = (state.data.nome_produto || "anuncio")
        .replace(/[^a-z0-9]/gi, "_")
        .toLowerCase();

      a.download = `anuncio_${nome}.docx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);

      setStatus("Concluído");
      setChecklist("docx", ["minimo", "uploads", "validacao", "extracao", "fontes", "json", "docx"]);
      block("DOCX pronto", `<p>Download iniciado ✅</p>`, "ok");
    } catch (e) {
      setStatus("Erro");
      block("Erro inesperado", `<p>Não consegui gerar o DOCX.</p>`, "err");
      console.error(e);
    }
  }

  function resetAll() {
    state.currentField = null;
    state.data = {};
    state.json = null;
    state.files = { photo: null, pdf: null, sheet: null };
    btnViewJson.disabled = true;
    finalActions.style.display = "none";
    jsonPre.textContent = "{}";
    marketplaceQuick.value = "";
    chatBody.innerHTML = "";
    setStatus("Coleta mínima");
    setChecklist("minimo", []);
    updateResume();
    greet();
  }

  function greet() {
    bubble(
      `Olá! Sou o assistente de anúncios da RocketAds. Vou te ajudar a criar um anúncio completo (estratégia + SEO + títulos + descrição + roteiro de imagens) e entregar em Word.<div class="small">Vamos começar pela coleta mínima.</div>`,
      "agent"
    );
    const first = nextMissingField();
    askForField(first);
  }

  // Upload buttons
  btnPhoto.addEventListener("click", () => filePhoto.click());
  btnPdf.addEventListener("click", () => filePdf.click());
  btnSheet.addEventListener("click", () => fileSheet.click());

  function onFilePicked(kind, file) {
    if (!file) return;
    state.files[kind] = file;
    setStatus("Coleta mínima");
    setChecklist("uploads", ["minimo"]);
    bubble(`Anexo recebido: <strong>${file.name}</strong>`, "agent");
  }

  filePhoto.addEventListener("change", (e) => onFilePicked("photo", e.target.files[0]));
  filePdf.addEventListener("change", (e) => onFilePicked("pdf", e.target.files[0]));
  fileSheet.addEventListener("change", (e) => onFilePicked("sheet", e.target.files[0]));

  // Quick marketplace selector
  marketplaceQuick.addEventListener("change", () => {
    if (marketplaceQuick.value) {
      state.data.marketplace_alvo = marketplaceQuick.value;
      updateResume();
      bubble(`Marketplace definido: <strong>${marketplaceQuick.value}</strong>`, "agent");
      const nxt = nextMissingField();
      if (nxt) askForField(nxt);
      else callGenerate();
    }
  });

  // Submit chat
  composerForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const text = (chatInput.value || "").trim();
    if (!text) return;

    bubble(text, "user");
    chatInput.value = "";

    // Se estamos perguntando um campo específico, gravar nele
    if (state.currentField) {
      let v = text;

      // Normalizações pontuais
      if (state.currentField === "necessita_montagem") v = normalizeYesNo(v);

      // aceitar "campo: valor" como atalho
      const match = text.match(/^([a-zA-Z_]+)\s*:\s*(.+)$/);
      if (match && QUESTIONS[match[1]]) {
        state.data[match[1]] = match[2].trim();
      } else {
        state.data[state.currentField] = v;
      }
      state.currentField = null;
      updateResume();
    } else {
      // Se usuário falou solto, tenta usar como "nome" se vazio
      if (!state.data.nome_produto) state.data.nome_produto = text;
      updateResume();
    }

    // Se já temos marketplace pelo quick, mantém.
    if (marketplaceQuick.value && !state.data.marketplace_alvo) {
      state.data.marketplace_alvo = marketplaceQuick.value;
      updateResume();
    }

    // Próximo passo
    const nxt = nextMissingField();
    if (nxt) {
      setStatus("Coleta mínima");
      setChecklist("minimo", []);
      askForField(nxt);
      return;
    }

    // Tudo preenchido -> chama backend
    await callGenerate();
  });

  btnRestart.addEventListener("click", resetAll);

  btnViewJson.addEventListener("click", () => {
    jsonModal.setAttribute("aria-hidden", "false");
  });
  jsonClose.addEventListener("click", () => jsonModal.setAttribute("aria-hidden", "true"));
  jsonCloseBtn.addEventListener("click", () => jsonModal.setAttribute("aria-hidden", "true"));

  btnDocx.addEventListener("click", downloadDocx);

  // Start
  resetAll();
})();
// ═══ FIM: my-agent/marketplace-specialist/static/script.js ═══