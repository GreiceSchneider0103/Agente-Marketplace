document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('product-form');
  const resultsContainer = document.getElementById('results-container');

  if (!form) {
    console.error("Form with id 'product-form' not found.");
    return;
  }
  if (!resultsContainer) {
    console.error("Container with id 'results-container' not found.");
    return;
  }

  const submitButton = form.querySelector('button[type="submit"]');

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

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    setLoading(true);

    try {
      const formData = new FormData(form);
      const productData = {};
      formData.forEach((value, key) => {
        productData[key] = typeof value === 'string' ? value.trim() : value;
      });

      // 1) Baixa o Word (DOCX)
      await gerarWord(productData);

      // 2) Mensagem de sucesso simples (opcional)
      resultsContainer.innerHTML = `
        <div class="result-section">
          <h2>✅ Word gerado com sucesso</h2>
          <p>O arquivo <b>anuncio_completo.docx</b> foi baixado.</p>
        </div>
      `;
    } catch (err) {
      renderError(err && err.message ? err.message : "Ocorreu um erro.");
    } finally {
      setLoading(false);
    }
  });

  function setLoading(isLoading) {
    if (!submitButton) return;
    submitButton.disabled = !!isLoading;
    submitButton.textContent = isLoading ? 'Gerando...' : 'Gerar Anúncio';
    if (isLoading) resultsContainer.innerHTML = '<div class="loader"></div>';
  }

  function renderError(message) {
    resultsContainer.innerHTML = `
      <div class="result-section error-section">
        <h2><span class="icon">❌</span> Erro na Geração</h2>
        <p>${escapeHtml(safeString(message) || 'Ocorreu um erro desconhecido.')}</p>
      </div>
    `;
  }

  function safeString(v) {
    if (v == null) return '';
    return String(v).trim();
  }

  function escapeHtml(str) {
    return String(str)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
  }
});