/**
 * sync.js — M0 验证主页面逻辑
 *
 * 注意：API 调用通过 Service Worker 自动打开临时 zhihu.com 标签页，
 * 在页面 MAIN world 中执行 XHR（知乎前端自动注入 x-zse-96 签名），
 * 获取结果后自动关闭标签页。全程约 5-10 秒。
 */

const $ = (id) => document.getElementById(id);

const el = {
  auth:    $('result-auth'),
  api:     $('result-api'),
  fs:      $('result-fs'),
  status:  $('status-bar'),
  logContainer: $('log-container'),
};

const btn = {
  checkCookie:  $('btn-check-cookie'),
  testApi:      $('btn-test-api'),
  listFavs:     $('btn-list-favlists'),
  listItems:    $('btn-list-items'),
  selectVault:  $('btn-select-vault'),
  testWrite:    $('btn-test-write'),
  listVault:    $('btn-list-vault'),
  refreshLogs:  $('btn-refresh-logs'),
  clearLogs:    $('btn-clear-logs'),
};

let vaultHandle = null;

// ============================================================
// 工具函数
// ============================================================

async function bg(action, payload = {}) {
  return chrome.runtime.sendMessage({ action, ...payload });
}

function showResult(el, { ok, message, details, error }) {
  el.className = 'result-box visible';
  el.classList.remove('success', 'error', 'info');
  if (ok) {
    el.classList.add('success');
    el.textContent = `✅ ${message}` + (details ? `\n\n${details}` : '');
  } else {
    el.classList.add('error');
    el.textContent = `❌ ${error || message}`;
  }
}

function showInfo(el, message) {
  el.className = 'result-box visible info';
  el.textContent = message;
}

function showLoading(el) {
  el.className = 'result-box visible info';
  el.textContent = '⏳ 正在打开 zhihu.com 临时标签页（后台，不抢焦点）...\n需要等待页面加载 + JS 初始化（~4秒），请稍候。\n查看下方日志面板获取实时进度。';
}

function setStatus(text, isError = false) {
  el.status.textContent = text;
  el.status.style.color = isError ? '#fa5252' : '#6c757d';
}

// ============================================================
// 日志查看器
// ============================================================

