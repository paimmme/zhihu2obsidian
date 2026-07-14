import sys, os, json, base64, html as html_mod
from pathlib import Path

import streamlit as st

# ── 确保能找到 cli 包 ─────────────────────────────────────────
_HERE = Path(__file__).parent
_CLI_PKG = str((_HERE.parent / "cli").resolve())
if _CLI_PKG not in sys.path:
    sys.path.insert(0, _CLI_PKG)

from zhihu2obsidian.config import Config
from zhihu2obsidian.agent.retriever import Retriever, adjusted_score, PLATFORM_ICON

# ── 页面配置 ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Zhihu2Obsidian",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 样式 ──────────────────────────────────────────────────────
st.markdown("""
<style>
.main-header { font-size: 1.5rem; font-weight: 700; margin-bottom: .5rem; }
.sub-header { font-size: .9rem; color: #666; margin-bottom: 1.5rem; }
.stats-grid { display: flex; gap: 1rem; flex-wrap: wrap; }
.stat-card { background: #f0f2f6; border-radius: 8px; padding: .5rem 1rem; min-width: 120px; }
.stat-card .value { font-size: 1.5rem; font-weight: 700; }
.stat-card .label { font-size: .75rem; color: #666; }
.result-item { border: 1px solid #e0e0e0; border-radius: 8px; padding: 1rem; margin-bottom: .75rem; }
.result-item .title { font-weight: 600; font-size: 1.05rem; }
.result-item .meta { font-size: .8rem; color: #666; margin: .25rem 0; }
.result-item .excerpt { font-size: .85rem; color: #333; margin-top: .5rem; max-height: 120px; overflow-y: auto; }
.highlight { background: #fff3cd; padding: 0 2px; }
.blockquote { border-left: 3px solid #ddd; padding-left: 1rem; color: #555; margin: .5rem 0; font-size: .9rem; }
.platform-tag { display: inline-block; border-radius: 4px; padding: 0 .4rem; font-size: .75rem; font-weight: 600; margin-right: .4rem; }
.platform-zhihu { background: #e8f4e8; color: #2a7a2a; }
.platform-bilibili { background: #e8f0fe; color: #1a5cc8; }
.platform-xiaoyuzhou { background: #fef0e8; color: #c85a1a; }
.platform-default { background: #f0f0f0; color: #666; }
</style>
""", unsafe_allow_html=True)

# ── 辅助函数 ──────────────────────────────────────────────────
@st.cache_resource
def load_knowledge(_config: Config) -> tuple[Path, Retriever | None]:
    kp = _config.knowledge_path
    if not kp.exists():
        return kp, None
    try:
        r = Retriever(kp)
        return kp, r
    except Exception:
        return kp, None


def get_config() -> Config | None:
    try:
        c = Config.load()
        if not c.vault:
            return None
    except Exception:
        c = None
    return c


def render_markdown_snippet(text: str, max_len: int = 500) -> str:
    if not text:
        return ""
    lines = text.split("\n")
    out = []
    count = 0
    for line in lines:
        if line.startswith("![["):
            continue
        out.append(line)
        count += len(line)
        if count > max_len:
            out.append("... *(截断)*")
            break
    return "\n".join(out)


def score_bar(score: float) -> str:
    pct = int(min(score, 1.0) * 100)
    color = "#28a745" if score > 0.7 else "#ffc107" if score > 0.5 else "#dc3545"
    return f'<div style="background:#e9ecef;border-radius:4px;width:100%;height:6px;margin:4px 0"><div style="background:{color};width:{pct}%;height:6px;border-radius:4px"></div></div>'


def platform_tag(platform: str) -> str:
    cls = f"platform-{platform}" if platform else "platform-default"
    label = platform or "unknown"
    return f'<span class="platform-tag {cls}">{label}</span>'


# ── 写作机会评分 ──────────────────────────────────

