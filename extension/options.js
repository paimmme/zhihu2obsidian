const apiBase = document.getElementById('apiBase');
const result = document.getElementById('result');

chrome.storage.sync.get({ apiBase: 'http://127.0.0.1:8765' }).then((stored) => {
  apiBase.value = stored.apiBase;
});

document.getElementById('save').addEventListener('click', async () => {
  await chrome.storage.sync.set({ apiBase: apiBase.value.trim() || 'http://127.0.0.1:8765' });
  result.textContent = '已保存';
});

document.getElementById('health').addEventListener('click', async () => {
  try {
    const response = await fetch(`${apiBase.value.replace(/\/$/, '')}/health`);
    result.textContent = JSON.stringify(await response.json(), null, 2);
  } catch (error) {
    result.textContent = `无法连接本地服务。请运行 zhihu2obsidian serve --port 8765\n${error.message}`;
  }
});
