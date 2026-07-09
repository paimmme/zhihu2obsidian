# Zhihu → Obsidian 知识库 · 开发文档

## 一、项目概述

从知乎收藏夹到 AI 增强的知识库：**Python CLI 做核心抓取 + ChromaDB 向量存储 + DeepSeek RAG 写作**。

**研究依据**：深入分析了两个同类项目后确定技术路线——
- [JasonJarvan/Zhihu-Collections-MCP](https://github.com/JasonJarvan/Zhihu-Collections-MCP)：Python + markdownify + 图片下载，验证了知乎集合 API 可凭 Cookie 直接调用（无需 x-zse-96 签名）
- [hc-tec/my-collection-skills](https://github.com/hc-tec/my-collection-skills)：Python + CookieCloud + Playwright 降级，验证了 `www.zhihu.com/api/v4/` 端点在纯 Cookie 认证下正常工作

**核心发现**：知乎收藏夹相关的 API 端不要求 x-zse-96 签名，仅需 Cookie + User-Agent + Referer。

**目标用户**：自己。稳定后考虑对外发布。

**MVP 目标**：
- Python CLI 读取 Cookie → 知乎/B站/小宇宙 API → Markdown 写入 Obsidian Vault（已完成 ✅）
- 增量同步 + 图片下载（已完成 ✅）
- 知识库构建：分块 → 向量化 → 知识图谱 → 词云（已完成 ✅）
- 语义搜索（平台/作者/收藏夹筛选）+ DeepSeek AI 写作（核心就绪，需 API Key）
- Streamlit 可视化仪表盘（已完成 ✅）

**长期方向**：
- 素材卡片 → 主题聚类 → 写作素材包
- 知识图谱升级为观点关系图（Cytoscape.js / Sigma.js）
- 相似度检查 + 来源追踪
- 本地应用打包（Tauri / Electron）

---

## 二、架构概览

```
┌─ Python CLI (zhihu2obsidian) ─────────────────────────────────────────────────────┐
│                                                                                    │
│  ┌ Platforms ─────────────────────────────────────────────────────┐                │
│  │  zhihu/ (知乎 API) │ bilibili/ (B站 WBI) │ xiaoyuzhou/ (公开)  │                │
│  └─────────────────────────────────────────────────────────────────┘               │
│         ↓                                                                           │
│  ┌─────────┐   ┌──────────┐   ┌───────────┐   ┌──────────────────────┐             │
│  │ auth.py │→│ api.py  │→│ sync.py │→│ .md + .jpg         │             │
│  │ Cookie  │   │ requests │   │ 增量引擎  │   │ Obsidian Vault       │             │
│  └─────────┘   └──────────┘   └─────┬─────┘   └──────────────────────┘             │
│                                     │                                              │
│                              ┌──────▼──────────────────┐                            │
│                              │  知识库构建              │                            │
│                              │                         │                            │
│                              │  chunker.py (分块+去重)  │                            │
│                              │       ↓                 │                            │
│                              │  embedder.py (ChromaDB) │→ 向量存储 / manifest       │
│                              │       ↓                 │                            │
│                              │  graph.py (NetworkX)    │→ graph.html                │
│                              │       ↓                 │                            │
│                              │  wordcloud.py (jieba)   │→ wordcloud.png             │
│                              └─────────────────────────┘                            │
│                                                                                    │
│  ┌─ AI 写作 ───────────────────────────────────────────────────────────┐          │
│  │  retriever.py (语义搜索+平台筛选) → writer.py (DeepSeek API) → 回答  │          │
│  └──────────────────────────────────────────────────────────────────────┘          │
│                                                                                    │
│  ┌─ Streamlit 仪表盘 ───────────────────────────────────────────────┐             │
│  │  知识图谱 / 词云 / 语义搜索 / AI 写作                               │             │
│  │  web/app.py — 4 面板，平台图标，元数据筛选                          │             │
│  └────────────────────────────────────────────────────────────────────┘              │
│                                                                                    │
│  CLI: sync │ search --platform │ write │ knowledge build │ auth status --platform  │
│       list │ bilibili sync │ xiaoyuzhou analyze │ streamlit                        │
└───────────────────────────────────────────────────────────────────────────────────┘
```

---

## 三、关键技术决策

### 3.1 为什么选 Python CLI

| 方面 | 纯扩展方案问题 | Python CLI 方案 |
|---|---|---|
| 知乎 API 认证 | Service Worker fetch 上下文异常，反复 401 | ✅ `requests` 直接带 Cookie，已验证 |
| HTML→Markdown | turndown.js 需 vendored 手动维护 | ✅ `markdownify` 成熟库，可继承定制 |
| 图片下载 | Service Worker + FS API，复杂 | ✅ `requests` + `open()` 直接写入 |
| 增量同步 | IndexedDB 扩展内状态，CLI 不可见 | ✅ `.state.json` 文件，天然持久 |
| 向量知识库 | 浏览器 IndexedDB 不适合 embedding | ✅ ChromaDB 本地文件存储 |
| AI 写作 | 扩展内调 API 受 CSP 限制 | ✅ Python 直接 HTTP 调用 |
| 安装代价 | ✅ 加载扩展即可用 | ❌ 需要 Python + pip install |
| 调试便利 | Service Worker 排查困难 | ✅ 终端直接运行，日志清晰 |

### 3.2 Cookie 方案

**绝不依赖 Chrome 扩展写入本地文件系统**。采用手动导入方案：

| 优先级 | 方式 | 状态 |
|---|---|---|
| 1 (MVP) | `zhihu2obsidian auth login` 交互式输入 | ✅ 已实现 |
| 2 (MVP) | 从 DevTools 复制 Cookie → 保存为 JSON 文件 | ✅ 已验证 |
| 3 (M4) | Chrome 扩展触发下载 `.json` 文件，用户手动保存 | 计划中 |

Cookie 文件格式 (`~/.zhihu2obsidian/cookies.json`)：
```json
{ "d_c0": "xxx...", "z_c0": "2|1:0|..." }
```

### 3.3 认证策略（x-zse-96 分析）

两个参考项目均证实：**知乎收藏夹相关 API 不要求 x-zse-96 签名**。

| 端点 | 认证 | 状态 |
|---|---|---|
| `GET /api/v4/people/{token}/collections` | Cookie ✅ | 已验证 |
| `GET /api/v4/collections/{id}/contents` | Cookie ✅ | 已验证 |
| `GET /api/v4/answers/{id}?include=content` | Cookie ✅ | 已验证 |
| `GET /api/v4/articles/{id}` | Cookie ⚠ 可能 403 | HTML 降级 |
| `GET zhuanlan.zhihu.com/p/{id}` | Cookie ✅ HTML 爬取 | 已验证 |

**不需要实现 x-zse-96 签名算法。**

### 3.4 Markdown 转换

使用 `markdownify` 1.2.3 定制 `ObsidianConverter`：

```python
ObsidianConverter(MarkdownConverter):
  convert_img  → ![[assets/content_id/hash.ext]]
  convert_a    → [text](url)
  convert_h    → ATX 风格 ##
```

输出格式（已验证 ✅）：
```markdown
---
title: "问题标题"
author: "作者名"
url: "https://..."
collection: "收藏夹名"
collection_id: 123456
content_type: "answer"
content_id: "answer_123456"
created: "2026-07-09"
exported_at: "2026-07-09T12:00:00"
tags:
  - zhihu
  - 收藏夹名
---

> 来源: https://...

# 问题标题

> 回答 by [作者名](https://...)

正文...

![[assets/answer_123456/abcd1234ef567890.jpg]]

---
原文链接：[标题](https://...)
```

### 3.5 图片处理

| 维度 | 决策 |
|---|---|
| 文件名 | `{url_hash}.{ext}` (MD5 前 16 位) |
| 目录 | `assets/{content_id}/{hash}.{ext}` |
| 引用 | `![[assets/content_id/hash.ext]]` |
| 去重 | 同一 content_id 内按 hash 检查 |
| 防盗链 | `Referer: https://www.zhihu.com/` |

### 3.6 增量同步模型

`.state.json` 文件存储在 vault 内知识库根目录。

```json
{
  "version": 2,
  "collections": {
    "26444956": {
      "title": "产品思维",
      "output_dir": "26444956__产品思维",
      "items": {
        "answer_123456": {
          "url": "https://...",
          "title": "标题",
          "file_path": "26444956__产品思维/标题 - answer_123456.md",
          "content_hash": "sha256:...",
          "updated_time": 1705312345,
          "content_version": 1,
          "exported_at": "2026-07-09T12:00:00"
        }
      }
    }
  }
}
```

**增量判断**（三字段联合）：
1. `content_hash` — 完整 Markdown 的 SHA-256（检测正文、作者、图片等任何变化）
2. `updated_time` — 知乎 API 返回的更新时间
3. `content_version` — 单调递增的版本号

**同步逻辑**：
- 本地无此 `content_id` → 新增
- `content_hash` 或 `updated_time` 变化 → 更新
- 完全匹配 → 跳过

**条目从收藏夹消失**：标记 `archived: true`，**不删除文件**。

### 3.7 M2 知识库构建

#### 分块策略

| 参数 | 值 |
|---|---|
| 默认块大小 | 500 字符，段落级切分 |
| 重叠 | 80 字符，句子边界中断 |
| 最小块 | 80 字符（过滤噪音片段） |
| 分块依据 | `#` / `##` / `###` 标题 → 段落 |
| 元数据保留 | title, url, author, collection, content_id, section, platform, content_hash |
| 去重 | 同一内容出现在多个收藏夹 → `目录名__content_id` 前缀 |

#### 增量构建（内容哈希 + 文件哈希双重追迹）

```
manifest.json:
  files[rel_path].hash        = SHA256(file)     # 文件级变更检测
  files[rel_path].chunk_ids   = [id1, id2, ...]  # ChromaDB 向量 ID
  files[rel_path].hashes      = [h1, h2, ...]    # chunk 内容哈希（去重）
  _chunk_hashes               = [h1, h2, ...]    # 全局去重索引

流程:
  1. get_changed_files() → 对比文件哈希 → 返回 changed + removed
  2. removed → remove_by_content_id() → 清理 ChromaDB + manifest
  3. changed → 逐文件分块 → remove_by_content_id(旧) → add_chunks(新, rel_path)
  4. update_file_hashes() → 记录新文件哈希
  5. chunk_all_markdowns() → 全量分块 (供图图谱/词云，不改变向量)
```

文件未变更 = 0 向量操作 (~2s 完成全局验证)。文件删除后旧 chunk 自动清理，不可搜索。

#### Embedding 策略

| 优先级 | 引擎 | 模型 | 场景 |
|---|---|---|---|
| 1 | ChromaDB ONNX (内置) | all-MiniLM-L6-v2 | ✅ 默认（已验证） |
| 2 | sentence-transformers | BAAI/bge-small-zh-v1.5 | 中文更准（需下载模型） |
| 3 | 递归 fallback | — | 无依赖可用 |

当前使用 ChromaDB 内置 ONNX 模型（all-MiniLM-L6-v2, 384维, 余弦距离），首次自动下载 79MB。中文精度可接受，如需更好的中文效果安装 BGE-small-zh（HuggingFace 模型，需翻墙或手动下载）。

#### 知识图谱

- 引擎：NetworkX（图构建）+ Pyvis（可视化）
- 节点类型：content（文章/回答）、author（作者）、collection（收藏夹）、section（章节）
- 边类型：authored_by、belongs_to、has_section
- 输出：HTML 力导向图（交互式，可缩放/悬停/拖拽）

#### 词云

- 分词：jieba
- 过滤：停用词表 + 长度 > 1
- 输出：1200×600 PNG

### 3.8 M3 AI 写作

#### 语义检索

- 查询 → ChromaDB cosine similarity 搜索
- 支持按平台 (`--platform zhihu/bilibili/xiaoyuzhou`)、作者 (`--author`)、收藏夹 (`--collection`) 筛选
- 按 content_id 去重，仅返回最佳匹配 chunk
- 加权：摘要/大纲 +0.06，字幕 -0.03
- 最大距离过滤：score < 0.25 不返回
- `--flat` 参数保留原始所有匹配 chunk（不分组去重）

#### DeepSeek 写作

```python
SYSTEM_PROMPT = """你是一位知乎答主，根据参考素材生成知乎回答。
要求：风格自然、接地气，不是 AI 文风
融入自己的观点（如果有提供）
引用素材观点，但不照搬
**粗体** 强调核心观点
口语化但逻辑清晰"""

WRITE_PROMPT = """
问题/主题：{question}
参考素材：{context}
个人观点：{personal_take}
"""
```

- 模型：deepseek-chat
- 温度：0.7（默认可调）
- 响应长度：2048 tokens
- 支持 --raw（纯文本输出）、--copy（剪贴板复制）

---

## 四、技术栈

### Python CLI

| 层 | 技术 | 说明 |
|---|---|---|
| 语言 | Python 3.10+ | |
| HTTP | `requests` | 已验证 |
| HTML 解析 | `beautifulsoup4` + `lxml` | 降级用 |
| Markdown | `markdownify` 1.2.3 | 定制子类 |
| 配置 | `PyYAML` | |
| 向量存储 | `chromadb` 0.5+ | ONNX 内置 |
| 图谱 | `networkx` + `pyvis` | |
| 词云 | `wordcloud` + `jieba` | |
| AI | DeepSeek API (`deepseek-chat`) | |
| 测试 | `pytest` + `responses` | |
| 打包 | pip (`pyproject.toml`) | |

安装方式：
```bash
pip install zhihu2obsidian[all]       # 全部（含 dev）
pip install zhihu2obsidian[knowledge] # 仅知识库
pip install zhihu2obsidian            # 仅导出核心
```

### Chrome 扩展（M4 规划）

| 层 | 技术 |
|---|---|
| 语言 | JavaScript (ES2022+) |
| 版本 | Manifest V3 |
| Cookie | `chrome.cookies.get()` |
| FS 选择 | `showDirectoryPicker()` |
| 持久化 | `chrome.storage.local` |

---

## 五、目录结构

```
zhihu2obsidian/
├── cli/
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── zhihu2obsidian/
│   │   ├── __init__.py
│   │   ├── __main__.py          ← CLI 入口（含多平台调度）
│   │   ├── config.py            ← 配置管理
│   │   ├── auth.py              ← Cookie 管理
│   │   ├── api.py               ← 知乎 API
│   │   ├── converter.py         ← Markdown 转换
│   │   ├── images.py            ← 图片下载
│   │   ├── sync.py              ← 同步引擎（知乎）
│   │   ├── models.py            ← 数据类
│   │   ├── platforms/           ← 平台适配器
│   │   │   ├── base.py          ← Platform ABC
│   │   │   ├── zhihu.py         ← 知乎适配器
│   │   │   ├── bilibili.py      ← B站适配器
│   │   │   ├── bilibili_content.py  ← B站字幕/AI总结
│   │   │   └── xiaoyuzhou.py    ← 小宇宙适配器
│   │   ├── knowledge/           ← 知识库
│   │   │   ├── __init__.py
│   │   │   ├── chunker.py       ← 文本分块 + 去重
│   │   │   ├── embedder.py      ← ChromaDB + manifest
│   │   │   ├── graph.py         ← 知识图谱
│   │   │   └── wordcloud.py     ← 词云
│   │   ├── agent/               ← AI 写作
│   │   │   ├── __init__.py
│   │   │   ├── retriever.py     ← 语义检索（分组+筛选+加权）
│   │   │   └── writer.py        ← DeepSeek 写作
│   └── tests/                   ← ⏳ 测试框架（计划中）
│       └── ...
│
├── extension/                   ← 辅助扩展 (M4 规划)
│   ├── manifest.json
│   ├── popup.html / popup.js
│   └── background.js
│
├── edge/                        ← Edge 版
│   └── manifest.json
│
├── docs/
│   └── api-samples/             ← API 脱敏样本
│
├── DEVELOPMENT_PLAN.md
└── README.md
```

---

## 六、CLI 命令设计

### 配置
```bash
zhihu2obsidian config init                        # 创建默认配置
zhihu2obsidian config set vault /path/to/vault    # 设置 vault 路径
zhihu2obsidian config set deepseek_api_key sk-xxx # 设置 DeepSeek API Key
zhihu2obsidian config show                        # 查看配置
```

### 认证
```bash
zhihu2obsidian auth login           # 交互式输入 Cookie
zhihu2obsidian auth import file     # 导入 Cookie 文件
zhihu2obsidian auth status          # 检查 Cookie 是否有效
```

### 导出
```bash
zhihu2obsidian list                             # 列出当前平台收藏夹
zhihu2obsidian list --platform bilibili          # 列出 B站 收藏夹
zhihu2obsidian sync                             # 增量同步全部（默认知乎）
zhihu2obsidian sync --platform bilibili          # 同步 B站 收藏夹
zhihu2obsidian sync --id 12345                  # 同步指定收藏夹
zhihu2obsidian sync --dry-run                   # 预览模式
zhihu2obsidian sync --limit 10                  # 限制条数
zhihu2obsidian sync --force                     # 强制重新导出
zhihu2obsidian status                           # 同步状态
```

### B站 专项
```bash
zhihu2obsidian bilibili list                    # 列出 B站 收藏夹
zhihu2obsidian bilibili sync                    # 同步 B站 收藏夹
```

### 小宇宙
```bash
zhihu2obsidian xiaoyuzhou trending              # 热门榜单（TOP 20）
zhihu2obsidian xiaoyuzhou analyze               # 风格分析报告
zhihu2obsidian xiaoyuzhou outline "主题"        # 生成播客大纲
```

### 知识库
```bash
zhihu2obsidian knowledge build      # 增量构建（只处理变更）
zhihu2obsidian knowledge rebuild    # 全量重建
zhihu2obsidian knowledge status     # 知识库统计
```

### AI 写作（搜索 + 生成）
```bash
zhihu2obsidian search "query"                            # 语义搜索（去重+加权）
zhihu2obsidian search "query" --platform bilibili         # 仅 B站
zhihu2obsidian search "query" --author "作者"             # 按作者筛
zhihu2obsidian search "query" --collection "收藏夹"       # 按收藏夹筛
zhihu2obsidian search "query" --flat                      # 不分组去重
zhihu2obsidian search "query" --n 10                      # 返回条数
zhihu2obsidian write "主题"                                # 生成知乎回答
zhihu2obsidian write "主题" --personal "我的观点"
zhihu2obsidian write "主题" --no-context                  # 仅 AI 不参考知识库
zhihu2obsidian write "主题" --raw                          # 纯文本输出
zhihu2obsidian write "主题" --copy                         # 复制到剪贴板
```

---

## 七、输出结构

```
~/Documents/Obsidian/
└── zhihu2obsidian/                      ← 可配置前缀
    ├── 994375688__我的收藏/              ← {collection_id}__{safe_title}
    │   ├── 标题 - answer_123456.md      ← {safe_title} - {content_id}.md
    │   ├── ...
    │   └── assets/
    │       └── answer_123456/           ← {content_id}/
    │           ├── abcd1234ef567890.jpg ← {url_hash}.{ext}
    │           └── ...
    ├── .state.json                      ← 增量同步状态
    └── .knowledge/                      ← M2 知识库（隐藏目录）
        ├── chroma.sqlite3               ← 向量存储 (ChromaDB)
        ├── graph.html                   ← 交互式知识图谱
        └── wordcloud.png               ← 词云
```

---

## 八、API 端点

| 端点 | 用途 | 认证 | 状态 |
|---|---|---|---|
| `GET /api/v4/people/{url_token}/collections` | 收藏夹列表 | Cookie ✅ | 已验证 |
| `GET /api/v4/collections/{id}/contents` | 收藏夹内容 | Cookie ✅ | 已验证 |
| `GET /api/v4/answers/{id}?include=content` | 回答详情 | Cookie ✅ | 已验证 |
| `GET /api/v4/articles/{id}` | 文章详情 | Cookie ⚠ | 可能 403 |
| `GET zhuanlan.zhihu.com/p/{id}` | 专栏 HTML | Cookie ✅ | 降级方案 |
| `GET www.zhihu.com/question/{q}/answer/{a}` | 回答 HTML | Cookie ✅ | 降级方案 |

---

## 九、开发里程碑与完成状态

### M0 — 技术验证 ✅ 已完成

| 验证项 | 状态 | 说明 |
|---|---|---|
| Python + Cookie 调用收藏夹 API | ✅ | `requests` 直连 `www.zhihu.com/api/v4/` |
| 收藏夹列表/内容/回答三类接口 | ✅ | 发现 `/items` 与 `/contents` 结构差异，用 `/contents` ✅ |
| Markdown 转换质量 | ✅ | markdownify 定制子类，图片 `![[path]]` 正确 |
| 文件系统写入 + 图片下载 | ✅ | 21 条内容 + 35 张图片一次成功 |
| 增量同步原型 | ✅ | content_hash 对比，21 条跳过零失败 |

### M1 — CLI MVP ✅ 已完成

| 功能 | 状态 |
|---|---|
| `zhihu2obsidian list` | ✅ |
| `zhihu2obsidian sync --limit N` | ✅ |
| Cookie 管理 (`auth login`, `auth import`) | ✅ |
| 图片下载 + `![[assets/content_id/hash.ext]]` | ✅ |
| frontmatter 输出 | ✅ |
| 增量同步 | ✅ |
| pytest 框架 + fixtures | ⏳ （已计划，未编写） |

### M2 — 知识库 ✅ 已完成

| 功能 | 状态 | 说明 |
|---|---|---|
| 中文分块 (chunker.py) | ✅ | 按标题+段落，重叠，元数据保留 |
| ChromaDB 向量存储 (embedder.py) | ✅ | ONNX 内置模型 (all-MiniLM-L6-v2) |
| 知识图谱 (graph.py) | ✅ | NetworkX + Pyvis HTML |
| 词云 (wordcloud.py) | ✅ | jieba + WordCloud, 1200×600 PNG |
| `knowledge build` 一键构建 | ✅ | 115 个块 → 向量 → 图谱 → 词云 |

### M3 — AI 写作 ✅ 已完成

| 功能 | 状态 | 说明 |
|---|---|---|
| 语义搜索 (retriever.py) | ✅ | 分组去重+平台筛选+加权排序+最大距离过滤 |
| 搜索筛选器 | ✅ | `--platform` / `--author` / `--collection` / `--flat` |
| DeepSeek 写作 (writer.py) | ✅ | deepseek-v4-flash 实际测试通过 |
| CLI `search` / `write` | ✅ | 命令已注册，端到端验证 |
| 素材卡片抽取 | ✅ | `knowledge cards build` — 76 张 LLM 结构化卡片 |
| 卡片搜索 | ✅ | 关键词匹配（观点/论据/案例/标签）|
| 月度同步 | ✅ | `monthly` — 全平台 + 知识库 + 卡片一键执行 |

### M4 — Streamlit 可视化仪表盘 ✅ 已完成

| 功能 | 状态 |
|---|---|
| 知识图谱交互式浏览 | ✅ Pyvis 力导向图 iframe |
| 词云展示 | ✅ 1200×600, 中文字体 |
| 语义搜索面板 | ✅ 含平台/作者/收藏夹筛选 |
| AI 写作面板 | ✅ 输入问题→选素材→生成 |
| DeepSeek Key 侧边栏 | ✅ 可在线保存 |
| 知识库重建按钮 | ✅ |
| 4 面板 Tab | ✅ 知识图谱 / 词云 / 搜索 / 写作 |

### M5 — Chrome 扩展辅助 ⏳ 计划中（优先级降低）

| 功能 | 说明 |
|---|---|
| Cookie 导出 | 扩展读取 → 触发下载（手动导入已够用） |
| Vault 目录选择 | FS Access API |
| 同步状态 UI | 进度展示 |

### M6 — 多平台扩展 ✅ 已完成核心 + 部分深入

| 功能 | 状态 | 说明 |
|---|---|---|
| **知乎适配器** | ✅ | Cookie 认证，收藏夹列表/内容/回答/文章 |
| **B站适配器** | ✅ | SESSDATA 认证，收藏夹/视频/专栏 |
| B站 CC 字幕 + AI 总结 | ✅ | WBI 签名，全文逐字稿+分段大纲 |
| **小宇宙适配器** | ✅ | 零认证，公开榜单+风格分析+播客大纲生成 |
| 平台 adapter 框架 | ✅ | ABC + registry + `--platform` CLI |
| 跨平台统一知识库 | ✅ | 所有平台共享 ChromaDB 索引 |
| 图文平台（小红书/抖音） | 🗓️ | 需要登录或付费 API

---

## 十、项目配置

`~/.zhihu2obsidian/config.yaml`:

```yaml
# —— 必要 ——
vault: ~/Documents/Obsidian/
cookie_file: ~/.zhihu2obsidian/cookies.json

# —— 导出 ——
output_prefix: zhihu2obsidian
rate_limit_min: 1.0
rate_limit_max: 3.0
image_concurrency: 3
collections: []              # 空 = 全部

# —— AI ——
deepseek_api_key: sk-xxx     # DeepSeek API Key
knowledge_dir:               # 默认: vault 内 .knowledge
```

---

## 十一、风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 知乎 API 增加 x-zse-96 要求 | 集合 API 失效 | HTML 爬取降级，最坏 Playwright |
| 知乎 HTML 结构变更 | BeautifulSoup 失败 | pytest fixture 检测回归 |
| 网络阻断 (GFW) | HuggingFace 模型下载失败 | ChromaDB 内置 ONNX 模型（已验证可用），BGE-small-zh 可手动下载 |
| z_c0 Cookie 过期 | 认证失败 | CLI 报明确错误；可一键重新导入 |
| 图片防盗链 | 图片 403 | Referer header |
| 同名图片覆盖 | 文件+引用不一致 | URL hash + 子目录隔离 |
| 收藏夹改名 | 新旧目录混乱 | 目录名含 id 前缀，不追溯历史 |

---

## 十二、当前进度总结

```
M0 技术验证  ████████████████████████████ ✅
M1 CLI MVP   ████████████████████████████ ✅
M2 知识库    ████████████████████████████ ✅
M3 AI 写作   ████████████████████████████ ✅
M4 仪表盘    ████████████████████████████ ✅
M5 扩展      ░░░░░░░░░░░░░░░░░░░░░░░░░░░ ⏳ (降低优先级)
M6 多平台    ████████████████████████████ ✅
M7 主题聚类  ████████████████████████████ ✅
M8 素材包    ████████████████████████████ ✅
M9 质量检查  ████████████████████████████ ✅
M10 可视升级 ████████████████████████████ ✅
```

**推广准备**（FUTURE_DEVELOPMENT.md 阶段 6）：
1. ✅ 完整 README（安装/配置/使用/隐私/技术栈）
2. ✅ install.sh 安装脚本
3. ✅ 隐私与数据安全说明
4. ✅ 来源追踪 + 相似度检查能力（M9）
5. ⏳ Demo 视频
6. ⏳ PyPI 发布