def calc_opportunity(topic: dict) -> int:
    """计算主题的写作机会评分 (0-100)."""
    score = 0
    score += min(topic.get("content_count", 0) * 3, 30)      # 素材量
    score += min(len(topic.get("viewpoints", [])) * 5, 20)    # 观点多样性
    score += min(len(topic.get("writing_ideas", [])) * 8, 24)  # 选题丰富度
    score += min(len(topic.get("keywords", [])) * 2, 16)      # 标签覆盖
    if len(topic.get("source_platforms", [])) > 1:             # 跨平台额外加分
        score += 10
    return min(score, 100)


def load_topics_index(knowledge_path: Path) -> list[dict]:
    """加载主题索引."""
    idx_file = knowledge_path / "topics" / "index.json"
    if idx_file.exists():
        try:
            return json.loads(idx_file.read_text())
        except Exception:
            return []
    return []


# ── 初始化配置 ────────────────────────────────────────────────
config = get_config()
if config:
    knowledge_path, retriever = load_knowledge(config)
    kb_exists = retriever is not None
else:
    knowledge_path = Path.home() / ".zhihu2obsidian"
    retriever = None
    kb_exists = False

# ================================================================
# 侧栏
# ================================================================
with st.sidebar:
    st.markdown('<div class="main-header">📚 Zhihu2Obsidian</div>', unsafe_allow_html=True)

    # 知识库状态
    st.markdown("---")
    if kb_exists:
        try:
            s = retriever.stats
            total = s.get("total_chunks", "?")
            files = s.get("tracked_files", "?")
            st.success(f"✅ 库就绪 ({total} 块 / {files} 文件)")
        except Exception as e:
            st.warning(f"⚠ 知识库加载异常: {e}")
    else:
        st.warning("📭 知识库未构建")

    # 导航
    st.markdown("---")
    page = st.radio(
        "导航",
        options=["搜索", "知识图谱", "词云", "主题", "AI 写作"],
        index=0,
        label_visibility="collapsed",
    )

    # API Key
    st.markdown("---")
    api_key = st.text_input(
        "DeepSeek API Key",
        value=config.deepseek_api_key if config and config.deepseek_api_key else "",
        type="password",
        placeholder="sk-...",
        help="可选：不设置则写作功能不可用",
    )
    if not api_key and config and config.deepseek_api_key:
        api_key = config.deepseek_api_key
    if api_key and config:
        config.deepseek_api_key = api_key
        config.save()
        st.caption("✅ Key 已保存")

    # 底部
    st.markdown("---")
    if config and config.vault:
        st.caption(f"🗂 {config.vault}")

    # When a topic was selected from graph/wordcloud panel, show hint
    if st.session_state.get("selected_topic") and not st.session_state.get("navigate_to"):
        st.info("📌 已选主题，请在 **主题** 页面查看", icon="ℹ️")

