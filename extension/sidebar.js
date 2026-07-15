/**
 * Sidebar for zhihu2obsidian extension.
 * Dual-tab: 文本分析 (selection) / 问题分析 (question + strategy).
 */

const statusEl = document.getElementById('status');
const contentEl = document.getElementById('content');
const actionsEl = document.getElementById('actions');
const copyBtn = document.getElementById('copy');
const tabButtons = document.querySelectorAll('.tab-button');

let currentState = null;

function escapeHtml(v) {
  return String(v || '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
}

function escapeAttr(v) {
  return String(v || '')
    .replaceAll('&', '&amp;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
    .replaceAll('\n', '&#10;')
    .replaceAll('\r', '&#13;');
}

function insertText(text) {
  chrome.runtime.sendMessage({ type: 'INSERT_TEXT', text: text });
}

// ── Tab switching ──
tabButtons.forEach(btn => {
  btn.addEventListener('click', () => {
    tabButtons.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    render(currentState);
  });
});

function getActiveTab() {
  return document.querySelector('.tab-button.active')?.dataset?.tab || 'selection';
}

// ── Platform selector ──
function getSelectedPlatform() {
  const sel = document.getElementById('platform-select');
  return sel ? sel.value : 'zhihu';
}

function onPlatformChange() {
  const platform = getSelectedPlatform();
  chrome.storage.local.set({ selectedPlatform: platform });
  // Re-run question analysis if available
  chrome.storage.local.get('lastAnalysis', ({ lastAnalysis }) => {
    if (lastAnalysis?.questionInfo?.questionTitle) {
      chrome.runtime.sendMessage({ type: 'ANALYZE_QUESTION', questionTitle: lastAnalysis.questionInfo.questionTitle, platform });
    }
  });
}

// ── Event delegation for clickable insert-items ──
document.getElementById('content').addEventListener('click', (e) => {
  const item = e.target.closest('[data-insert-text]');
  if (item) {
    insertText(item.dataset.insertText);
  }
});

// ── Main render ──
function render(state) {
  currentState = state;
  const tab = getActiveTab();
  actionsEl.style.display = 'none';
  actionsEl.innerHTML = '';

  // ── Quality-check tab: show inline panel, hide others ──
  const qcPanel = document.getElementById('tab-quality-check');
  if (tab === 'quality-check') {
    statusEl.textContent = '';
    contentEl.innerHTML = '';
    contentEl.style.display = 'none';
    if (qcPanel) qcPanel.style.display = 'block';
    return;
  }
  if (qcPanel) qcPanel.style.display = 'none';
  contentEl.style.display = '';

  if (!state) {
    statusEl.textContent = '等待分析';
    contentEl.innerHTML = '<p class="muted">右键页面，选择「分析当前问题」或选中文本后分析。</p>';
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

  if (state.questionAnalysis && tab === 'question') {
    renderQuestionView(state);
  } else if (!state.questionAnalysis && tab === 'selection') {
    renderSelectionView(state);
  } else {
    statusEl.textContent = '';
    contentEl.innerHTML = '<p class="muted">切换到对应标签查看结果。</p>';
  }
}

// ════════════════════════════════════════════
//  SELECTION TAB
// ════════════════════════════════════════════

function renderSelectionView(state) {
  const a = state.analysis || {};
  statusEl.textContent = state.context?.text ? `已分析 ${state.context.text.length} 字` : '已分析';
  contentEl.innerHTML = [
    listCard('知识树位置', a.matched_tree_nodes, item =>
      `<li><strong>${escapeHtml(item.path?.join(' / ') || item.title)}</strong><br><span class="muted">score=${escapeHtml(item.score)} ${escapeHtml(item.reason)}</span></li>`),
    listCard('相似素材', a.similar_sources, item =>
      `<li><strong>[${escapeHtml(item.platform)}] ${escapeHtml(item.title)}</strong><br><span class="muted">${escapeHtml(item.author)} score=${escapeHtml(item.score)}</span><blockquote>${escapeHtml(item.quote)}</blockquote></li>`),
    listCard('写作建议', a.writing_suggestions, item => `<li>${escapeHtml(item)}</li>`),
    listCard('相似风险', a.risks, item =>
      `<li class="risk-${escapeHtml(item.level)}">[${escapeHtml(item.level)}] ${escapeHtml(item.message)}</li>`),
  ].join('');
}

// ════════════════════════════════════════════
//  QUESTION TAB
// ════════════════════════════════════════════

function renderQuestionView(state) {
  const a = state.analysis || {};
  const info = state.questionInfo || {};
  const strategy = state.strategy;

  statusEl.textContent = info.questionTitle ? `问题: ${info.questionTitle.slice(0, 40)}...` : '问题分析';

  // Handle strategy errors specifically
  if (state.strategyError) {
    if (state.strategyError.includes('LLM_KEY_REQUIRED')) {
      contentEl.innerHTML = `<div class="card"><p style="color:#b42318">🔑 需要设置 DeepSeek API Key</p><p class="muted">在终端运行：<br><code style="font-size:12px">zhihu2obsidian config set deepseek_api_key sk-xxx</code></p></div>`;
    } else if (state.strategyError.includes('401') || state.strategyError.includes('Unauthorized')) {
      contentEl.innerHTML = `<div class="card"><p style="color:#b42318">🔑 DeepSeek API Key 无效或过期</p><p class="muted">请检查 config 中的 key 是否正确。</p></div>`;
    } else {
      contentEl.innerHTML = `<div class="card"><p style="color:#b42318">❌ ${escapeHtml(state.strategyError)}</p></div>`;
    }
    return;
  }

  const parts = [];

  // ── 问题标题 ──
  if (info.questionTitle) {
    parts.push(`<div class="card"><strong>📌 ${escapeHtml(info.questionTitle)}</strong></div>`);
  }

  // ── Show format analysis (always when available) ──
  // If strategy is shown, format analysis is collapsed with "显示格式分析" toggle
  const showFormat = !strategy && !state.strategyLoading;
  const showFormatToggle = strategy && (a.best_type || a.classification?.length);

  if (showFormat) {
    renderFormatAnalysis(parts, a);
  } else if (showFormatToggle) {
    // Collapsible format analysis behind "显示格式分析"
    parts.push(`<div class="card" data-collapsible="format-recs">
      <div class="card-header" onclick="toggleCollapse('format-recs')">
        <h2>📐 格式分析</h2>
        <span class="collapse-icon collapsed">▶</span>
      </div>
      <div class="card-body" id="collapse-format-recs" style="display:none">`);
    // Render minimal format analysis into a temp array then join
    const fmtParts = [];
    renderFormatAnalysis(fmtParts, a);
    parts.push(fmtParts.join('').replace(/<\/?div class="card"[^>]*>/g, '').replace(/<\/div>/g, '')); // strip outer card wrappers
    parts.push(`</div></div>`);
  }

  // ── 生成策略按钮 / 加载中 / 策略结果 ──
  if (state.strategyLoading) {
    const slowMsg = state.strategySlow
      ? '<br><span class="muted">⏳ 策略可能需要更多时间（素材检索量大），请稍候...</span>'
      : '';
    parts.push(`<div class="card"><p><span class="spinner"></span>生成策略中（需 30-60s，视素材量而定）${slowMsg}</p></div>`);
  } else if (strategy) {
    renderStrategy(parts, strategy);
  } else {
    // 无 strategy, 还没点按钮 — 在后面 actions 区域加按钮
    actionsEl.style.display = 'flex';
    actionsEl.innerHTML = `<button class="action-btn primary" id="gen-strategy-btn">🚀 生成写作策略</button>`;
    setTimeout(() => {
      document.getElementById('gen-strategy-btn')?.addEventListener('click', () => {
        chrome.runtime.sendMessage({ type: 'GENERATE_STRATEGY' });
      });
    }, 0);
  }

  // ── Draft section ──
  if (state.draftLoading) {
    const slowMsg = state.draftSlow
      ? '<br><span class="muted">⏳ 草稿可能需要更多时间（素材量大），请稍候...</span>'
      : '';
    parts.push(`<div class="card"><p><span class="spinner"></span>生成草稿中（需 60-120s）${slowMsg}</p></div>`);
  } else if (state.draftError) {
    if (state.draftError.includes('LLM_KEY_REQUIRED')) {
      parts.push(`<div class="card"><p style="color:#b42318">🔑 需要设置 DeepSeek API Key</p></div>`);
    } else if (state.draftError.includes('401') || state.draftError.includes('Unauthorized')) {
      parts.push(`<div class="card"><p style="color:#b42318">🔑 DeepSeek API Key 无效或过期</p></div>`);
    } else {
      parts.push(`<div class="card"><p style="color:#b42318">❌ ${escapeHtml(state.draftError)}</p></div>`);
    }
  } else if (state.draft) {
    renderDraft(parts, state.draft);
  } else if (strategy) {
    // Strategy is ready, show draft generation button
    parts.push(`<div class="card" style="text-align:center">
      <button class="action-btn primary" id="gen-draft-btn">✍️ 生成草稿</button>
    </div>`);
  }

  contentEl.innerHTML = parts.join('');
  // Bind draft button after rendering
  setTimeout(() => {
    document.getElementById('gen-draft-btn')?.addEventListener('click', () => {
      chrome.runtime.sendMessage({ type: 'GENERATE_DRAFT' });
    });
  }, 0);
}

// ── 格式分析渲染（返回HTML字符串） ──
function renderFormatAnalysis(parts, a) {
  const bestType = a.best_type;
  if (bestType) {
    parts.push(`<div class="card"><h2>🔎 问题类型</h2>`);
    parts.push(`<div><span class="type-tag">${escapeHtml(bestType.type_name)}</span>`);
    parts.push(` <span class="muted">置信度: ${Math.round(bestType.confidence * 100)}%</span></div>`);
    parts.push(`<p class="muted">基调: ${escapeHtml(bestType.estimated_tone)} | 预估长度: ${escapeHtml(bestType.estimated_length)}</p>`);
    if (bestType.avoid?.length) {
      parts.push(`<p style="margin:2px 0;font-size:12px;color:#b42318">⚠ 避免: ${escapeHtml(bestType.avoid.join('；'))}</p>`);
    }
    parts.push('</div>');
  }

  const formatHtml = buildFormatHtml(a.format_recommendation || {});
  if (formatHtml) {
    parts.push(collapsibleCard('📐 格式策略', 'format-recs', true, () => formatHtml));
  }

  const similar = a.similar_sources || [];
  if (similar.length) {
    parts.push(listCard('📚 知识库相似素材', similar.slice(0, 3), s =>
      `<li><strong>[${escapeHtml(s.platform)}] ${escapeHtml(s.title)}</strong><br><span class="muted">${escapeHtml(s.author)}</span><blockquote>${escapeHtml(s.text_preview || '')}...</blockquote></li>`));
  }

  // 关联主题（图谱集成）
  const topics = a.related_topics || [];
  if (topics.length) {
    let topicHtml = '<div class="card"><h2>🌐 关联主题</h2><p class="muted">知识库中与问题相关的主题簇</p><div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:4px">';
    topics.forEach(t => {
      const score = t.relevance_score || 0;
      const size = Math.min(score, 5) + 0.5;
      topicHtml += `<span class="topic-tag" style="font-size:${12 + size}px" title="${escapeHtml(t.title)} (${t.content_count}篇素材, 相关度${score})">${escapeHtml(t.title.slice(0, 20))}</span>`;
    });
    topicHtml += '</div></div>';
    parts.push(topicHtml);
  }
}

// 格式 HTML 内容构建（独立出来供 toggle 复用）
function buildFormatHtml(f) {
  if (!f.description && !f.hook?.recommended?.length && !f.style?.recommended?.length) return '';
  const html = [f.description ? `<p>${escapeHtml(f.description)}</p>` : ''];

  const hook = f.hook || {};
  if (hook.recommended?.length) {
    html.push(`<div class="section-label">开头钩子</div>`);
    hook.recommended.forEach(h => {
      const rc = h.risk_level === 'low' ? 'risk-tag-low' : h.risk_level === 'medium' ? 'risk-tag-medium' : 'risk-tag-high';
      html.push(`<div class="tech-item"><span class="risk-tag ${rc}">${escapeHtml(h.risk_level)}</span><strong>${escapeHtml(h.name)}</strong>：${escapeHtml(h.structure)}</div>`);
    });
  }

  const style = f.style || {};
  if (style.recommended?.length) {
    html.push(`<div class="section-label">文风</div>`);
    html.push(`<div>${style.recommended.map(s => `<span class="type-tag">${escapeHtml(s.name)}</span>`).join(' ')}</div>`);
    if (style.blend_suggestion) html.push(`<p class="muted">${escapeHtml(style.blend_suggestion)}</p>`);
  }

  const sr = f.structure || {};
  if (sr.recommended) {
    html.push(`<div class="section-label">结构：${escapeHtml(sr.recommended.name)}</div>`);
    (sr.recommended.sections || []).forEach(sec => {
      html.push(`<div class="arc-phase"><strong>${escapeHtml(sec.name)}</strong> <span class="emotion">${escapeHtml(sec.length_ratio)}</span><span>${escapeHtml(sec.content)}</span></div>`);
    });
  }

  const arc = f.emotional_arc || {};
  if (arc.recommended) {
    html.push(`<div class="section-label">情绪曲线：${escapeHtml(arc.recommended.name)}</div>`);
    (arc.recommended.phases || []).forEach(ph => {
      html.push(`<div class="arc-phase"><strong>${escapeHtml(ph.phase)}</strong> <span class="emotion">${escapeHtml(ph.emotion)}</span><span>${escapeHtml(ph.action)}</span></div>`);
    });
  }

  const tech = f.techniques || {};
  if (tech.recommended?.length) {
    html.push(`<div class="section-label">推荐技巧</div>`);
    tech.recommended.forEach(t => {
      const rc = t.risk_level === 'low' ? 'risk-tag-low' : t.risk_level === 'medium' ? 'risk-tag-medium' : 'risk-tag-high';
      html.push(`<div class="tech-item"><span class="risk-tag ${rc}">${escapeHtml(t.risk_level)}</span><strong>${escapeHtml(t.name)}</strong>：${escapeHtml(t.description)}</div>`);
    });
  }

  const img = f.image_suggestions || [];
  if (img.length) {
    html.push(`<div class="section-label">配图建议</div>`);
    img.forEach(i => html.push(`<div class="tech-item">· ${escapeHtml(i.name)}</div>`));
  }

  return html.join('');
}

// ── 策略渲染 ──
function renderStrategy(parts, s) {
  // 策略大纲
  const outline = s.outline || [];
  if (outline.length) {
    parts.push(collapsibleCard('📋 策略大纲', 'strategy-outline', true, () => {
      return outline.map((sec, i) => {
        const pts = (sec.key_points || []).map(kp => `<li>${escapeHtml(kp)}</li>`).join('');
        const hint = sec.technique_hint ? `<div class="tech-hint">🛠 ${escapeHtml(sec.technique_hint)}</div>` : '';
        const sectionText = `## ${sec.section}\n${(sec.key_points || []).map(kp => `· ${kp}`).join('\n')}`;
        return `<div class="outline-section clickable-item" data-insert-text="${escapeAttr(sectionText)}"><h4>${i + 1}. ${escapeHtml(sec.section)}</h4><ul>${pts}</ul>${hint}</div>`;
      }).join('');
    }));
  }

  // 素材包
  const m = s.material_package || {};
  if (Object.keys(m).length) {
    // 核心观点
    const views = m.core_viewpoints || [];
    if (views.length) {
      parts.push(collapsibleCard(`💡 核心观点 (${views.length})`, 'core-views', true, () => {
        return views.map(v => `<div class="tech-item clickable-item" data-insert-text="${escapeAttr(v)}">· ${escapeHtml(v)}</div>`).join('');
      }));
    }

    // 论据链
    const chain = m.argument_chain || [];
    if (chain.length) {
      parts.push(collapsibleCard(`🔗 论据链 (${chain.length})`, 'arg-chain', false, () => {
        return chain.map(a => {
          const src = a.source_title ? `<br><span class="muted">来源: ${escapeHtml(a.source_title)}</span>` : '';
          const insertVal = `${a.point} - ${a.evidence || ''}`;
          return `<div class="tech-item clickable-item" data-insert-text="${escapeAttr(insertVal)}"><strong>${escapeHtml(a.point)}</strong><br>证据: ${escapeHtml((a.evidence || '').slice(0, 120))}...${src}</div>`;
        }).join('');
      }));
    }

    // 案例
    const cases = m.case_stories || [];
    if (cases.length) {
      parts.push(collapsibleCard(`📖 案例 (${cases.length})`, 'cases', false, () => {
        return cases.map(c => {
          const storyText = c.story || '';
          return `<div class="tech-item clickable-item" data-insert-text="${escapeAttr(storyText)}"><strong>${escapeHtml(storyText.slice(0, 80))}...</strong><br><span class="muted">用法: ${escapeHtml(c.usage || '')}</span></div>`;
        }).join('');
      }));
    }

    // 金句
    const quotes = m.key_quotes || [];
    if (quotes.length) {
      parts.push(collapsibleCard(`💬 金句 (${quotes.length})`, 'quotes', false, () => {
        return quotes.map(q => {
          const insertVal = `「${q.quote}」— ${q.source || ''}`;
          return `<div class="key-quote clickable-item" data-insert-text="${escapeAttr(insertVal)}">「${escapeHtml(q.quote)}」<span class="cite">— ${escapeHtml(q.source || '')}</span></div>`;
        }).join('');
      }));
    }
  }

  // 配图建议
  const imgSuggests = s.image_suggestions || [];
  if (imgSuggests.length) {
    parts.push(collapsibleCard('📷 配图建议', 'img-suggestions', false, () => {
      return imgSuggests.map(si => {
        const secName = escapeHtml(si.section);
        const imgType = escapeHtml(si.image_type_name || '');
        const placement = escapeHtml(si.placement || '');
        const images = si.images || [];
        const marker = si.suggest_marker || '';

        let imgHtml = `<div class="outline-section"><h4>${secName} <span class="type-tag">${imgType}</span></h4>`;
        if (placement) imgHtml += `<p class="muted">位置: ${placement}</p>`;

        if (images.length) {
          images.forEach(img => {
            const url = img.url || '';
            const desc = escapeHtml(img.description || '');
            const source = img.source || '';
            if (source === 'suggest') {
              imgHtml += `<div class="tech-item clickable-item" data-insert-text="${escapeAttr(marker)}">建议配图: <code>${escapeHtml(marker)}</code></div>`;
            } else if (url) {
              imgHtml += `<div class="tech-item clickable-item" data-insert-text="${escapeAttr(url)}">`;
              imgHtml += `<a href="${escapeHtml(url)}" target="_blank" rel="noopener" class="img-link">🖼 ${desc}</a>`;
              if (img.author) imgHtml += `<br><span class="muted">摄影: ${escapeHtml(img.author)}</span>`;
              imgHtml += `</div>`;
            }
          });
        } else if (marker) {
          imgHtml += `<div class="tech-item">建议配图: <code>${escapeHtml(marker)}</code></div>`;
        }

        imgHtml += `</div>`;
        return imgHtml;
      }).join('');
    }));
  }

  // 风险
  const risks = s.risks || [];
  if (risks.length) {
    parts.push(listCard('⚠ 风险提示', risks, r =>
      `<li class="risk-${escapeHtml(r.level)}">[${escapeHtml(r.level)}] ${escapeHtml(r.message)}</li>`));
  }

  // 复制按钮文案 — include image suggestions in copied text
  copyBtn.dataset.strategy = '1';
}

// ── 草稿渲染 ──
function renderDraft(parts, draft) {
  parts.push(`<div class="card draft-section">
    <div class="card-header" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:4px">
      <h2 style="margin:0">✍️ 草稿</h2>
      <div style="display:flex;gap:4px">
        <button class="action-btn secondary" onclick="copyDraft()">📋 复制草稿</button>
        <button class="action-btn primary insert-btn" onclick="insertDraft()">➡ 插入回答框</button>
      </div>
    </div>
    <textarea class="draft-textarea" id="draft-textarea">${escapeHtml(draft)}</textarea>
  </div>`);
}

async function copyDraft() {
  const ta = document.getElementById('draft-textarea');
  if (ta && ta.value) {
    await navigator.clipboard.writeText(ta.value);
  }
}

function insertDraft() {
  const ta = document.getElementById('draft-textarea');
  if (ta && ta.value) {
    chrome.runtime.sendMessage({ type: 'INSERT_TEXT', text: ta.value });
  }
}

// ════════════════════════════════════════════
//  QUALITY CHECK (质量检查)
// ════════════════════════════════════════════

function setupQualityCheck() {
  const importBtn = document.getElementById('qc-from-editor-btn');
  const runBtn = document.getElementById('qc-run-btn');
  const qcText = document.getElementById('qc-text');
  const resultDiv = document.getElementById('qc-result');

  // 从草稿导入
  importBtn?.addEventListener('click', () => {
    const draftTa = document.getElementById('draft-textarea');
    if (draftTa && qcText) {
      qcText.value = draftTa.value;
    }
  });

  // 开始检查
  runBtn?.addEventListener('click', async () => {
    if (!qcText || !resultDiv) return;

    const text = qcText.value.trim();
    if (!text) {
      resultDiv.innerHTML = '<div class="qc-error">请输入要检查的文本。</div>';
      resultDiv.style.display = 'block';
      return;
    }

    runBtn.disabled = true;
    runBtn.textContent = '检查中...';
    resultDiv.style.display = 'none';

    try {
      const resp = await fetch('http://localhost:7999/draft-check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, title: '', with_rewrite: true }),
      });

      if (!resp.ok) {
        const detail = await resp.text().catch(() => '');
        throw new Error(`HTTP ${resp.status}${detail ? ': ' + detail.slice(0, 200) : ''}`);
      }

      const data = await resp.json();
      renderQualityCheckResult(resultDiv, data);
      resultDiv.style.display = 'block';
    } catch (err) {
      resultDiv.innerHTML = `<div class="qc-error">检查失败: ${escapeHtml(err.message)}</div>`;
      resultDiv.style.display = 'block';
    } finally {
      runBtn.disabled = false;
      runBtn.textContent = '开始检查';
    }
  });
}

function renderQualityCheckResult(container, data) {
  // ── Verdict banner ──
  const verdicts = {
    good:           { icon: '✅', text: '原创度良好' },
    needs_revision: { icon: '⚠️', text: '需修改部分段落' },
    high_risk:      { icon: '❌', text: '高风险' },
  };
  const v = verdicts[data.verdict] || verdicts.needs_revision;
  const vc = data.verdict === 'good' ? 'good' : data.verdict === 'high_risk' ? 'high_risk' : 'needs_revision';

  let html = `<div class="qc-verdict ${vc}">${v.icon} ${v.text}</div>`;

  // ── Stats grid ──
  const s = data.stats || {};
  html += `<div class="qc-stats">
    <div class="qc-stat"><div class="qc-stat-label">总段落</div><div class="qc-stat-value">${s.total_paragraphs ?? 0}</div></div>
    <div class="qc-stat"><div class="qc-stat-label">高相似</div><div class="qc-stat-value">${s.high_similarity ?? 0}</div></div>
    <div class="qc-stat"><div class="qc-stat-label">平均相似度</div><div class="qc-stat-value">${(s.avg_similarity ?? 0).toFixed(3)}</div></div>
  </div>`;

  // ── Overreliance ──
  if (data.overreliance) {
    html += `<div class="qc-verdict needs_revision">⚠️ 过度依赖: ${escapeHtml(data.overreliance.source)} (${data.overreliance.percentage}%)</div>`;
  }

  // ── Paragraphs ──
  const paragraphs = data.paragraphs || [];
  paragraphs.forEach((p, i) => {
    const riskClass = p.risk || 'good';
    const riskIcon = riskClass === 'good' ? '🟢' : riskClass === 'moderate' ? '🟡' : '🔴';
    const riskLabel = riskClass === 'good' ? '原创度良好' : riskClass === 'moderate' ? '参考' : '高相似';
    const matchInfo = p.match_source ? ` (匹配: ${escapeHtml(p.match_source)})` : '';
    const preview = escapeHtml((p.preview || '').slice(0, 200));

    html += `<div class="qc-paragraph ${riskClass}">
      <div><strong>#${i + 1}</strong> ${riskIcon} ${riskLabel} 相似度: ${(p.similarity ?? 0).toFixed(3)}${matchInfo}</div>
      <div class="qc-paragraph-meta">${preview}</div>`;

    if (p.rewrite) {
      html += `<div class="qc-paragraph-rewrite">✏️ 改写建议: ${escapeHtml(p.rewrite)}</div>`;
    }

    html += `</div>`;
  });

  // ── Source coverage ──
  const coverage = data.coverage || [];
  if (coverage.length) {
    html += `<div class="qc-coverage"><strong>📚 素材使用分布</strong>`;
    coverage.forEach(c => {
      html += `<div class="qc-coverage-item">${c.count}× ${escapeHtml(c.source)}</div>`;
    });
    html += `</div>`;
  }

  container.innerHTML = html;
}

// ════════════════════════════════════════════
//  RENDER HELPERS
// ════════════════════════════════════════════

function listCard(title, items, renderItem) {
  if (!items?.length) return '';
  return `<div class="card"><h2>${escapeHtml(title)}</h2><ul>${items.map(renderItem).join('')}</ul></div>`;
}

function collapsibleCard(title, id, defaultOpen, renderContent) {
  const collapsed = defaultOpen ? '' : 'collapsed';
  const hidden = defaultOpen ? '' : 'style="display:none"';
  return `<div class="card" data-collapsible="${id}">
    <div class="card-header" onclick="toggleCollapse('${id}')">
      <h2>${title}</h2>
      <span class="collapse-icon ${collapsed}">▼</span>
    </div>
    <div class="card-body" id="collapse-${id}" ${hidden}>${renderContent()}</div>
  </div>`;
}

// Toggle collapsible card (called from onclick)
function toggleCollapse(id) {
  const body = document.getElementById(`collapse-${id}`);
  if (!body) return;
  const icon = body.parentElement?.querySelector('.collapse-icon');
  const isHidden = body.style.display === 'none';
  body.style.display = isHidden ? '' : 'none';
  if (icon) icon.classList.toggle('collapsed', !isHidden);
}

// ════════════════════════════════════════════
//  COPY
// ════════════════════════════════════════════

copyBtn.addEventListener('click', async () => {
  const { lastAnalysis } = await chrome.storage.local.get('lastAnalysis');
  const a = lastAnalysis?.analysis || {};
  const s = lastAnalysis?.strategy;
  const draft = lastAnalysis?.draft;
  const isQuestion = lastAnalysis?.questionAnalysis;

  // 草稿优先：如有草稿则复制草稿文本
  if (draft) {
    await navigator.clipboard.writeText(draft);
    return;
  }

  if (isQuestion && s) {
    // Strategy mode: copy formatted text
    let text = '# 写作策略\n\n';
    if (s.outline?.length) {
      text += '## 策略大纲\n';
      s.outline.forEach((sec, i) => {
        text += `${i + 1}. ${sec.section}\n`;
        (sec.key_points || []).forEach(kp => text += `   · ${kp}\n`);
        if (sec.technique_hint) text += `   🛠 ${sec.technique_hint}\n`;
        text += '\n';
      });
    }
    const m = s.material_package || {};
    if (m.core_viewpoints?.length) {
      text += '## 核心观点\n';
      m.core_viewpoints.forEach(v => text += `· ${v}\n`);
      text += '\n';
    }
    if (m.argument_chain?.length) {
      text += '## 论据链\n';
      m.argument_chain.forEach(a => {
        text += `· ${a.point}\n  证据: ${(a.evidence || '').slice(0, 200)}\n`;
        if (a.source_title) text += `  来源: ${a.source_title}\n`;
        text += '\n';
      });
    }
    if (m.key_quotes?.length) {
      text += '## 金句\n';
      m.key_quotes.forEach(q => text += `· 「${q.quote}」— ${q.source || ''}\n`);
      text += '\n';
    }
    // 配图建议
    const imgSuggests = s.image_suggestions || [];
    if (imgSuggests.length) {
      text += '## 配图建议\n';
      imgSuggests.forEach(si => {
        text += `### ${si.section} [${si.image_type_name || ''}]\n`;
        const images = si.images || [];
        if (images.length) {
          images.forEach(img => {
            if (img.url) {
              text += `· ${img.description || ''}\n  ${img.url}\n`;
            } else if (img.suggest_marker) {
              text += `· ${img.suggest_marker}\n`;
            }
          });
        } else if (si.suggest_marker) {
          text += `· ${si.suggest_marker}\n`;
        }
        text += '\n';
      });
    }
    await navigator.clipboard.writeText(text);
  } else if (isQuestion) {
    // Question analysis mode
    await navigator.clipboard.writeText(JSON.stringify(a, null, 2));
  } else {
    // Selection mode
    await navigator.clipboard.writeText(JSON.stringify(a, null, 2));
  }
});

// ════════════════════════════════════════════
//  STORAGE LISTENER
// ════════════════════════════════════════════

chrome.storage.onChanged.addListener((changes, area) => {
  if (area === 'local') {
    if (changes.lastAnalysis) render(changes.lastAnalysis.newValue);
    if (changes.activeTab) {
      tabButtons.forEach(b => b.classList.toggle('active', b.dataset.tab === changes.activeTab.newValue));
    }
  }
});

// ════════════════════════════════════════════
//  INIT
// ════════════════════════════════════════════

async function load() {
  const { lastAnalysis, activeTab } = await chrome.storage.local.get(['lastAnalysis', 'activeTab']);
  if (activeTab) tabButtons.forEach(b => b.classList.toggle('active', b.dataset.tab === activeTab));
  render(lastAnalysis);
  setupQualityCheck();
}

load();
