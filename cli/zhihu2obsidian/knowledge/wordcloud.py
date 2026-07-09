"""词云生成."""

from __future__ import annotations

from pathlib import Path


def generate_wordcloud(chunks: list, output_path: Path) -> None:
    """从文本块生成词云图片."""
    # Collect all text
    all_text = " ".join(c.text for c in chunks if c.text)

    if not all_text.strip():
        # No text, create empty white image
        from PIL import Image
        img = Image.new("RGB", (800, 400), "white")
        img.save(output_path)
        return

    try:
        import jieba
        from wordcloud import WordCloud
    except ImportError:
        # Skip wordcloud if deps not installed
        print("  ⚠ 需要 jieba + wordcloud: pip install jieba wordcloud matplotlib")
        return

    # Chinese tokenization
    tokens = jieba.cut(all_text)
    # Filter short tokens and common stopwords
    filtered = [t for t in tokens if len(t) > 1 and t not in _STOPWORDS]

    # Join back for WordCloud
    text_for_wc = " ".join(filtered)

    if not text_for_wc.strip():
        from PIL import Image
        img = Image.new("RGB", (800, 400), "white")
        img.save(output_path)
        return

    wc = WordCloud(
        width=1200,
        height=600,
        background_color="white",
        font_path="/System/Library/Fonts/STHeiti Light.ttc",
        max_words=200,
        max_font_size=80,
        random_state=42,
        collocations=False,
    )
    wc.generate(text_for_wc)
    wc.to_file(str(output_path))


_STOPWORDS: set = {
    "这个", "那个", "什么", "可以", "没有", "不是", "就是", "但是", "一个",
    "我们", "他们", "你们", "自己", "知道", "觉得", "因为", "所以", "如果",
    "时候", "问题", "可能", "已经", "还是", "或者", "只是", "虽然", "不过",
    "然后", "这么", "怎么", "这样", "非常", "因为", "还有", "现在", "已经",
    "最后", "开始", "看到", "出来", "不过", "一样", "很多", "一些", "也是",
    "大家", "之后", "觉得", "起来", "应该", "能够", "需要", "什么",
    "其实", "这个", "那个", "就是", "可以", "没有", "不要", "不是",
    "一个", "比较", "有些", "所有", "对于", "关于", "因为", "所以",
    "而是", "还是", "虽然", "然后", "但是", "不过", "所以", "如果",
    "都会", "由于", "通过", "作为", "实现",
}