# ================================================================
# 页面: 搜索
# ================================================================
if page == "搜索":
    st.markdown('<div class="main-header">🔎 语义搜索</div>', unsafe_allow_html=True)

    if not kb_exists:
        st.info("📭 请先运行 `zhihu2obsidian knowledge build` 构建知识库")
    else:
        col1, col2 = st.columns([3, 1])
        with col1:
            q = st.text_input(
                "搜索内容",
                value=st.session_state.get("search_query", ""),
                placeholder="输入语义搜索关键词...",
                label_visibility="collapsed",
            )
        with col2:
            n = st.number_input("条数", min_value=1, max_value=20, value=5, label_visibility="collapsed")

        with st.expander("筛选条件", expanded=True):
            fcol1, fcol2, fcol3 = st.columns(3)
            with fcol1:
                platform_filter = st.selectbox("平台", ["全部", "zhihu", "bilibili", "xiaoyuzhou"], index=0)
            with fcol2:
                author_filter = st.text_input("作者", placeholder="按作者筛选")
            with fcol3:
                collection_filter = st.text_input("收藏夹", placeholder="按收藏夹筛选")

        if q:
            filters = {}
            if platform_filter != "全部":
                filters["platform"] = platform_filter
            if author_filter:
                filters["author"] = author_filter
            if collection_filter:
                filters["collection"] = collection_filter

            with st.spinner("搜索中..."):
                assert retriever is not None
                results = retriever.search_grouped(q, n_results=n, **filters)

            if not results:
                st.info(f'📭 未找到匹配 "{q}" 的结果')
            else:
                st.success(f"🔎 找到 {len(results)} 条结果 (已去重加权)")

                for i, r in enumerate(results):
                    meta = r["metadata"]
                    score = adjusted_score(r)
                    title = meta.get("title", "(无标题)")
                    author = meta.get("author", "")
                    section = meta.get("section", "")
                    platform = meta.get("platform", "")
                    collection = meta.get("collection", "")
                    url = meta.get("url", "")
                    content_id = meta.get("content_id", "")
                    text = r.get("text", "")

                    with st.container():
                        st.markdown(f'<div class="result-item">', unsafe_allow_html=True)

                        col_a, col_b = st.columns([5, 1])
                        with col_a:
                            icon = PLATFORM_ICON.get(platform, "📄")
                            tag = platform_tag(platform)
                            st.markdown(f'<div class="title">{i+1}. {icon} {html_mod.escape(title)} {html_mod.escape(tag)}</div>', unsafe_allow_html=True)
                        with col_b:
                            st.markdown(f'<div style="text-align:right;font-size:.8rem;color:#666">score: {score:.2%}</div>', unsafe_allow_html=True)

                        st.markdown(score_bar(score), unsafe_allow_html=True)

                        # 元数据
                        meta_parts = []
                        if author:
                            meta_parts.append(f"👤 {author}")
                        if section:
                            meta_parts.append(f"📂 {section}")
                        if collection:
                            meta_parts.append(f"📁 {collection}")
                        if content_id:
                            meta_parts.append(f"🆔 {content_id[:60]}")
                        if url:
                            meta_parts.append(f'🔗 <a href="{url}" target="_blank">链接</a>')
                        if meta_parts:
                            st.markdown(f'<div class="meta">{" · ".join(html_mod.escape(p) for p in meta_parts)}</div>', unsafe_allow_html=True)

                        excerpt = render_markdown_snippet(text, max_len=300)
                        if excerpt:
                            st.markdown(f'<div class="excerpt">{html_mod.escape(excerpt)}</div>', unsafe_allow_html=True)

                        st.markdown('</div>', unsafe_allow_html=True)

        else:
            # 默认显示知识库概览
            assert retriever is not None
            s = retriever.embedder.stats()
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("🧩 文本块", s.get("total_chunks", 0))
            with col_b:
                st.metric("📄 文件", s.get("tracked_files", 0))
            with col_c:
                st.metric("📊 向量", s.get("total_chunks", 0))
            st.info("💡 输入关键词开始语义搜索")

