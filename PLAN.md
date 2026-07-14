# 社交收藏知识树与知乎浏览器助手 · 产品与开发文档

## 1. 产品文档

### 产品定位

把长期积累的知乎、B站、小宇宙等收藏内容整理成本地知识树，并在浏览知乎时提供即时参考：选中一段回答后，系统自动判断它属于你知识树中的哪个话题、有哪些相似素材、可从哪些角度重新组织表达。

产品不是“复制改写器”，而是“个人素材定位 + 写作参考 + 原创化建议”工具。

### 目标用户

核心用户：你本人，重度收藏、长期写作、需要从旧资料中快速找素材。

后续可扩展用户：

- 内容创作者
- 知识管理用户
- 研究型写作者
- 自媒体选题策划者

### 核心场景

1. 清理收藏夹  
   把知乎收藏、B站收藏、播客内容同步到本地 Obsidian/Markdown。

2. 建立知识树  
   系统把已有知识库聚类为几个“原话题”，每个原话题下面有分支、代表素材、核心观点、反方观点、写作角度。

3. 浏览知乎时即时匹配  
   用户在知乎回答页选中一段内容，插件分析该内容，返回它在个人知识树里的位置。

4. 写作参考  
   系统给出相似素材、可借用论据、可展开角度、与原文过近的表达风险、改写建议。

### MVP 功能

- 本地知识库构建：Markdown 分块、向量化、卡片抽取、主题聚类。
- 知识树生成：从现有 topics/cards/chunks 生成稳定树结构。
- 浏览器插件：支持知乎页面选中文本后一键分析。
- 本地服务：插件调用本机 Python API，不上传私人收藏。
- 分析结果：
  - 匹配知识树路径
  - 相似收藏素材
  - 来源标题、作者、平台
  - 可用观点/论据/案例
  - 写作建议
  - 高相似风险提示

### 非目标

- 不做云端同步。
- 不做多人协作。
- 不做自动发布。
- MVP 不生成完整文章，只给素材和建议。
- 不承诺“洗稿避检”，重点是原创化和来源回溯。

### 用户流程

1. 用户运行 CLI 同步收藏。
2. 用户运行知识库构建。
3. 用户运行知识树构建。
4. 用户启动本地分析服务。
5. 用户打开知乎页面。
6. 用户选中回答片段。
7. 插件请求本地服务分析。
8. 插件展示知识树定位和写作建议。

### 插件界面信息架构

插件主面板：

- 当前分析文本摘要
- 最相关知识树路径
- 相似素材列表
- 可用观点
- 可用案例/论据
- 反方观点
- 写作角度
- 相似度风险
- 一键复制素材包

状态页：

- 本地服务是否在线
- 知识库是否已构建
- 知识树节点数
- 向量块数
- DeepSeek API Key 是否可用

### 成功指标

- 选中文本后 3 秒内返回非 LLM 匹配结果。
- 有 API Key 时 10 秒内返回写作建议。
- Top 3 知识树匹配中至少 1 个主观上相关。
- 每条建议都能追溯到来源素材。
- 插件在本地服务关闭时有明确提示，不静默失败。

---

## 2. 开发文档

### 当前项目现状

已有能力：

- Python CLI 同步知乎/B站/小宇宙内容。
- Markdown 输出到 Obsidian。
- ChromaDB 向量知识库。
- 素材卡片抽取。
- KMeans 主题聚类。
- 写作素材包。
- Streamlit 仪表盘。
- 浏览器扩展雏形。

主要缺口：

- 知识树模型未固化。
- 插件还未接入本地知识库。
- 缺少本地 HTTP API。
- 检索结果未统一成插件可消费的结构。
- 主题聚类结果不够稳定，不能直接作为长期知识树。

### 推荐架构

```text
知乎/B站/播客
   ↓
CLI 同步
   ↓
Markdown Vault
   ↓
知识库构建
   ↓
ChromaDB + cards + topics
   ↓
知识树生成
   ↓
本地 API 服务
   ↓
浏览器插件
   ↓
选中文本分析 + 写作建议
```

### 目录规划

建议新增：

```text
cli/zhihu2obsidian/tree/
  model.py          # 知识树数据结构
  builder.py        # 从 topics/cards/chunks 构建树
  overrides.py      # 手动修订规则
  matcher.py        # 文本到知识树节点匹配

cli/zhihu2obsidian/server/
  app.py            # FastAPI 应用
  schemas.py        # API 请求/响应模型
  analyzer.py       # 选中文本分析主流程

extension/
  manifest.json
  background.js
  content.js
  sidebar.html
  sidebar.js
  options.html
  options.js
```

现有根目录插件文件可迁移进 `extension/`，避免和 CLI/Web 混在一起。

### 知识树数据模型

`.knowledge/tree/index.json`：

```json
{
  "version": 1,
  "generated_at": "2026-07-13T00:00:00",
  "nodes": [
    {
      "id": "node_ai_coding",
      "title": "AI 编程工具",
      "summary": "围绕 AI 编程助手、开发者效率、工程实践的内容集合。",
      "keywords": ["AI 编程", "Cursor", "Copilot", "工程效率"],
      "parent_id": null,
      "children": ["node_ai_coding_workflow"],
      "source_topic_ids": ["topic_001"],
      "content_ids": ["answer_123", "bilibili_BVxxx"],
      "representative_chunks": [
        {
          "content_id": "answer_123",
          "title": "如何看待 AI 编程？",
          "author": "作者名",
          "text": "代表片段..."
        }
      ],
      "confidence": 0.82,
      "created_at": "2026-07-13T00:00:00",
      "updated_at": "2026-07-13T00:00:00"
    }
  ]
}
```

