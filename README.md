# 📚 创作者知识库 (Creator Knowledge Base)

> 把你的收藏夹变成创作引擎。自动同步知乎/B站收藏 → 向量知识库 → 主题聚类 → AI 写作 + 质量检查。

```text
知乎收藏 ──→ Markdown ──→ ChromaDB 向量索引
B站视频  ──→ AI摘要/字幕 ──→ .knowledge/
                               ├── 主题聚类 (15簇)
                               ├── 素材卡片 (76+张)
                               ├── 知识图谱 (Pyvis)
                               ├── 词云
                               └── ChromaDB (398向量)
                                          └── 语义搜索 → 素材包 → 初稿 → 质量检查
```

## ✨ 功能一览

| 能力 | 详情 |
|---|---|
| **多平台同步** | 知乎收藏夹 + B站收藏视频 + 小宇宙热门播客 |
| **增量同步** | 只同步新内容，已同步的跳过，内容变化自动重新抓取 |
| **向量知识库** | ChromaDB 中文语义搜索，按平台/作者/收藏夹筛选 |
| **素材卡片** | LLM 自动提取：核心观点/论据/案例/金句/反方/写作角度 |
| **主题聚类** | KMeans 自动发现素材中的 15 个主题簇，含摘要/观点/选题 |
| **写作素材包** | 输入问题 → 检索知识库+卡片+主题 → 结构化素材包 → 可选初稿 |
| **质量检查** | 逐段相似度分析，标注高相似段落，自动生成改写建议 |
| **Web 仪表盘** | Streamlit 5 面板：搜索/图谱/词云/主题/写作 |
| **写作机会评分** | 综合素材量+观点+选题，量化每个主题的创作价值 |
| **月度一键同步** | `zhihu2obsidian monthly` → 全平台同步 + 知识库 + 卡片 |
| **隐私优先** | 所有数据存储本地，Cookie 本地管理，API Key 本地配置 |

## 🚀 快速开始

### 前置条件

- Python 3.10+
- 一个知乎账号（用于同步收藏夹）
- 可选：DeepSeek API Key（用于 AI 写作 + 素材卡片 + 主题聚类）

### 安装

```bash
# 克隆项目
git clone git@github.com:paimmme/zhihu2obsidian.git
cd zhihu2obsidian/cli

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 完整安装（知识库 + Web 仪表盘）
pip install -e ".[all]"

# 或最小安装（仅同步导出）
pip install -e .
```

### 首次配置

```bash
# 初始化配置
zhihu2obsidian config init

# 设置 Obsidian vault 路径（或任意输出目录）
zhihu2obsidian config set vault ~/Documents/Obsidian

# 设置 DeepSeek API Key（可选，用于 AI 功能）
zhihu2obsidian config set deepseek_api_key sk-xxx
```

### 获取 Cookie（知乎）

1. 在浏览器打开 `zhihu.com` 并登录
2. 按 F12 打开 DevTools → **Application** → **Cookies** → `www.zhihu.com`
3. 复制 `z_c0` 和 `d_c0` 的值（两个都需要）
4. 导入到 CLI：

```bash
zhihu2obsidian auth login
# 粘贴 z_c0 和 d_c0
```

验证 Cookie 是否有效：

```bash
zhihu2obsidian auth status
# → ✅ zhihu 已登录: 你的用户名
```

### B站 可选配置

```bash
# 获取 SESSDATA（浏览器 DevTools → Application → Cookies → bilibili.com）
zhihu2obsidian auth login --platform bilibili
```

### 同步数据

```bash
# 查看所有收藏夹
zhihu2obsidian list

# 同步全部收藏（首次建议 --limit 5 测试）
zhihu2obsidian sync

# 或指定数量
zhihu2obsidian sync --limit 3
```

### 构建知识库

```bash
# 增量构建（分块 → 向量 → 图谱 → 词云）
zhihu2obsidian knowledge build

# 查询知识库状态
zhihu2obsidian knowledge status
```

### 日常使用

```bash
# 语义搜索
zhihu2obsidian search "AI 编程工具" --platform zhihu --author "飞天红猪侠"

# 生成素材包（需 DeepSeek API Key）
zhihu2obsidian write "古法编程值不值得坚持" --package

# 素材包 + 初稿 + 质量检查
zhihu2obsidian write "从零开始学编程" --package --draft --check

# 单独质量检查（检查已有稿件）
zhihu2obsidian check --file draft.md --rewrite

# 主题聚类
zhihu2obsidian knowledge topics build
zhihu2obsidian knowledge topics list
zhihu2obsidian knowledge topics view topic_006

# 素材卡片管理
zhihu2obsidian knowledge cards build
zhihu2obsidian knowledge cards search "RAG"

# 月度全量同步
zhihu2obsidian monthly
```