# ================================================================
# 页面: 知识图谱
# ================================================================
if page == "知识图谱":
    st.markdown('<div class="main-header">📊 知识图谱 · 主题网络</div>', unsafe_allow_html=True)
    st.markdown("主题 · 素材 · 作者 关系网络，选择主题聚焦查看")

    if not kb_exists:
        st.info("📭 请先运行 `zhihu2obsidian knowledge build` 构建知识库")
    else:
        # 主题筛选
        topics_index = load_topics_index(knowledge_path)
        topic_ids = [""] + [t["id"] for t in topics_index]
        topic_labels = ["🏷 全部主题"] + [f'{t["title"]} ({t["content_count"]}篇)' for t in topics_index]

        selected_topic = st.selectbox(
            "🌐 筛选主题，聚焦相关素材网络",
            options=topic_ids,
            format_func=lambda tid: topic_labels[topic_ids.index(tid)] if tid in topic_ids else tid,
            key="graph_topic_filter",
        )

        col_graph, col_info = st.columns([3, 2])

        with col_graph:
            graph_file = knowledge_path / "graph.html"
            if not graph_file.exists():
                st.warning("⚠ 知识图谱未生成。请运行 `zhihu2obsidian knowledge build`")
            else:
                html_content = graph_file.read_text(encoding="utf-8")
                st.html(html_content)

            # Stats
            assert retriever is not None
            s = retriever.embedder.stats()
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("🧩 文本块", s.get("total_chunks", 0))
            with col_b:
                st.metric("📄 文件", s.get("tracked_files", 0))
            with col_c:
                if selected_topic:
                    matching = next((t for t in topics_index if t["id"] == selected_topic), None)
                    st.metric("📂 素材", matching["content_count"] if matching else 0)
                else:
                    st.metric("📂 存储", str(knowledge_path))

        with col_info:
            if selected_topic:
                # Topic detail in sidebar
                topic_file = knowledge_path / "topics" / f"{selected_topic}.json"
                if topic_file.exists():
                    try:
                        tp = json.loads(topic_file.read_text())
                    except Exception:
                        tp = {}

                    score = calc_opportunity(tp)
                    st.markdown(f'### 📌 {tp.get("title", "")}')

                    # Opportunity score
                    st.markdown(f'**📊 写作机会: {score}/100**')
                    st.progress(score / 100)
                    st.caption(f"素材 {tp.get('content_count', 0)} 篇 · 平台 {', '.join(tp.get('source_platforms', []))}")

                    kw = ", ".join(tp.get("keywords", [])[:5])
                    if kw:
                        st.markdown(f"🏷 **关键词:** {kw}")

                    if tp.get("summary"):
                        with st.expander("📝 主题摘要", expanded=False):
                            st.markdown(tp["summary"])

                    if tp.get("viewpoints"):
                        st.markdown("**💡 观点**")
                        for vp in tp["viewpoints"][:3]:
                            st.markdown(f"- {vp}")

                    if tp.get("writing_ideas"):
                        st.markdown("**✍️ 选题**")
                        for wi in tp["writing_ideas"][:3]:
                            st.markdown(f"- {wi}")

                    # Navigate to topic detail
                    if st.button("📂 查看完整主题页", key="goto_topic_from_graph"):
                        st.session_state.selected_topic = selected_topic
                        st.rerun()

            else:
                # No topic selected: show overview
                st.markdown("### 📊 知识库总览")
                assert retriever is not None
                s = retriever.embedder.stats()
                st.metric("🧩 文本块", s.get("total_chunks", 0))
                st.metric("📄 文件", s.get("tracked_files", 0))

                # Writing opportunity rankings
                if topics_index:
                    st.markdown("---")
                    st.markdown("### 🏆 写作机会排行")
                    scored = [(t, calc_opportunity(t)) for t in topics_index]
                    scored.sort(key=lambda x: -x[1])
                    for t, score in scored[:5]:
                        st.progress(score / 100, text=f"{t['title']} ({score})")
                        if st.button(f"查看", key=f"graph_go_{t['id']}"):
                            st.session_state.selected_topic = t["id"]
                            st.rerun()