async function refreshLogs() {
  try {
    const result = await bg('get-logs');
    const entries = result.entries || [];
    if (entries.length === 0) {
      el.logContainer.innerHTML = '<div class="log-empty">暂无日志。点击操作按钮后重新刷新。</div>';
      return;
    }
    el.logContainer.innerHTML = entries.map(e => {
      const levelClass = e.level || 'LOG';
      return `<div class="log-entry">
        <span class="log-time">${e.time || ''}</span>
        <span class="log-level ${levelClass}">${levelClass}</span>
        <span class="log-module">[${e.module || '?'}]</span>
        <span class="log-msg">${escapeHtml(e.msg || e.message || '')}</span>
        ${e.data ? `<div class="log-data">${escapeHtml(e.data)}</div>` : ''}
      </div>`;
    }).join('');
    el.logContainer.scrollTop = el.logContainer.scrollHeight;
  } catch (err) {
    el.logContainer.innerHTML = `<div class="log-entry"><span class="log-msg" style="color:#fa5252">获取日志失败: ${escapeHtml(err.message)}</span></div>`;
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

btn.refreshLogs.addEventListener('click', refreshLogs);
btn.clearLogs.addEventListener('click', async () => {
  try { await chrome.runtime.sendMessage({ action: 'clear-logs' }); } catch {}
  el.logContainer.innerHTML = '<div class="log-empty">日志已清除</div>';
});

let logInterval = setInterval(refreshLogs, 3000);
window.addEventListener('beforeunload', () => clearInterval(logInterval));

// ============================================================
// 1. 认证
// ============================================================

btn.checkCookie.addEventListener('click', async () => {
  btn.checkCookie.disabled = true;
  showInfo(el.auth, '⏳ 读取 Cookie...');
  setStatus('检查 Cookie...');
  try {
    const result = await bg('check-cookie');
    if (result.ok) {
      const detailLines = Object.entries(result.details || {})
        .map(([k, v]) => `  ${k}: ${v}`).join('\n');
      showResult(el.auth, { ok: true, message: result.message, details: detailLines });
    } else {
      showResult(el.auth, result);
    }
  } catch (err) {
    showResult(el.auth, { ok: false, error: err.message });
  } finally {
    btn.checkCookie.disabled = false;
    setStatus('就绪');
  }
});

btn.testApi.addEventListener('click', async () => {
  btn.testApi.disabled = true;
  showLoading(el.auth);
  setStatus('🚀 打开 zhihu.com 标签页...');
  try {
    const result = await bg('test-api');
    showResult(el.auth, result);
  } catch (err) {
    showResult(el.auth, { ok: false, error: err.message });
  } finally {
    btn.testApi.disabled = false;
    setStatus('就绪');
  }
});

// ============================================================
// 2. 收藏夹数据
// ============================================================

btn.listFavs.addEventListener('click', async () => {
  btn.listFavs.disabled = true;
  showLoading(el.api);
  setStatus('🚀 打开 zhihu.com 标签页...');
  try {
    const result = await bg('list-favlists', { offset: 0 });
    showResult(el.api, result);
  } catch (err) {
    showResult(el.api, { ok: false, error: err.message });
  } finally {
    btn.listFavs.disabled = false;
    setStatus('就绪');
  }
});

btn.listItems.addEventListener('click', async () => {
  btn.listItems.disabled = true;
  showLoading(el.api);
  setStatus('🚀 打开 zhihu.com 标签页...');
  try {
    const list = await bg('list-favlists', { offset: 0 });
    if (!list.ok) {
      showResult(el.api, list);
      return;
    }
    const parsed = JSON.parse(list.details);
    const collections = parsed.collections || [];
    if (collections.length === 0) {
      showResult(el.api, { ok: false, error: '没有找到收藏夹' });
      return;
    }
    const first = collections[0];
    setStatus(`拉取收藏夹「${first.title}」的内容...`);
    const result = await bg('list-items', { collectionId: first.id, offset: 0 });
    if (result.ok) {
      const original = JSON.parse(result.details);
      result.message = `收藏夹「${first.title}」: ${result.message}`;
      result.details = JSON.stringify({ collection_name: first.title, ...original }, null, 2);
    }
    showResult(el.api, result);
  } catch (err) {
    showResult(el.api, { ok: false, error: err.message });
  } finally {
    btn.listItems.disabled = false;
    setStatus('就绪');
  }
});

// ============================================================
// 3. 文件系统（不变）
// ============================================================

btn.selectVault.addEventListener('click', async () => {
  btn.selectVault.disabled = true;
  setStatus('打开目录选择器...');
  try {
    const handle = await Vault.pickVaultDirectory();
    vaultHandle = handle;
    showResult(el.fs, {
      ok: true,
      message: `已选择 Vault: ${handle.name}`,
      details: `目录名: ${handle.name}\n句柄已存入 IndexedDB，可跨会话恢复。`,
    });
    setStatus(`Vault: ${handle.name}`);
  } catch (err) {
    if (err.name === 'AbortError') {
      showInfo(el.fs, '已取消选择');
    } else {
      showResult(el.fs, { ok: false, error: `选择失败: ${err.message}` });
    }
  } finally {
    btn.selectVault.disabled = false;
    if (!vaultHandle) setStatus('就绪');
  }
});

btn.testWrite.addEventListener('click', async () => {
  btn.testWrite.disabled = true;
  showInfo(el.fs, '⏳ 写入中...');
  try {
    let handle = vaultHandle;
    if (!handle) handle = await Vault.getVaultHandle();
    if (!handle) {
      showResult(el.fs, { ok: false, error: '尚未选择 Vault，请先点击「选择 Vault 目录」' });
      return;
    }
    setStatus('检查写入权限...');
    const permitted = await Vault.ensurePermission(handle);
    if (!permitted) {
      showResult(el.fs, { ok: false, error: '没有写入权限，请重新选择 Vault' });
      return;
    }
    vaultHandle = handle;
    setStatus('写入测试文件...');
    const testDir = await Vault.ensureDirectory(handle, ['zhihu2obsidian-test']);
    const testContent = `---\ntitle: "M0 测试文件"\ncreated: "${new Date().toISOString()}"\ntags:\n  - test\n  - zhihu2obsidian\n---\n\n# M0 技术验证 — 文件写入测试\n\n✅ File System Access API 写入成功！\n\n- 时间: ${new Date().toLocaleString()}\n`;
    const fileName = `m0-test-${Date.now()}.md`;
    await Vault.writeMarkdownFile(testDir, fileName, testContent);
    const fileList = await Vault.listFiles(testDir);
    showResult(el.fs, {
      ok: true,
      message: `写入成功: ${fileName}`,
      details: `路径: zhihu2obsidian-test/${fileName}\n\n目录中的文件:\n${fileList.map(f => `  - ${f}`).join('\n')}`,
    });
    setStatus('写入测试完成');
  } catch (err) {
    showResult(el.fs, { ok: false, error: `写入失败: ${err.message}` });
    setStatus('写入失败', true);
  } finally {
    btn.testWrite.disabled = false;
  }
});

btn.listVault.addEventListener('click', async () => {
  btn.listVault.disabled = true;
  showInfo(el.fs, '⏳ 读取中...');
  try {
    let handle = vaultHandle;
    if (!handle) handle = await Vault.getVaultHandle();
    if (!handle) {
      showResult(el.fs, { ok: false, error: '尚未选择 Vault' });
      return;
    }
    const permitted = await Vault.ensurePermission(handle);
    if (!permitted) {
      showResult(el.fs, { ok: false, error: '没有读取权限' });
      return;
    }
    vaultHandle = handle;
    let testDir;
    try {
      testDir = await Vault.ensureDirectory(handle, ['zhihu2obsidian-test']);
    } catch {
      showResult(el.fs, { ok: false, error: 'zhihu2obsidian-test 目录不存在，请先写入测试文件' });
      return;
    }
    const files = await Vault.listFiles(testDir);
    showResult(el.fs, { ok: true, message: `找到 ${files.length} 个测试文件`, details: files.map(f => `  - ${f}`).join('\n') });
  } catch (err) {
    showResult(el.fs, { ok: false, error: `列出文件失败: ${err.message}` });
  } finally {
    btn.listVault.disabled = false;
    setStatus('就绪');
  }
});

// ============================================================
// 初始化
// ============================================================
(async () => {
  try {
    const handle = await Vault.getVaultHandle();
    if (handle) { vaultHandle = handle; setStatus(`已有 Vault: ${handle.name}`); }
  } catch { /* first use */ }
})();
