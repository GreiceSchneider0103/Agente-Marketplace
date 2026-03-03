document.addEventListener("DOMContentLoaded", () => {
  const chat = document.getElementById("chat");
  const form = document.getElementById("chat-form");
  const btnSend = document.getElementById("btn-send");
  const btnReset = document.getElementById("btn-reset");

  const step2Box = document.getElementById("step2");
  const uploadsHint = document.getElementById("uploads-hint");

  const filePhoto = document.getElementById("file-photo");
  const filePdf = document.getElementById("file-pdf");
  const fileSheet = document.getElementById("file-sheet");

  function addBubble(role, title, text, badgeText, badgeWarn = false) {
    const div = document.createElement("div");
    div.className = `bubble ${role === "agent" ? "bubble--agent" : "bubble--user"}`;

    const meta = document.createElement("div");
    meta.className = "bubble__meta";
    meta.innerHTML = `<span>${escapeHtml(title)}</span>` +
      (badgeText ? `<span class="badge ${badgeWarn ? "badge--warn" : ""}">${escapeHtml(badgeText)}</span>` : "");

    const body = document.createElement("div");
    body.innerHTML = escapeHtml(text).replace(/\n/g, "<br>");

    div.appendChild(meta);
    div.appendChild(body);
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
  }

  function escapeHtml(str) {
    return String(str || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function setLoading(isLoading) {
    btnSend.disabled = !!isLoading;
    btnSend.textContent = isLoading ? "Gerando Word..." : "Gerar Word";
  }

  function getFormPayload() {
    const fd = new FormData(form);
    const payload = {};
    fd.forEach((v, k) => {
      if (typeof v === "string") payload[k] = v.trim();
      else payload[k] = v;
    });

    // normalize montagem (se "nao", limpa campos)
    const needs = (payload["necessita_montagem"] || "").toLowerCase();
    if (needs === "nao") {
      payload["tempo_montagem"] = "";
      payload["nivel_montagem"] = "";
    }

    // garantia/diferenciais podem não existir se step2 hidden
    payload["garantia"] = (payload["garantia"] || "3 meses").trim();
    payload["diferenciais_reais"] = (payload["diferenciais_reais"] || "").trim();

    return payload;
  }

  function shouldShowStep2() {
    return !!(filePhoto.files?.length || filePdf.files?.length || fileSheet.files?.length);
  }

  function updateUploadsUI() {
    const hasAny = shouldShowStep2();
    step2Box.classList.toggle("hidden", !hasAny);

    const names = [];
    if (filePhoto.files?.[0]) names.push(`Foto: ${filePhoto.files[0].name}`);
    if (filePdf.files?.[0]) names.push(`PDF: ${filePdf.files[0].name}`);
    if (fileSheet.files?.[0]) names.push(`Planilha/print: ${fileSheet.files[0].name}`);

    uploadsHint.textContent = hasAny
      ? `Arquivos selecionados — vou usar como base. (${names.join(" • ")})`
      : `Nenhum arquivo selecionado. (Tudo bem — sigo só com os campos obrigatórios.)`;
  }

  async function gerarWord(payload) {
    const res = await fetch("/generate-docx", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.message || "Falha ao gerar Word");
    }

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = "anuncio_completo.docx";
    document.body.appendChild(a);
    a.click();
    a.remove();

    window.URL.revokeObjectURL(url);
  }

  function boot() {
    chat.innerHTML = "";

    addBubble(
      "agent",
      "Agente",
      [
        "Oi! Vou montar seu anúncio completo (estratégia + SEO + títulos + descrição + roteiro de imagens) e te entregar em Word.",
        "",
        "Antes, preciso do básico:",
        "• Nome do produto",
        "• Marca e (se tiver) Fabricante",
        "• Materiais (estrutura/pés/estofamento)",
        "• Dimensões (L x A x P)",
        "• Peso máximo suportado",
        "• Conteúdo da embalagem",
        "• Precisa montagem? (tempo + nível: fácil/médio/difícil)",
        "• Empresa e canal de vendas (ML/Magalu/Amazon/Shopee/Shopify)",
        "",
        "Se você tiver, pode enviar agora:",
        "✅ Foto do produto",
        "✅ PDF da ficha técnica (eu extraio as informações)",
        "✅ Uma linha/print da planilha com dados extras (opcional)",
      ].join("\n"),
      "Etapa 1"
    );

    updateUploadsUI();
  }

  // listeners uploads
  [filePhoto, filePdf, fileSheet].forEach((el) => {
    el.addEventListener("change", () => {
      updateUploadsUI();

      if (shouldShowStep2()) {
        addBubble(
          "agent",
          "Agente",
          [
            "Perfeito — vou extrair o que for técnico do PDF/fotos e usar como base.",
            "Confere pra mim só 2 coisas:",
            "1) A garantia é 3 meses, certo?",
            "2) Tem diferenciais reais que você quer que eu destaque? (opcional)",
            "",
            "(Se não tiver, eu sigo. Sem travar.)",
          ].join("\n"),
          "Etapa 2"
        );
      }
    });
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const payload = getFormPayload();

      addBubble(
        "user",
        "Você",
        `Ok — pode gerar o Word.\nProduto: ${payload.nome_produto}\nCanal: ${payload.marketplace_alvo}`,
        "Enviar"
      );

      await gerarWord(payload);

      addBubble(
        "agent",
        "Agente",
        "Fechado. Word gerado e enviado no download. ✅",
        "Concluído"
      );
    } catch (err) {
      addBubble(
        "agent",
        "Agente",
        err?.message || "Ocorreu um erro na geração.",
        "Erro",
        true
      );
    } finally {
      setLoading(false);
    }
  });

  btnReset.addEventListener("click", () => {
    // limpa campos
    form.reset();
    filePhoto.value = "";
    filePdf.value = "";
    fileSheet.value = "";
    step2Box.classList.add("hidden");
    updateUploadsUI();
    boot();
  });

  boot();
});