### 启动 Web 仪表盘

```bash
cd ..
streamlit run web/app.py
```

然后浏览器打开 `http://localhost:8501` → 5 个面板：
- **🔎 搜索** — 语义搜索 + 平台/作者筛选
- **📊 知识图谱** — 主题筛选 + 写作机会排行
- **☁️ 词云 · 主题机会** — 词云 + 主题评分排行榜
- **📂 主题** — 15 个主题簇详情页
- **✍️ AI 写作** — 素材包生成 + 初稿 + 质量检查

## 📖 CLI 完整参考

### 认证

| 命令 | 说明 |
|---|---|
| `auth login` | 交互式输入知乎 Cookie |
| `auth login --platform bilibili` | B站 Cookie |
| `auth status` | 查看当前 Cookie 状态 |
| `auth import` | 从文件导入 Cookie |

### 同步

| 命令 | 说明 |
|---|---|
| `list` | 列出收藏夹列表 |
| `sync` | 增量同步到 vault |
| `bilibili sync` | 同步 B站 |
| `sync --limit 5` | 限制同步数量 |
| `status` | 查看 vault 状态 |
| `xiaoyuzhou trending` | 小宇宙热门榜 |
| `xiaoyuzhou analyze` | 风格分析 |
| `xiaoyuzhou outline "主题"` | 播客大纲生成 |

### 知识库

| 命令 | 说明 |
|---|---|
| `knowledge build` | 增量构建（分块→向量→图谱→词云） |
| `knowledge rebuild` | 完全重建 |
| `knowledge status` | 知识库状态 |
| `knowledge cards build` | 增量抽取素材卡片 |
| `knowledge cards search "关键词"` | 搜索卡片 |
| `knowledge topics build` | 主题聚类 |
| `knowledge topics list` | 主题列表 |
| `knowledge topics view topic_001` | 查看主题详情 |

### AI 写作

| 命令 | 说明 |
|---|---|
| `write "问题"` | 生成知乎回答 |
| `write "问题" --package` | 生成结构化素材包 |
| `write "问题" --package --draft` | 素材包 + 初稿 |
| `write "问题" --package --draft --check` | 素材包 + 初稿 + 质量检查 |
| `write "问题" --personal "我的观点"` | 融入个人观点 |
| `check --file draft.md` | 检查已有稿件 |
| `check --text "文本" --rewrite` | 检查并生成改写建议 |
| `search "关键词"` | 语义搜索 |
| `search "关键词" --author "人名" --platform zhihu` | 带筛选 |

### 工具

| 命令 | 说明 |
|---|---|
| `config init` | 初始化配置 |
| `config set key value` | 设置配置项 |
| `config show` | 查看配置 |
| `monthly` | 全平台同步 + 知识库 + 卡片一键执行 |

## 🔒 隐私与数据安全

| 关注点 | 说明 |
|---|---|
| **数据存储** | 所有数据存储在你的本地机器，不上传任何云端 |
| **Cookie** | Cookie 文件存储在 `~/.zhihu2obsidian/`，仅用于 API 请求 |
| **API Key** | DeepSeek API Key 存储在本地配置文件中，仅用于直接 API 调用 |
| **AI 请求** | 素材卡片/主题聚类/写作包请求直接发送到 DeepSeek API，**不经过第三方代理** |
| **向量索引** | ChromaDB 在本地运行，嵌入向量不出本地 |
| **来源追踪** | 所有 AI 生成内容均标注素材来源（作者/标题/平台） |
| **相似度检查** | 生成初稿后自动检查与素材库的相似度，高风险段落标红并建议改写 |
| **日志** | 写入 `~/.zhihu2obsidian/logs/`，可随时删除 |

## 📁 输出结构

```
~/Documents/Obsidian/
└── zhihu2obsidian/
    ├── 994375688__我的收藏/           ← 知乎收藏夹 (id__名称)
    │   ├── 标题 - answer_12345.md     ← 单篇内容
    │   └── assets/answer_12345/       ← 图片
    │       └── abcd1234.jpg
    ├── 1003429158__tech/              ← 另一个收藏夹
    │   ├── 标题 - article_67890.md
    │   └── assets/article_67890/
    ├── bilibili/                       ← B站收藏
    │   └── BV1xx__视频标题.md
    ├── .state.json                     ← 增量同步状态
    └── .knowledge/                     ← 知识库
        ├── chroma.sqlite3              ← ChromaDB 向量 (398 维)
        ├── manifest.json               ← 文件哈希 (增量去重)
        ├── graph.html                  ← 交互式知识图谱
        ├── wordcloud.png               ← 词云
        ├── cards/                      ← 素材卡片 (76+)
        │   ├── answer_12345.json
        │   └── manifest.json
        ├── topics/                     ← 主题页 (15 簇)
        │   ├── index.json
        │   ├── topic_001.json
        │   └── ...
        ├── tree/                       ← 知识树 + 手动修订
        │   ├── index.json
        │   └── overrides.yaml
        └── embeddings/                 ← ChromaDB 持久化
```

