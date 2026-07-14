const statusEl = document.getElementById('status');
const contentEl = document.getElementById('content');
const copyBtn = document.getElementById('copy');

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

function renderList(title, items, renderItem) {
  if (!items?.length) return '';
  return `<div class="card"><h2>${escapeHtml(title)}</h2><ul>${items.map(renderItem).join('')}</ul></div>`;
}

function render(state) {
  if (!state) {
    statusEl.textContent = '等待分析';
    contentEl.innerHTML = '';
    return;
  }
  if (state.loading) {
    statusEl.textContent = '分析中...';
    contentEl.innerHTML = '';
    return;
  }
  if (state.error) {
    statusEl.textContent = '无法分析';
    contentEl.innerHTML = `<pre class="card">${escapeHtml(state.error)}</pre>`;
    return;
  }
  const analysis = state.analysis || {};
  statusEl.textContent = state.context?.text ? `已分析 ${state.context.text.length} 字` : '已分析';
  contentEl.innerHTML = [
    renderList('知识树位置', analysis.matched_tree_nodes, item =>
      `<li><strong>${escapeHtml(item.path?.join(' / ') || item.title)}</strong><br><span class="muted">score=${escapeHtml(item.score)} ${escapeHtml(item.reason)}</span></li>`
    ),
    renderList('相似素材', analysis.similar_sources, item =>
      `<li><strong>[${escapeHtml(item.platform)}] ${escapeHtml(item.title)}</strong><br><span class="muted">${escapeHtml(item.author)} score=${escapeHtml(item.score)}</span><blockquote>${escapeHtml(item.quote)}</blockquote></li>`
    ),
    renderList('写作建议', analysis.writing_suggestions, item => `<li>${escapeHtml(item)}</li>`),
    renderList('相似风险', analysis.risks, item =>
      `<li class="risk-${escapeHtml(item.level)}">[${escapeHtml(item.level)}] ${escapeHtml(item.message)}</li>`
    ),
  ].join('');
}

async function load() {
  const { lastAnalysis } = await chrome.storage.local.get('lastAnalysis');
  render(lastAnalysis);
}

copyBtn.addEventListener('click', async () => {
  const { lastAnalysis } = await chrome.storage.local.get('lastAnalysis');
  await navigator.clipboard.writeText(JSON.stringify(lastAnalysis?.analysis || {}, null, 2));
});

chrome.storage.onChanged.addListener((changes, area) => {
  if (area === 'local' && changes.lastAnalysis) render(changes.lastAnalysis.newValue);
});

load();
