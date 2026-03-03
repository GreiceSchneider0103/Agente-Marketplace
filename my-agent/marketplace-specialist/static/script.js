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

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    setLoading(true);

    const formData = new FormData(form);
    const productData = {};
    formData.forEach((value, key) => {
      productData[key] = typeof value === 'string' ? value.trim() : value;
    });

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
  });

  function setLoading(isLoading) {
    if (!submitButton) return;
    submitButton.disabled = !!isLoading;
    submitButton.textContent = isLoading ? 'Gerando...' : 'Gerar Anúncio';
    if (isLoading) resultsContainer.innerHTML = '<div class="loader"></div>';
  }

  function renderResult(data) {
    resultsContainer.innerHTML = '';
    const status = safeString(data && data.status);

    if (!status) {
      renderError('Resposta inválida: status ausente.');
      return;
    }

    if (status === 'ok') return renderSuccess(data);
    if (status === 'missing_fields') return renderMissingFields(data);
    if (status === 'error') return renderError(safeString(data && data.message) || 'Ocorreu um erro.');

    renderError(`Status desconhecido recebido: ${status}`);
  }

  function renderSuccess(data) {
    const analise = data && data.analise_estrategica;
    const seo = data && data.seo;
    const titulos = data && data.titulos;
    const modelo = data && data.modelo;
    const descricao = data && data.descricao;
    const roteiro = data && data.roteiro_imagens;

    resultsContainer.innerHTML = `
      ${createSectionHTML('Análise Estratégica', analise)}
      ${createSectionHTML('SEO', seo)}
      ${createSectionHTML('Títulos Sugeridos', titulos)}
      ${createSectionHTML('Campo Modelo', modelo)}
      <div class="result-section">
        <h2>Descrição Completa</h2>
        <div class="description-content">${formatMultiline(descricao)}</div>
      </div>
      ${createSectionHTML('Roteiro de Imagens', roteiro)}
    `;
  }

  function renderMissingFields(data) {
    const questions = Array.isArray(data && data.questions) ? data.questions : [];
    const list = questions.length
      ? questions.map(q => `<li>${escapeHtml(safeString(q) || 'Campo faltando.')}</li>`).join('')
      : '<li>Preencha os campos obrigatórios para continuar.</li>';

    resultsContainer.innerHTML = `
      <div class="result-section error-section">
        <h2><span class="icon">⚠️</span> Campos Faltando</h2>
        <p>Por favor, preencha os seguintes campos para continuar:</p>
        <ul>${list}</ul>
      </div>
    `;
  }

  function renderError(message) {
    resultsContainer.innerHTML = `
      <div class="result-section error-section">
        <h2><span class="icon">❌</span> Erro na Geração</h2>
        <p>${escapeHtml(safeString(message) || 'Ocorreu um erro desconhecido.')}</p>
      </div>
    `;
  }

  function createSectionHTML(title, content) {
    if (content == null) {
      return `<div class="result-section"><h2>${escapeHtml(title)}</h2><p>Não informado.</p></div>`;
    }

    // Roteiro de imagens (melhor leitura)
    if (title === 'Roteiro de Imagens' && Array.isArray(content)) {
      const items = content.map((item, idx) => {
        const n = (item && item.imagem) ? item.imagem : (idx + 1);
        const t = safeString(item && item.titulo);
        const objetivo = safeString(item && item.objetivo);
        const orientacao = safeString(item && item.orientacao_visual);
        const texto = safeString(item && item.texto_sugerido);

        return `
          <li>
            <strong>Imagem ${escapeHtml(String(n))}${t ? ' — ' + escapeHtml(t) : ''}</strong>
            <div>${objetivo ? '<div><b>Objetivo:</b> ' + escapeHtml(objetivo) + '</div>' : ''}</div>
            <div>${orientacao ? '<div><b>Orientação:</b> ' + escapeHtml(orientacao) + '</div>' : ''}</div>
            <div>${texto ? '<div><b>Texto:</b> ' + escapeHtml(texto) + '</div>' : ''}</div>
            ${(!objetivo && !orientacao && !texto) ? '<div>Não informado.</div>' : ''}
          </li>
        `;
      }).join('');

      return `<div class="result-section"><h2>${escapeHtml(title)}</h2><ul>${items}</ul></div>`;
    }

    let contentHTML = '';

    if (typeof content === 'string') {
      contentHTML = `<p>${escapeHtml(content) || 'Não informado.'}</p>`;
    } else if (Array.isArray(content)) {
      const list = content.length
        ? content.map(item => `<li>${formatContent(item)}</li>`).join('')
        : '<li>Não informado.</li>';
      contentHTML = `<ul>${list}</ul>`;
    } else if (typeof content === 'object') {
      const entries = Object.entries(content);
      contentHTML = entries.length
        ? `<ul>${entries.map(([k, v]) => `<li><strong>${escapeHtml(formatKey(k))}:</strong> ${formatContent(v)}</li>`).join('')}</ul>`
        : `<p>Não informado.</p>`;
    } else {
      contentHTML = `<p>${escapeHtml(String(content))}</p>`;
    }

    return `<div class="result-section"><h2>${escapeHtml(title)}</h2>${contentHTML}</div>`;
  }

  function formatKey(key) {
    return String(key).replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
  }

  function formatContent(value) {
    if (value == null) return 'Não informado';
    if (typeof value === 'string') return escapeHtml(value) || 'Não informado';
    if (typeof value === 'number' || typeof value === 'boolean') return escapeHtml(String(value));
    if (Array.isArray(value)) {
      if (!value.length) return 'Não informado';
      return `<ul>${value.map(v => `<li>${formatContent(v)}</li>`).join('')}</ul>`;
    }
    if (typeof value === 'object') {
      const entries = Object.entries(value);
      if (!entries.length) return 'Não informado';
      return entries.map(([k, v]) => `<span><b>${escapeHtml(formatKey(k))}:</b> ${formatContent(v)}</span>`).join('<br>');
    }
    return escapeHtml(String(value));
  }

  function formatMultiline(text) {
    const s = safeString(text);
    if (!s) return 'Não informado.';
    return escapeHtml(s).replace(/\n/g, '<br>');
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