## 🌳 知识树与浏览器助手

```bash
# 从 topics/cards 生成稳定知识树
zhihu2obsidian knowledge tree build

# 查看知识树
zhihu2obsidian knowledge tree list
zhihu2obsidian knowledge tree view node_topic_001

# 命令行分析一段选中文本
zhihu2obsidian analyze --text "知乎回答片段" --json

# 启动插件调用的本地 API
zhihu2obsidian serve --port 8765
```

浏览器插件在 `extension/` 目录，Chrome/Edge 开发者模式中选择“加载已解压的扩展程序”即可。插件不会读取本地文件，只调用 `http://127.0.0.1:8765`，返回知识树位置、相似素材、写作建议和相似风险。

## ⚙️ 配置文件

`~/.zhihu2obsidian/config.yaml`:

```yaml
# —— 必要 ——
vault: ~/Documents/Obsidian/zhihu2obsidian   # 输出目录
cookie_file: ~/.zhihu2obsidian/cookies.json   # Cookie 文件

# —— 导出 ——
output_prefix: zhihu2obsidian                 # vault 内子目录
rate_limit_min: 1.0                           # 请求间隔 (秒)
rate_limit_max: 3.0
image_concurrency: 3                          # 图片下载并发
collections: []                               # 空 = 全部收藏夹

# —— AI ——
deepseek_api_key: sk-xxx                      # DeepSeek API Key
knowledge_dir:                                # 默认: vault 内 .knowledge
```

## 📦 依赖

| 级别 | 安装方式 | 包含 |
|---|---|---|
| 基础 | `pip install -e .` | 同步 + 导出 (requests, bs4, markdownify) |
| 知识库 | `pip install -e ".[knowledge]"` | 基础 + ChromaDB + 图谱 + 词云 |
| Web | `pip install -e ".[web]"` | 知识库 + Streamlit 仪表盘 + 本地 API |
| 全部 | `pip install -e ".[all]"` | 完整功能 + 开发工具 |
| 最小 | `pip install zhihu2obsidian` | 暂未发布 PyPI |

## 🧩 技术栈

- **语言**: Python 3.10+
- **CLI**: click
- **向量**: ChromaDB + sentence-transformers (all-MiniLM-L6-v2)
- **聚类**: scikit-learn (KMeans)
- **AI**: DeepSeek API
- **可视化**: Pyvis (图谱), wordcloud (词云), Streamlit (仪表盘)
- **解析**: BeautifulSoup4, markdownify
- **平台**: 知乎 API, Bilibili API (WBI 签名), 小宇宙 (xyzrank)

## 🧠 设计理念

1. **增量优先** — 首次全量，后续增量。同步/知识库/卡片/聚类全部支持增量
2. **本地优先** — 除非调用 AI API，所有操作在本地完成
3. **素材溯源** — 每篇生成内容标注素材来源，相似度可检查
4. **AI 辅助，而非替代** — 素材包提供结构，初稿提供起点，改写建议降低重复
5. **CLI 优先，Web 可选** — 核心功能全在 CLI，仪表盘只是可视化增强

## 🗺️ 开发路线

| 里程碑 | 状态 | 内容 |
|---|---|---|
| M0 | ✅ 完成 | 技术验证 (API/Cookie/FS) |
| M1 | ✅ 完成 | CLI MVP (同步/导出) |
| M2 | ✅ 完成 | 知识库 (分块/嵌入/检索) |
| M3 | ✅ 完成 | AI 写作 (素材卡片/搜索/写作) |
| M4 | ✅ 完成 | Streamlit 仪表盘 5 面板 |
| M5 | ✅ MVP | Chrome/Edge 扩展 + 本地 API + 选中文本分析 |
| M6 | ✅ 完成 | 多平台 (B站/小宇宙) |
| M7 | ✅ 完成 | 主题聚类 (KMeans + LLM 主题页) |
| M8 | ✅ 完成 | 写作素材包 (三源检索 + 结构化) |
| M9 | ✅ 完成 | 质量检查 (相似度/改写/来源分析) |
| M10 | ✅ 完成 | 词云/图谱 UI 升级 + 机会评分 |

详情见 [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) 和 [docs/FUTURE_DEVELOPMENT.md](docs/FUTURE_DEVELOPMENT.md)