手动修订文件 `.knowledge/tree/overrides.yaml`：

```yaml
rename:
  topic_001: "AI 编程工具"

hide:
  - topic_014

merge:
  node_productivity:
    - topic_003
    - topic_008

parent:
  node_cursor_workflow: node_ai_coding
```

### 本地 API

启动命令：

```bash
zhihu2obsidian serve --host 127.0.0.1 --port 8765
```

健康检查：

```http
GET /health
```

返回：

```json
{
  "ok": true,
  "knowledge_ready": true,
  "tree_ready": true,
  "llm_ready": true,
  "chunk_count": 398,
  "tree_node_count": 42
}
```

知识树：

```http
GET /tree
```

选中文本分析：

```http
POST /analyze-selection
```

请求：

```json
{
  "text": "用户在知乎选中的文本",
  "url": "https://www.zhihu.com/question/xxx/answer/yyy",
  "page_title": "页面标题",
  "question_title": "知乎问题标题",
  "author": "回答作者",
  "mode": "reference"
}
```

响应：

```json
{
  "matched_tree_nodes": [
    {
      "node_id": "node_ai_coding",
      "path": ["技术", "AI 编程工具"],
      "title": "AI 编程工具",
      "score": 0.86,
      "reason": "文本讨论 AI 编程效率，与该节点代表素材高度相似。"
    }
  ],
  "similar_sources": [
    {
      "content_id": "answer_123",
      "title": "相关收藏标题",
      "author": "作者名",
      "platform": "zhihu",
      "score": 0.81,
      "quote": "相似原文片段..."
    }
  ],
  "writing_suggestions": [
    "可从“效率提升是否带来能力退化”切入。",
    "建议补充一个个人使用场景，降低与原回答结构相似度。"
  ],
  "risks": [
    {
      "level": "medium",
      "message": "选中文本与 2 条收藏素材表达接近，引用时建议重组论证顺序。"
    }
  ]
}
```

### 分析流程

`SelectionAnalyzer` 主流程：

1. 清洗选中文本。
2. 用 ChromaDB 做语义检索。
3. 聚合同一 `content_id` 的多个 chunk。
4. 匹配知识树节点。
5. 读取相关素材卡片。
6. 读取相关主题页。
7. 生成写作建议。
8. 返回结构化 JSON。

无 API Key 时：

- 返回知识树匹配。
- 返回相似素材。
- 返回基础风险提示。
- 不返回 LLM 生成建议。

有 API Key 时：

- 增加观点提炼。
- 增加改写建议。
- 增加写作角度。
- 增加反方观点提醒。

### 插件设计

Manifest 权限：

- `activeTab`
- `scripting`
- `contextMenus`
- `storage`
- `http://127.0.0.1:8765/*`

触发方式：

- 右键菜单：“用知识库分析选中文本”
- 快捷键
- 页面浮动按钮

内容脚本职责：

- 获取选中文本。
- 获取页面 URL、标题、知乎问题标题、回答作者。
- 发消息给 background。

Background 职责：

- 调用本地 API。
- 处理本地服务不可用错误。
- 打开 sidebar/popup 展示结果。

Sidebar 职责：

- 展示知识树路径。
- 展示相似素材。
- 展示写作建议。
- 提供复制素材包按钮。

### CLI 命令

新增：

```bash
zhihu2obsidian knowledge tree build
zhihu2obsidian knowledge tree list
zhihu2obsidian knowledge tree view node_ai_coding
zhihu2obsidian analyze --text "..."
zhihu2obsidian serve
```

保留现有：

```bash
zhihu2obsidian sync
zhihu2obsidian knowledge build
zhihu2obsidian knowledge topics build
zhihu2obsidian knowledge cards build
zhihu2obsidian search "..."
zhihu2obsidian write "..."
zhihu2obsidian check --text "..."
```

### 测试计划

单元测试：

- 知识树节点生成稳定。
- overrides 生效。
- 文本能匹配正确节点。
- API schema 字段完整。
- 无 API Key 时降级正常。

集成测试：

- 临时 vault 生成知识库。
- 构建知识树。
- 启动本地 API。
- 调用 `/analyze-selection`。
- 验证返回知识树节点和相似素材。

手动测试：

- 知乎回答页选中文本。
- 插件成功调用本地服务。
- 关闭本地服务后插件显示启动提示。
- DeepSeek Key 缺失时仍可定位知识树。
- 高相似文本能显示风险提示。

### 开发阶段

1. 文档与现实对齐  
   把 README 中“已完成”和“计划中”分开。

2. 知识树 v1  
   从现有 topics/cards 生成稳定树结构。

3. 分析引擎  
   实现选中文本到知识树节点的匹配。

4. 本地 API  
   用 FastAPI 暴露 `/health`、`/tree`、`/analyze-selection`。

5. 插件 MVP  
   实现右键选中文本分析和结果面板。

6. 质量增强  
   加测试、错误提示、相似度风险、README 更新。

### 技术默认值

- 浏览器：Chrome/Edge Manifest V3。
- 后端：Python + FastAPI。
- 向量库：ChromaDB。
- 本地优先：所有收藏、索引、知识树保存在本机。
- LLM：继续使用 DeepSeek；无 Key 时可降级。
- 知识树策略：自动生成 + 手动修订。
- 写作建议策略：默认给参考建议，不生成完整草稿。