# ================================================================
# 页面: 词云
# ================================================================
if page == "词云":
    st.markdown('<div class="main-header">☁️ 词云 · 主题机会</div>', unsafe_allow_html=True)
    st.markdown("知识库关键词分布 + 高价值写作主题推荐")

    if not kb_exists:
        st.info("📭 请先运行 `zhihu2obsidian knowledge build` 构建知识库")
    else:
        col_wc, col_opp = st.columns([3, 2])

        with col_wc:
            # Static word cloud (reliable fallback)
            wc_file = knowledge_path / "wordcloud.png"
            if not wc_file.exists():
                st.warning("⚠ 词云未生成")
            else:
                with open(wc_file, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode()
                st.markdown(
                    f'<img src="data:image/png;base64,{img_data}" '
                    f'style="max-width:100%;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.1)">',
                    unsafe_allow_html=True,
                )

            # Hot topic quick access
            topics_index = load_topics_index(knowledge_path)
            if topics_index:
                st.markdown("### 🔥 热门主题")
                scored = [(t, calc_opportunity(t)) for t in topics_index]
                scored.sort(key=lambda x: -x[1])
                cols = st.columns(3)
                for i, (t, score) in enumerate(scored[:9]):
                    with cols[i % 3]:
                        if st.button(f"{t['title'][:10]}… ({score})" if len(t['title']) > 10 else f"{t['title']} ({score})", key=f"wc_topic_{i}"):
                            st.session_state.selected_topic = t["id"]
                            st.rerun()

        with col_opp:
            # Topic opportunity rankings
            st.markdown("### 📊 写作机会评分")
            st.caption("基于素材量、观点多样性、选题丰富度综合评分")

            topics_index = load_topics_index(knowledge_path)
            if topics_index:
                scored = [(t, calc_opportunity(t)) for t in topics_index]
                scored.sort(key=lambda x: -x[1])

                for t, score in scored[:8]:
                    st.progress(score / 100, text=f"**{t['title']}** ({score})")
                    st.caption(f"📄 {t['content_count']}篇 · {', '.join(t.get('keywords', [])[:3])}")
                    if st.button(f"查看主题", key=f"opp_go_{t['id']}"):
                        st.session_state.selected_topic = t["id"]
                        st.rerun()
                    st.markdown("---")

            # Legacy word frequency buttons
            st.markdown("### 🔥 热词快捷搜索")
            if retriever:
                try:
                    from collections import Counter
                    import re

                    all_chunks = retriever.embedder.get_all()
                    words = Counter()
                    for c in all_chunks:
                        text = c.get("document", "") or ""
                        tokens = re.findall(r"[\u4e00-\u9fff\u3400-\u4dbf]{2,10}", text)
                        words.update(tokens)

                    top = words.most_common(40)
                    stopwords = {"一个", "可以", "这个", "那个", "什么", "没有", "我们",
                                 "他们", "就是", "不是", "因为", "所以", "但是", "如果",
                                 "已经", "以及", "非常", "比较", "可能", "通过", "这些",
                                 "那些", "不会", "对于", "这样", "那个", "怎么", "自己",
                                 "时候", "这种", "还有", "之后", "很多", "一下", "之间",
                                 "使用", "还是", "需要", "一些", "知道", "看到", "觉得",
                                 "目前", "其实", "这样", "这种", "这里", "第一", "应该",
                                 "问题", "回答", "文章", "收藏", "内容", "没有", "可以",
                                 "没有", "不会", "只能", "已经", "那么", "所有", "其中"}
                    top = [(w, c) for w, c in top if w not in stopwords][:30]

                    if top:
                        cols = st.columns(5)
                        for i, (word, count) in enumerate(top):
                            with cols[i % 5]:
                                if st.button(f"{word} ({count})", key=f"kw_{i}"):
                                    st.session_state["search_query"] = word
                                    st.rerun()
                    else:
                        st.info("📭 未提取到关键词")

                except Exception as e:
                    st.caption(f"⚠ 关键词提取失败: {e}")

# ================================================================
# 页面: 主题
# ================================================================
if page == "主题":
    st.markdown('<div class="main-header">📂 主题聚类</div>', unsafe_allow_html=True)

    if not kb_exists:
        st.info("📭 请先运行 `zhihu2obsidian knowledge topics build` 生成主题页")
    else:
        topics_dir = knowledge_path / "topics"
        index_file = topics_dir / "index.json"

        if not index_file.exists():
            st.warning("⚠ 主题页未生成。请运行 `zhihu2obsidian knowledge topics build`")
        else:
            # Store selected topic in session    state
            if "selected_topic" not in st.session_state:
                st.session_state.selected_topic = None

            # Back button when viewing a topic
            if st.session_state.selected_topic:
                if st.button("← 返回主题列表"):
                    st.session_state.selected_topic = None
                    st.rerun()

            if st.session_state.selected_topic:
                # Show single topic detail
                topic_id = st.session_state.selected_topic
                topic_file = topics_dir / f"{topic_id}.json"
                if topic_file.exists():
                    try:
                        topic = json.loads(topic_file.read_text())
                    except Exception:
                        st.error("无法读取主题数据")
                        st.session_state.selected_topic = None
                        st.rerun()
                        topic = {}

                    st.markdown(f'### 📌 {topic.get("title", "")}')
                    kw = ", ".join(topic.get("keywords", []))
                    if kw:
                        st.markdown(f'**🏷 关键词:** {kw}')
                    st.markdown(f'**📄 素材: {topic.get("content_count", 0)} 篇**')
                    if topic.get("source_platforms"):
                        pf_str = ", ".join(topic["source_platforms"])
                        st.markdown(f'**🌐 平台: {pf_str}**')

                    if topic.get("summary"):
                        st.markdown(f'**📝 摘要**\n\n{topic["summary"]}')

                    if topic.get("viewpoints"):
                        st.markdown("**💡 主要观点**")
                        for vp in topic["viewpoints"]:
                            st.markdown(f"- {vp}")

                    if topic.get("counterpoints"):
                        st.markdown("**⚡ 反方观点**")
                        for cp in topic["counterpoints"]:
                            st.markdown(f"- {cp}")

                    if topic.get("writing_ideas"):
                        st.markdown("**✍️ 可写选题**")
                        for wi in topic["writing_ideas"]:
                            st.markdown(f"- {wi}")

                    if topic.get("representative_contents"):
                        st.markdown("**📄 代表素材**")
                        for rc in topic["representative_contents"]:
                            pf = rc.get("platform", "?")
                            title = rc.get("title", "")
                            author = rc.get("author", "")
                            content_id = rc.get("content_id", "")
                            cid = content_id[:40] if content_id else ""
                            if title:
                                st.markdown(f"- [{pf}] {title} — {author}  `{cid}`")

            else:
                # Show topic list
                index = json.loads(index_file.read_text())
                st.markdown(f"共 **{len(index)}** 个主题簇\n")

                for t in index:
                    kw = ", ".join(t.get("keywords", [])[:4]) or "-"
                    pf = ", ".join(t.get("source_platforms", []))
                    with st.container():
                        st.markdown(f'<div class="result-item">', unsafe_allow_html=True)
                        st.markdown(f'### {t.get("title", "")}')
                        st.markdown(f'📄 {t.get("content_count", 0)} 篇  ·  🏷 {kw}  ·  🌐 {pf}')
                        if st.button("查看详情", key=f"topic_{t['id']}"):
                            st.session_state.selected_topic = t["id"]
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)

