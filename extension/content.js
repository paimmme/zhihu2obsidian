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
  return {
    text,
    url: location.href,
    pageTitle: document.title,
    questionTitle,
    author,
  };
};
