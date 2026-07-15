/**
 * Content script for zhihu2obsidian extension.
 * Injects functions into page context + auto-detects question pages.
 */

// ── 选中文本分析 ──
window.zhihuKnowledgeSelection = function zhihuKnowledgeSelection() {
  const selection = window.getSelection();
  const text = selection ? selection.toString().trim() : '';
  const questionTitle =
    document.querySelector('.QuestionHeader-title')?.textContent?.trim() ||
    document.querySelector('h1')?.textContent?.trim() ||
    '';
  const author =
    selection?.anchorNode?.parentElement?.closest('.ContentItem')?.querySelector('.AuthorInfo-name')?.textContent?.trim() ||
    document.querySelector('.AuthorInfo-name')?.textContent?.trim() ||
    '';
  return { text, url: location.href, pageTitle: document.title, questionTitle, author };
};

// ── 问题信息（无需选中） ──
window.zhihuQuestionInfo = function zhihuQuestionInfo() {
  const questionTitle =
    document.querySelector('.QuestionHeader-title')?.textContent?.trim() ||
    document.querySelector('h1')?.textContent?.trim() ||
    '';
  const description =
    document.querySelector('.QuestionHeader-detail')?.textContent?.trim() || '';
  return {
    url: location.href,
    pageTitle: document.title,
    questionTitle,
    questionDescription: description,
  };
};

// ── 自动检测：是否有问题标题 → 通知 background ──
(function autoDetect() {
  const checkQuestion = () => {
    const title =
      document.querySelector('.QuestionHeader-title')?.textContent?.trim() ||
      document.querySelector('h1')?.textContent?.trim() ||
      '';
    if (title && location.href.includes('zhihu.com')) {
      chrome.runtime.sendMessage({
        type: 'QUESTION_DETECTED',
        questionTitle: title,
        url: location.href,
      });
    }
  };
  // 页面加载后 + DOM 变化时重试（SPA 导航）
  checkQuestion();
  const observer = new MutationObserver(() => checkQuestion());
  observer.observe(document.body, { childList: true, subtree: true, once: true });
})();