# ================================================================
# 页面: AI 写作
# ================================================================
if page == "AI 写作":
    st.markdown('<div class="main-header">✍️ AI 写作助手</div>', unsafe_allow_html=True)
    st.markdown("基于知识库素材，辅助撰写知乎回答")

    if not api_key:
        st.warning("⚠️ 请在侧栏设置 DeepSeek API Key 后使用写作功能")
    else:
        col1, col2 = st.columns([3, 1])
        with col1:
            question = st.text_area(
                "你希望回答什么问题？",
                placeholder="例如：AI 会取代程序员吗？",
                height=80,
            )
        with col2:
            style = st.selectbox("风格", ["自然", "专业", "幽默", "结构化"], index=0)
            temperature = st.slider("创造性", 0.0, 1.5, 0.7, 0.1)
            model = st.selectbox("模型", ["deepseek-chat", "deepseek-reasoner"], index=0)

        personal = st.text_area(
            "你的观点（可选）",
            placeholder="补充你自己的经历或观点，AI 会融入回答...",
            height=60,
        )

        use_context = st.checkbox("检索知识库相关素材", value=True)

        generate = st.button("🚀 生成回答", type="primary", use_container_width=True)
        generate_package = st.button("📦 生成素材包", use_container_width=True)

        if generate_package and question:
            with st.spinner("📦 正在组织素材包..."):
                try:
                    from zhihu2obsidian.agent.package import WritingPackageBuilder

                    cards_dir = knowledge_path / "cards" if kb_exists else None
                    if cards_dir and not cards_dir.exists():
                        cards_dir = None
                    topics_dir = knowledge_path / "topics" if kb_exists else None
                    if topics_dir and not topics_dir.exists():
                        topics_dir = None

                    builder = WritingPackageBuilder(
                        api_key=api_key,
                        model=model,
                        retriever=retriever if kb_exists else None,
                        cards_dir=cards_dir,
                        topics_dir=topics_dir,
                    )

                    package = builder.build(
                        topic=question,
                        personal_take=personal or "",
                    )

                    st.markdown("---")
                    st.markdown("### 📦 写作素材包")
                    st.markdown("---")

                    # Core viewpoints
                    if package.core_viewpoints:
                        st.markdown("**💡 核心观点**")
                        for vp in package.core_viewpoints:
                            st.markdown(f"- {vp}")

                    # Argument chain
                    if package.argument_chain:
                        st.markdown("---")
                        st.markdown("**🔗 论据链**")
                        for i, arg in enumerate(package.argument_chain, 1):
                            point = arg.get("point", "")
                            evidence = arg.get("evidence", "")
                            source = arg.get("source_title", "")
                            with st.expander(f"{i}. {point[:60]}..." if len(point) > 60 else f"{i}. {point}"):
                                if evidence:
                                    st.markdown(f"> {evidence}")
                                if source:
                                    st.caption(f"来源: {source}")

                    # Case stories
                    if package.case_stories:
                        st.markdown("---")
                        st.markdown("**📖 案例库**")
                        for cs in package.case_stories:
                            story = cs.get("story", "") if isinstance(cs, dict) else str(cs)
                            source = cs.get("source", "") if isinstance(cs, dict) else ""
                            usage = cs.get("usage", "") if isinstance(cs, dict) else ""
                            st.markdown(f"- {story}")
                            if usage:
                                st.caption(f"💡 {usage}")

                    # Key quotes
                    if package.key_quotes:
                        st.markdown("---")
                        st.markdown("**💬 金句**")
                        for kq in package.key_quotes:
                            quote = kq.get("quote", "") if isinstance(kq, dict) else str(kq)
                            source = kq.get("source", "") if isinstance(kq, dict) else ""
                            st.markdown(f"> {quote}")
                            if source:
                                st.caption(f"— {source}")

                    # Counterpoints
                    if package.counterpoints:
                        st.markdown("---")
                        st.markdown("**⚡ 反方观点**")
                        for cp in package.counterpoints:
                            if isinstance(cp, dict):
                                st.markdown(f"- {cp.get('point', '')}")
                                if cp.get('context'):
                                    st.caption(f"回应思路: {cp['context']}")
                            else:
                                st.markdown(f"- {cp}")

                    # Writing angles
                    if package.writing_angles:
                        st.markdown("---")
                        st.markdown("**✍️ 推荐写作角度**")
                        for wa in package.writing_angles:
                            if isinstance(wa, dict):
                                st.markdown(f"- **{wa.get('angle', '')}**: {wa.get('description', '')}")
                            else:
                                st.markdown(f"- {wa}")

                    # Outline
                    if package.outline:
                        st.markdown("---")
                        st.markdown("**📋 文章大纲**")
                        for section in package.outline:
                            if isinstance(section, dict):
                                title = section.get("title", "")
                                if title:
                                    st.markdown(f"**{title}**")
                                for pt in section.get("points", []):
                                    st.markdown(f"- {pt}")
                            else:
                                st.markdown(f"- {section}")

                    # Sources
                    if package.sources:
                        st.markdown("---")
                        st.markdown("**📚 使用素材**")
                        for s in package.sources:
                            t = s.get("title", s.get("content_id", "?"))
                            a = s.get("author", "")
                            p = s.get("platform", "")
                            st.markdown(f"- [{p}] {t} ({a})")

                    st.markdown("---")
                    st.caption(f"素材包时间: {package.created_at[:19]}")

                except Exception as e:
                    st.error(f"❌ 生成素材包失败: {e}")

        if generate and question:
            with st.spinner("正在生成回答..."):
                try:
                    from zhihu2obsidian.agent.writer import Writer

                    writer = Writer(api_key=api_key, model=model)

                    context = ""
                    if use_context and kb_exists and retriever:
                        ctx_results = retriever.search_with_context(question, n_results=5)
                        if ctx_results:
                            parts = []
                            for cr in ctx_results:
                                title = cr.get("title", "")
                                author = cr.get("author", "")
                                chunks = cr.get("chunks", [])
                                excerpt = ""
                                for ch in chunks:
                                    if ch.get("text", ""):
                                        excerpt = ch["text"][:200]
                                        break
                                if excerpt:
                                    parts.append(f"## {title} ({author})\n\n{excerpt}")
                            context = "\n\n---\n\n".join(parts)

                    answer = writer.write_answer(
                        question=question,
                        context=context,
                        personal_take=personal,
                        temperature=temperature,
                    )

                    st.markdown("---")
                    st.markdown("### 📝 生成结果")
                    st.markdown("---")
                    st.markdown(answer)

                    st.markdown("---")
                    with st.expander("📋 纯文本（复制用）"):
                        st.text_area("", answer, height=200, label_visibility="collapsed")

                    col_a, col_b = st.columns(2)
                    with col_a:
                        safe_title = question[:20].replace("/", "_").replace(" ", "_")
                        st.download_button(
                            "💾 下载为 .md",
                            data=answer,
                            file_name=f"zhihu-answer-{safe_title}.md",
                            mime="text/markdown",
                        )
                    if st.button("🔄 重新生成", use_container_width=True):
                        st.rerun()

                    # 质量检查
                    with st.expander("🔍 质量检查（与知识库相似度分析）"):
                        if st.button("▶️ 运行质量检查", key="run_check", use_container_width=True):
                            with st.spinner("分析中..."):
                                try:
                                    from zhihu2obsidian.agent.checker import WritingChecker

                                    check_retriever = None
                                    if kb_exists:
                                        check_retriever = retriever

                                    checker = WritingChecker(
                                        retriever=check_retriever,
                                        api_key=api_key,
                                    )
                                    report = checker.check(answer, title=question)

                                    # Generate rewrites for flagged paragraphs
                                    if report.flagged_high > 0 and api_key:
                                        checker._generate_rewrite(report.paragraphs)

                                    # Verdict
                                    vmap = {
                                        "good": "✅ 原创度良好",
                                        "needs_revision": "⚠️ 需修改部分段落",
                                        "high_risk": "❌ 高风险",
                                    }
                                    st.markdown(f"**{vmap.get(report.overall_verdict, '?')}**")

                                    col_a, col_b, col_c = st.columns(3)
                                    col_a.metric("总段落", report.total_paragraphs)
                                    col_b.metric("🔴 高相似", report.flagged_high)
                                    col_c.metric("🟡 参考", report.flagged_moderate)

                                    # Per-paragraph results
                                    if report.paragraphs:
                                        st.markdown("---")
                                        st.markdown("**逐段落分析**")
                                        for pc in report.paragraphs:
                                            lmap = {"high": "🔴", "moderate": "🟡", "good": "🟢"}
                                            icon = lmap.get(pc.level, "❓")
                                            src = f" — 匹配: {pc.source_title[:30]}" if pc.source_title else ""
                                            with st.expander(
                                                f"{icon} 段落 {pc.index+1}  (相似度: {pc.max_score:.3f}){src}",
                                                expanded=(pc.flagged),
                                            ):
                                                st.markdown(f"_{pc.text}_")
                                                if pc.rewrite:
                                                    st.markdown("---")
                                                    st.markdown(f"✏️ **建议改写:**\n\n{pc.rewrite}")

                                    # Source coverage
                                    if report.source_coverage:
                                        st.markdown("---")
                                        st.markdown("**📚 素材使用分布**")
                                        for src, cnt in sorted(
                                            report.source_coverage.items(),
                                            key=lambda x: -x[1],
                                        )[:8]:
                                            bar = "█" * min(cnt, 20)
                                            st.markdown(f"`{bar}` {cnt}× {src[:50]}")

                                    if report.overreliance_source:
                                        st.warning(
                                            f"⚠️ 过度依赖单一来源: {report.overreliance_source[:60]} "
                                            f"({report.overreliance_pct}%)"
                                        )

                                except Exception as e:
                                    st.error(f"检查失败: {e}")

                except Exception as e:
                    st.error(f"❌ 生成失败: {e}")

        elif generate:
            st.warning("请先输入问题")

# ================================================================
# 首次使用指引
# ================================================================
if not kb_exists and config:
    st.sidebar.markdown("---")
    st.sidebar.info(
        "**首次使用**\n\n"
        "1. `zhihu2obsidian sync`\n"
        "2. `zhihu2obsidian knowledge build`\n"
        "3. 刷新本页面"
    )
