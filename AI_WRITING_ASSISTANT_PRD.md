# 用知识库生成格式感知回答 — 产品设计文档

> 目标：基于 zhihu2obsidian 知识库，构建一个**格式策略** AI 写作助手，帮助用户规划如何组织回答，而不是替用户写出完整回答。

---

## 0. 产品定位

两个产品（本 PRD 覆盖#1）：

| # | 产品 | 定位 | 输给用户什么 | Phase |
|---|---|---|---|---|
| 1 | **写作策略助手** | 写作前的格式参谋 | 问题分析 + 推荐方案 + 素材包 + 大纲 | Phase 1/2 |
| 2 | **自动草稿生成器** | 减少从策略到初稿的执行成本 | 完整回答草稿 | 未来 |

**写作策略助手的核心理念**：不替用户写。给用户策略、格式参考、素材组织，帮用户做出更好的写作决策。用户自己写出来的回答，质量高于 AI 代笔，且保留个人风格。

### 策略助手不做的事

- ❌ 生成完整回答草稿
- ❌ 自动寻找/生成配图
- ❌ 未经用户触发就调用 LLM

### Phase 1 边界

- 写作格式知识库（7 个模块，schema 定义）
- `question analyze`（问题分析 CLI）
- `write-smart --outline`（格式策略 + 大纲生成，不含完整正文）
- `/question-analysis` API（供插件调用）
- 本地知识库 + 格式指南 → 结构化建议输出
- 显式触发（CLI / 右键菜单 / 快捷键）

---

## 1. 用户故事

| 角色 | 行为 | 价值 |
|---|---|---|
| 我 | 在知乎看到一个问题，右键 → "分析回答策略" | 快速获得回答策略 + 素材路线 |
| 我 | CLI 输入问题 + `--outline`，得到带格式的写作策略 | 写作前心中有谱 |
| 我 | 拿到策略后按建议写回答，策略不干预具体措辞 | 保留个人风格，同时也参考了格式指导 |
| 我 | 遇到类似问题时，策略助手记得我偏好的文风 | 越用越顺 |

---

## 2. 核心功能

### 2.1 写作格式知识库

结构化指导集合，安装在 `cli/zhihu2obsidian/writing_guide/templates/`（repo 内、版本受控）。

用户可在 `.knowledge/writing-guide/overrides.yaml` 中覆盖/增补。

#### 2.1.1 问题类型分类（`question_types.yaml`）

```yaml
# Schema 定义
question_types:
  - id: string                # 唯一标识（如 opinion_debate）
    name: string              # 中文名（如 观点讨论型）
    detection:
      patterns: string[]      # 正则/关键词模式
      min_confidence: float   # 需要达到的最低置信度才启用自动选择
    characteristics:
      typical_structure: string[]  # 推荐结构列表（带优先级权重）
      typical_style: string[]      # 推荐文风列表（带优先级权重）
      typical_arc: string[]        # 推荐情绪曲线
      tone: string             # 基调（严肃/轻松/温暖/犀利/中立）
      length_estimate: string  # 预估长度建议
      avoid: string[]          # 禁忌做法
    conflict:
      priority: int            # 类型重叠时，按 priority 排序取高者
```

例：

```yaml
question_types:
  - id: opinion_debate
    name: 观点讨论型
    detection:
      patterns:
        - "你怎么看"
        - "你支持"
        - "你同意"
        - "如何看待"
        - "?what.*think"
      min_confidence: 0.7
    characteristics:
      typical_structure:
        - structure_id: opinion_evidence_counter_close
          weight: 10
        - structure_id: pro_con_conclusion
          weight: 7
      typical_style:
        - style_id: analytical
          weight: 10
        - style_id: sharp
          weight: 6
      typical_arc:
        - arc_id: persuade
      tone: 中立/犀利
      length_estimate: "1200-2000字"
      avoid:
        - 只讲个人感受不讲逻辑
        - 回避反方观点
    conflict:
      priority: 5

  - id: experience_share
    name: 经验分享型
    detection:
      patterns:
        - "有什么经验"
        - "怎么做到的"
        - "如何.*学习"
        - "怎样.*提升"
      min_confidence: 0.7
    characteristics:
      typical_structure:
        - structure_id: background_method_tips
          weight: 10
        - structure_id: story_reflect_advice
          weight: 8
      typical_style:
        - style_id: storytelling
          weight: 10
        - style_id: warm
          weight: 7
      typical_arc:
        - arc_id: empathize_inspire
      tone: 亲切/诚恳
      length_estimate: "1500-3000字"
      avoid:
        - 只列方法不给理由
        - 过度炫耀
    conflict:
      priority: 5

  - id: phenomenon_analysis
    name: 现象分析型
    detection:
      patterns:
        - "为什么会出现"
        - "原因是什么"
        - "说明了什么"
        - "背后.*逻辑"
        - "趋势"
      min_confidence: 0.7
    characteristics:
      typical_structure:
        - structure_id: phenomenon_cause_effect_trend
          weight: 10
        - structure_id: data_interpretation_inference
          weight: 8
      typical_style:
        - style_id: analytical
          weight: 10
        - style_id: professional
          weight: 7
      typical_arc:
        - arc_id: surprise_understand
      tone: 冷静/客观
      length_estimate: "1500-2500字"
      avoid:
        - 归因单一
        - 情绪化判断
    conflict:
      priority: 4

  - id: knowledge_explain
    name: 知识科普型
    detection:
      patterns:
        - "什么是"
        - "如何理解"
        - "是什么原理"
        - "怎么解释"
      min_confidence: 0.7
    characteristics:
      typical_structure:
        - structure_id: analogy_intro_layer_conclusion
          weight: 10
        - structure_id: what_why_how
          weight: 9
      typical_style:
        - style_id: storytelling
          weight: 8
        - style_id: professional
          weight: 10
      typical_arc:
        - arc_id: surprise_understand
      tone: 耐心/清晰
      length_estimate: "1000-2000字"
      avoid:
        - 堆砌术语不给类比
        - 跳过基础直接讲深
    conflict:
      priority: 3

  - id: controversy_evaluation
    name: 争议评价型
    detection:
      patterns:
        - "值不值得"
        - "好不好"
        - "有没有用"
        - "值得.*吗"
        - "是不是智商税"
      min_confidence: 0.7
    characteristics:
      typical_structure:
        - structure_id: pro_con_conclusion
          weight: 10
        - structure_id: opinion_evidence_counter_close
          weight: 8
      typical_style:
        - style_id: analytical
          weight: 10
        - style_id: sharp
          weight: 7
      typical_arc:
        - arc_id: persuade
      tone: 客观/犀利
      length_estimate: "1500-2500字"
      avoid:
        - 只看单边证据
        - 绝对化断言
    conflict:
      priority: 6

  - id: emotional_resonance
    name: 情感共鸣型
    detection:
      patterns:
        - "有没有同感"
        - "怎么办"
        - "有谁.*一样"
        - "好难"
        - "迷茫"
      min_confidence: 0.65
    characteristics:
      typical_structure:
        - structure_id: empathize_share_inspire
          weight: 10
      typical_style:
        - style_id: warm
          weight: 10
        - style_id: storytelling
          weight: 9
      typical_arc:
        - arc_id: empathize_inspire
      tone: 温暖/有力量
      length_estimate: "800-1500字"
      avoid:
        - 说教
        - 比较痛苦
        - 强行正能量
    conflict:
      priority: 3

  - id: data_driven
    name: 数据论证型
    detection:
      patterns:
        - "数据说明"
        - "统计显示"
        - "数据显示"
        - "占比|增长率|下降.*%"
      min_confidence: 0.7
    characteristics:
      typical_structure:
        - structure_id: data_interpretation_inference
          weight: 10
      typical_style:
        - style_id: analytical
          weight: 10
        - style_id: professional
          weight: 9
      typical_arc:
        - arc_id: persuade
      tone: 严谨/客观
      length_estimate: "1200-2000字"
      avoid:
        - 选择性用数据
        - 不标数据来源
    conflict:
      priority: 4

  - id: comparison_choice
    name: 对比选择型
    detection:
      patterns:
        - "A和B怎么选"
        - "还是"
        - "取舍"
        - "vs"
        - "对比"
      min_confidence: 0.65
    characteristics:
      typical_structure:
        - structure_id: option_analysis_scenario_decision
          weight: 10
      typical_style:
        - style_id: analytical
          weight: 10
        - style_id: warm
          weight: 7
      typical_arc:
        - arc_id: empathize_inspire
      tone: 理性/体谅
      length_estimate: "1200-2000字"
      avoid:
        - 直接替读者决定
        - 只讲差异不讲适用场景
    conflict:
      priority: 5
```

#### 2.1.2 开头钩子（`hooks.yaml`）

```yaml
hooks:
  - id: string
    name: string
    type: string                         # 反常识 / 故事开头 / 数据冲击 / 共情开场 / 引用 / 提问
    structure: string                    # 模板描述（含变量标记如 {data}）
    example: string                      # 符合结构的真实例子
    suitable_for: string[]               # 适用问题类型 ID 列表
    unsuitable_for: string[]             # 不适用的问题类型
    risk_level: "low" | "medium" | "high"  # 容易翻车的程度
    risk_note: string                    # 使用时的注意事项
```

例：

```yaml
hooks:
  - id: counter_intuitive
    name: 反常识
    type: 反常识
    structure: "先说一个反直觉的事实/数据 → 引出问题 → 表明立场"
    example: "你可能不相信，但根据XX数据，真正选择躺平的年轻人不到3%。大部分人只是累了。"
    suitable_for: [opinion_debate, phenomenon_analysis, data_driven]
    unsuitable_for: [emotional_resonance]
    risk_level: medium
    risk_note: "数据需要真实可查，建议用知识库中已有数据。如果数据被质疑会丧失信用。"

  - id: story_open
    name: 故事开头
    type: 故事开头
    structure: "三句话讲一个相关故事 → 点出问题核心"
    suitable_for: [experience_share, knowledge_explain, emotional_resonance]
    unsuitable_for: [data_driven]
    risk_level: low
    risk_note: "故事必须真实或标明改编。长度控制在60字以内才有效果。"

  - id: data_impact
    name: 数据冲击
    type: 数据冲击
    structure: "抛出一个对比强烈的数据 → 说数据来源 → 追问"
    suitable_for: [data_driven, phenomenon_analysis, opinion_debate]
    unsuitable_for: [emotional_resonance]
    risk_level: medium
    risk_note: "数据必须可溯源。对比的巧妙比数字大小更重要。"

  - id: empathy_open
    name: 共情开场
    type: 共情开场
    structure: "承认感受 → 转视角 → 给出新角度"
    suitable_for: [emotional_resonance, experience_share, comparison_choice]
    unsuitable_for: [data_driven]
    risk_level: low
    risk_note: "共情要真诚，用'很多人'而不是'你'来避免说教感。"

  - id: question_open
    name: 提问开场
    type: 提问开场
    structure: "抛出一个让人停下来想的问题 → 自答/引导"
    suitable_for: [opinion_debate, knowledge_explain, phenomenon_analysis]
    unsuitable_for: [emotional_resonance]
    risk_level: low
    risk_note: "问题要有张力，答案是'不一定'或'看情况'的那种问题最好。"
```

#### 2.1.3 情绪曲线（`emotional_arcs.yaml`）

```yaml
emotional_arcs:
  - id: string
    name: string
    suitable_for: string[]
    unsuitable_for: string[]
    phases:
      - phase: string         # 阶段名
        emotion: string       # 起始→结束情绪
        position: string      # 在回答中的位置百分比
        action: string        # 这个阶段做什么
        technique: string     # 可用技巧
```

例：

```yaml
emotional_arcs:
  - id: empathize_inspire
    name: 共情-启发
    suitable_for: [emotional_resonance, experience_share, comparison_choice]
    unsuitable_for: [data_driven, controversy_evaluation]
    phases:
      - phase: 引入
        emotion: 平静→好奇
        position: "0-10%"
        action: 用钩子拉入
        technique: "故事/共情开场"
      - phase: 共情
        emotion: 认同
        position: "10-25%"
        action: 表明自己也有类似感受，建立信任
        technique: "留白、类比"
      - phase: 转折
        emotion: 疑惑→思考
        position: "25-45%"
        action: 抛出不同于直觉的新视角
        technique: "归因框架、以退为进"
      - phase: 展开
        emotion: 沉浸
        position: "45-75%"
        action: 论据+案例层层推进
        technique: "结构模板中的展开逻辑"
      - phase: 收束
        emotion: 满足/有力量
        position: "75-100%"
        action: 总结 + 开放问题/行动建议
        technique: "留白、金句"
    note: "转折阶段的力度决定整个回答的深度，值得花最多精力打磨。"

  - id: persuade
    name: 论证-说服
    suitable_for: [opinion_debate, controversy_evaluation, data_driven]
    unsuitable_for: [emotional_resonance]
    phases:
      - phase: 立场展示
        emotion: 开始可能对立→好奇
        position: "0-15%"
        action: 明确自己的核心立场，但给读者一个留下来的理由
        technique: "反常识钩子、数据冲击"
      - phase: 构建信任
        emotion: 开始松动
        position: "15-35%"
        action: 展示自己研究过反方观点，承认对方有道理之处
        technique: "以退为进"
      - phase: 核心论证
        emotion: 跟随思考
        position: "35-75%"
        action: 论据链推进，每个论据讲透再接下一个
        technique: "归因框架、类比暗示"
      - phase: 收束
        emotion: 明白→自己得出结论
        position: "75-100%"
        action: 总结 + 给读者自己去判断的空间
        technique: "留白"
    note: "说服不是压倒对方，而是给对方一个体面的台阶来改变看法。"

  - id: surprise_understand
    name: 惊讶-理解
    suitable_for: [knowledge_explain, phenomenon_analysis]
    unsuitable_for: [emotional_resonance, comparison_choice]
    phases:
      - phase: 抓住注意力
        emotion: 好奇
        position: "0-10%"
        action: 用一个反直觉的事实/类比开场
        technique: "类比暗示"
      - phase: 建基
        emotion: 理解基础
        position: "10-30%"
        action: 用最白的话讲核心概念
        technique: "类比"
      - phase: 深入
        emotion: 满足求知欲
        position: "30-70%"
        action: 分层讲解，每层加例子
        technique: "结构模板中的分层展开"
      - phase: 落地
        emotion: 恍然大悟
        position: "70-100%"
        action: 用一句话总结 + 开放延伸方向
        technique: "金句"
    note: "最怕的是讲太浅，懂的人觉得啰嗦。每层都要给出新信息增量。"
```

#### 2.1.4 文风画像（`styles.yaml`）

```yaml
styles:
  - id: string
    name: string
    tone: string               # 情绪基调描述
    sentence_length: string    # 句式特点
    paragraph_flow: string     # 段落推进逻辑
    markers: string[]          # 语言标记特征
    techniques: string[]       # 常用技巧
    suitable_for: string[]     # 适用类型
    example_authors: string[]  # 风格参考作者（提示用，非必须引用）
    avoid: string[]            # 避免的做法
```

例：

```yaml
styles:
  - id: analytical
    name: 分析型
    tone: 冷静、客观、逻辑
    sentence_length: 中短句为主，长句只用于排比或连续推导
    paragraph_flow: "观点 → 论据 → 小结 → 下一观点"
    markers:
      - "转折词（但/然而/不过）引导新一层论证"
      - "数据/事实先行于判断"
      - "少用形容词判断，多用名词定义"
    techniques:
      - "归因框架"
      - "类比暗示"
      - "以退为进"
    suitable_for: [opinion_debate, phenomenon_analysis, data_driven, controversy_evaluation, comparison_choice]
    example_authors: ["和菜头（部分）", "李楠（部分）"]
    avoid:
      - "空洞抒情"
      - "情绪化表述"
      - "过于口语化"

  - id: storytelling
    name: 讲故事型
    tone: 亲切、画面感、节奏感
    sentence_length: 短句为主，时有长句做铺垫
    paragraph_flow: "场景 → 细节 → 感受 → 提炼"
    markers:
      - "具体细节（时间/地点/人物/对话）"
      - "悬念或反转"
      - "金句点题"
    techniques:
      - "留白"
      - "类比暗示"
    suitable_for: [experience_share, knowledge_explain, emotional_resonance]
    example_authors: ["张佳玮"]
    avoid:
      - "故事太长没提炼"
      - "细节不够泛泛而谈"

  - id: sharp
    name: 犀利型
    tone: 直接、有力度、敢下判断
    sentence_length: 短句为主，节奏快
    paragraph_flow: "断言 → 证据 → 再断言"
    markers:
      - "开头就亮观点"
      - "反问句多"
      - "对比强烈"
    techniques:
      - "反讽"
      - "归因框架"
      - "反常识钩子"
    suitable_for: [opinion_debate, controversy_evaluation, phenomenon_analysis]
    example_authors: ["曹丰"]
    avoid:
      - "攻击性过强"
      - "只有批评没有建设"
      - "过度简化复杂问题"

  - id: professional
    name: 专业型
    tone: 权威、有深度、可信
    sentence_length: 中长句，表达精确
    paragraph_flow: "定义/背景 → 分析 → 证据 → 结论"
    markers:
      - "使用学科术语（但紧跟解释）"
      - "引述研究/文献"
      - "谨慎限定词（'在XX条件下'）"
    techniques:
      - "归因框架"
      - "类比暗示"
    suitable_for: [knowledge_explain, data_driven, phenomenon_analysis]
    example_authors: ["李靖（数据向）"]
    avoid:
      - "术语轰炸不加解释"
      - "用复杂表达简单概念"
      - "绝对化断言"

  - id: warm
    name: 温暖型
    tone: 有温度、共情、包容
    sentence_length: 中短句，节奏舒缓
    paragraph_flow: "共情 → 分享 → 启发"
    markers:
      - "使用'我们'而非'你'"
      - "承认不确定性"
      - "给予空间而非给出标准答案"
    techniques:
      - "留白"
      - "类比暗示"
      - "以退为进"
    suitable_for: [emotional_resonance, experience_share, comparison_choice]
    example_authors: []
    avoid:
      - "说教"
      - "强行正能量"
      - "比惨/比较痛苦"
```

#### 2.1.5 结构模板（`structures.yaml`）

```yaml
structures:
  - id: string
    name: string
    sections:
      - id: string
        name: string
        content: string
        length_ratio: string   # 占全文比例
        example: string
    suitable_for: string[]
    unsuitable_for: string[]
```

例：

```yaml
structures:
  - id: opinion_evidence_counter_close
    name: 观点-论据-反方-总结
    sections:
      - id: opening
        name: 开篇亮观点
        content: "直接给出核心观点（一句话）"
        length_ratio: "10%"
      - id: evidence_chain
        name: 论据链
        content: "2-3个层层递进的论据，每个论据 = 点 + 证 + 例"
        length_ratio: "50%"
      - id: counterpoint_response
        name: 回应反方
        content: "先承认反方的合理之处，再指出局限"
        length_ratio: "20%"
      - id: closing
        name: 总结升华
        content: "回到开头观点 + 留白/开放问题"
        length_ratio: "20%"
    suitable_for: [opinion_debate, controversy_evaluation, phenomenon_analysis]
    unsuitable_for: [emotional_resonance, experience_share]

  - id: pro_con_conclusion
    name: 正反-结论
    sections:
      - id: context
        name: 背景说明
        content: "定义讨论范围"
        length_ratio: "15%"
      - id: pro_side
        name: 正方论证
        content: "认真阐述支持的论据"
        length_ratio: "30%"
      - id: con_side
        name: 反方论证
        content: "同样认真阐述反对的论据"
        length_ratio: "30%"
      - id: conclusion
        name: 综合结论
        content: "给出判断框架与结论"
        length_ratio: "25%"
    suitable_for: [controversy_evaluation, comparison_choice, opinion_debate]
    unsuitable_for: [emotional_resonance]

  - id: phenomenon_cause_effect_trend
    name: 现象-原因-影响-趋势
    sections:
      - id: phenomenon
        name: 现象描述
        content: "具体现象 + 数据/例子支撑"
        length_ratio: "15%"
      - id: cause_analysis
        name: 原因分析
        content: "深层原因（避免归因单一）"
        length_ratio: "30%"
      - id: impact
        name: 影响展开
        content: "对不同群体的差异化影响"
        length_ratio: "25%"
      - id: trend
        name: 趋势预判
        content: "推演而非预测，给读者判断框架"
        length_ratio: "30%"
    suitable_for: [phenomenon_analysis, data_driven]
    unsuitable_for: [emotional_resonance]

  - id: analogy_intro_layer_conclusion
    name: 类比-分层-总结
    sections:
      - id: analogy
        name: 类比引入
        content: "用一个读者熟悉的概念做锚点"
        length_ratio: "10%"
      - id: layer_1
        name: 第一层：基础
        content: "最白的话讲核心"
        length_ratio: "25%"
      - id: layer_2
        name: 第二层：深入
        content: "引入必要的复杂度"
        length_ratio: "30%"
      - id: layer_3
        name: 第三层：边界
        content: "这个概念的局限/适用条件"
        length_ratio: "20%"
      - id: closing
        name: 总结
        content: "回到类比 + 一句话概括"
        length_ratio: "15%"
    suitable_for: [knowledge_explain, phenomenon_analysis]
    unsuitable_for: [emotional_resonance]

  - id: background_method_tips
    name: 背景-方法-踩坑-建议
    sections:
      - id: background
        name: 背景与起点
        content: "自己的起点是什么（建立共鸣）"
        length_ratio: "15%"
      - id: method
        name: 具体方法
        content: "做了什么、怎么做"
        length_ratio: "35%"
      - id: pitfalls
        name: 踩过的坑
        content: "走了什么弯路、如何识别和避免"
        length_ratio: "25%"
      - id: advice
        name: 给你的建议
        content: "针对不同情况的差异化建议"
        length_ratio: "25%"
    suitable_for: [experience_share]
    unsuitable_for: [opinion_debate, data_driven]

  - id: empathize_share_inspire
    name: 共情-分享-启发
    sections:
      - id: empathize
        name: 我懂你
        content: "承认感受的普遍性，消除孤独感"
        length_ratio: "15%"
      - id: share
        name: 我的经历/视角
        content: "具体故事或视角转换"
        length_ratio: "35%"
      - id: pivot
        name: 新的可能性
        content: "不是解决方案，是另一种看待方式"
        length_ratio: "25%"
      - id: closing
        name: 送给你
        content: "一句话的力量"
        length_ratio: "25%"
    suitable_for: [emotional_resonance]
    unsuitable_for: [data_driven, controversy_evaluation]

  - id: what_why_how
    name: What-Why-How
    sections:
      - id: what
        name: 是什么
        content: "定义/范围/不包含什么"
        length_ratio: "20%"
      - id: why
        name: 为什么重要
        content: "这个问题/概念为什么值得关注"
        length_ratio: "30%"
      - id: how
        name: 怎么办/怎么理解
        content: "理解框架或行动指南"
        length_ratio: "50%"
    suitable_for: [knowledge_explain, experience_share]
    unsuitable_for: [emotional_resonance]

  - id: data_interpretation_inference
    name: 数据-解读-归因-推测
    sections:
      - id: raw_data
        name: 数据呈现
        content: "原始数据，标注来源"
        length_ratio: "15%"
      - id: interpretation
        name: 数据解读
        content: "数据在说什么（不要过度解读）"
        length_ratio: "30%"
      - id: attribution
        name: 归因分析
        content: "为什么会出现这个数据"
        length_ratio: "30%"
      - id: inference
        name: 推测与问题
        content: "这意味着什么 + 哪些还没答案"
        length_ratio: "25%"
    suitable_for: [data_driven, phenomenon_analysis]
    unsuitable_for: [emotional_resonance]

  - id: option_analysis_scenario_decision
    name: 选项分析-场景-决策框架
    sections:
      - id: clarify
        name: 梳理选项
        content: "明确比较的是什么"
        length_ratio: "15%"
      - id: option_a
        name: 选项A分析
        content: "适合谁、为什么、代价"
        length_ratio: "25%"
      - id: option_b
        name: 选项B分析
        content: "适合谁、为什么、代价"
        length_ratio: "25%"
      - id: scenario
        name: 场景匹配
        content: "什么情况选A、什么情况选B"
        length_ratio: "20%"
      - id: framework
        name: 决策框架
        content: "给出读者自己能用的判断方法"
        length_ratio: "15%"
    suitable_for: [comparison_choice]
    unsuitable_for: [emotional_resonance, data_driven]
```

#### 2.1.6 春秋笔法技巧（`techniques.yaml`）

每个 technique 必须有硬性安全约束：

```yaml
techniques:
  - id: string
    name: string
    description: string
    mechanism: string           # 为什么有效（原理）
    example: string
    usage: string               # 怎么用
    allowed_contexts: string[]  # 允许使用的场景
    avoid_contexts: string[]    # 禁止使用的场景
    risk_level: "low" | "medium" | "high"
    safety_instruction: string  # 必须遵守的安全准则
```

例：

```yaml
techniques:
  - id: attribution_framing
    name: 归因框架
    description: "选择归因层次（个人/系统/时代）来影响读者对问题的理解"
    mechanism: "读者会不自觉地接受你设定的归因层次，从而按你的框架思考"
    example: "不是年轻人不努力，而是努力的回报率在下降"
    usage: "观点讨论型、现象分析型 — 在引出核心观点后使用"
    allowed_contexts:
      - opinion_debate
      - phenomenon_analysis
      - data_driven
    avoid_contexts:
      - emotional_resonance  # 需先共情而非归因
    risk_level: medium
    safety_instruction: |
      1. 归因不能只选有利证据 — 需要同时提及反方向因素
      2. 系统归因不能完全免去个人责任 — "既有系统因素，也有个人选择"
      3. 归因框架用于帮助读者理解，不是操控判断
      4. 涉及敏感话题（政策/社会结构）时，优先展示多角度归因

  - id: analogy_suggestion
    name: 类比暗示
    description: "用类比替代直接结论，让读者自己推导"
    mechanism: "读者自己推导出的结论比被告知的更有说服力"
    example: "这就像让鱼去爬树 — 不是鱼不行，是标准错了"
    usage: "所有类型均可，但类比要精准"
    allowed_contexts:
      - opinion_debate
      - phenomenon_analysis
      - knowledge_explain
      - emotional_resonance
      - data_driven
      - controversy_evaluation
      - comparison_choice
      - experience_share
    avoid_contexts: []
    risk_level: low
    safety_instruction: |
      1. 类比必须准确 — 误导性类比比没有类比更糟
      2. 不能用于将复杂问题过度简化
      3. 敏感话题的类比要格外谨慎（不能类比暴力/歧视等）

  - id: white_space
    name: 留白
    description: "点到为止，不给标准答案，让读者自己完成思考"
    mechanism: "人们珍惜自己得出的结论胜过被告知的答案"
    example: "至于怎么选，每个人心里都有自己的答案。"
    usage: "争议型、情感型 — 在关键结论处使用"
    allowed_contexts:
      - opinion_debate
      - emotional_resonance
      - comparison_choice
      - controversy_evaluation
    avoid_contexts:
      - knowledge_explain        # 科普需要给出明确答案
    risk_level: low
    safety_instruction: |
      1. 留白不等于逃避 — 前面需要充分展开铺垫
      2. 留白后不应产生误导性暗示
      3. 适合用在读者已经拥有判断所需信息的情况下

  - id: concede_then_advance
    name: 以退为进
    description: "先承认反方有道理 → 再指出其盲区/不完备之处"
    mechanism: "先认可对方能降低防御，后续的批判更容易被接受"
    example: "这种担忧确实有道理。实际上XX危机就源于类似问题。不过我们可能忽略了一个关键变量……"
    usage: "观点型、争议型 — 回应反方时使用"
    allowed_contexts:
      - opinion_debate
      - controversy_evaluation
      - phenomenon_analysis
    avoid_contexts:
      - emotional_resonance      # 情感话题不需要辩论结构
    risk_level: medium
    safety_instruction: |
      1. 退让必须真诚 — 不能先假装认同再全盘推翻
      2. 退让的部分应该是反方真正的合理之处
      3. "再指出盲区"不是全盘否定，而是补充视角

  - id: irony
    name: 反讽
    description: "正话反说，让读者自己读出讽刺意味"
    mechanism: "让读者成为'看懂暗示'的局内人，增强认同"
    example: "对，加班确实'提高效率' — 把本来8小时能做完的事拖到12小时再做。"
    usage: "吐槽文风、犀利文风 — 不宜在温暖型或专业型中使用"
    allowed_contexts:
      - opinion_debate
      - controversy_evaluation
    avoid_contexts:
      - emotional_resonance
      - experience_share
      - knowledge_explain
      - comparison_choice
    risk_level: high
    safety_instruction: |
      1. 反讽极易被误读为字面意思 — 需要在上下文中给出足够暗示
      2. 不能用于讽刺弱势群体或敏感话题
      3. 一次回答中反讽不超过1-2处
      4. 如果读者可能不熟悉你的风格，慎用
      5. 反讽的对象应该是制度/现象，而非个人
```

#### 2.1.7 图片指导（`image_guide.yaml`）

```yaml
# Phase 1 只做占位文本，不做图源集成
image_guide:
  - type: opinion_illustration
    name: 观点配图
    suggestion_format: "![suggest:{描述}]"
    placement: "开头或每个主要观点附近"
    note: "避免配图过于直白或重复文字内容"

  - type: data_visualization
    name: 数据可视化
    suggestion_format: "![suggest:{描述},参考:{参考样式}]"
    placement: "数据解读段落附近"

  - type: diagram
    name: 流程图/框架图
    suggestion_format: "![suggest:{描述},参考:{参考样式}]"
    placement: "方法/流程说明段附近"

  - type: comparison_diagram
    name: 对比图
    suggestion_format: "![suggest:{描述}]"
    placement: "对比分析段附近"

  - type: mood_image
    name: 氛围图
    suggestion_format: "![suggest:{描述}]"
    placement: "共情/转折段附近"
```

#### 2.1.8 用户覆盖（`overrides.yaml`）

```yaml
# 用户放在 .knowledge/writing-guide/overrides.yaml
# 与 repo 内 templates/ 合并，同名字段覆盖
override_mode: merge  # merge | replace
style_preferences:
  preferred: []        # 优先选择的文风
  avoid: []            # 避免的文风
hook_preferences:
  preferred: []
  avoid: [irony]       # 例如：用户不喜欢反讽
structure_preferences:
  preferred: []
```

### 2.2 格式感知策略生成 — SmartWriter

#### 2.2.1 核心流程

```
用户输入问题
  │
  ▼
┌────────────────────┐
│ QuestionClassifier │  分析问题类型 + 提取关键维度
│  - intent          │  置信度 < 0.7 → 不自动分类，给选项让用户选
│  - question_type   │
│  - keywords        │
│  - tone            │
└────────┬───────────┘
         ▼
┌────────────────────┐
│ FormatSelector     │  根据类型 + 权重 → 推荐方案
│  - hooks           │  返回推荐列表 + 备选
│  - emotional_arc   │  每个推荐附 weight 和 reason
│  - structure       │
│  - styles          │
│  - techniques      │
└────────┬───────────┘
         ▼
┌────────────────────┐
│ Retriever          │  搜索知识库
│                    │  匹配素材卡片
│                    │  匹配主题
└────────┬───────────┘
         ▼
┌────────────────────┐
│ LLM Strategist     │  组装增强 prompt
│                    │  调用 DeepSeek
│                    │  输出结构化策略
└────────┬───────────┘
         ▼
    结构化策略输出
```

#### 2.2.2 输出结构

```json
{
  "question_analysis": {
    "type": "phenomenon_analysis",
    "type_confidence": 0.85,
    "alternative_types": [{"type": "opinion_debate", "confidence": 0.20}],
    "keywords": ["躺平", "年轻人", "就业"],
    "estimated_tone": "中立/犀利",
    "estimated_length": "1500-2500字"
  },
  "format_recommendation": {
    "description": "对这个现象分析类问题，建议采用分析型文风 + 论证-说服情绪曲线 + 现象-原因-影响-趋势结构",
    "hook": {
      "recommended": [
        {"id": "counter_intuitive", "reason": "这类问题读者已经听了很多泛泛之谈，反常识数据最容易抓住注意力"}
      ],
      "alternatives": [
        {"id": "story_open", "reason": "如果有一个典型人物故事，可以用故事切入"}
      ]
    },
    "style": {
      "recommended": ["analytical"],
      "reason": "现象分析需要冷静客观，分析型文风最适合用数据和逻辑推进",
      "blend": "如果想让阅读体验更轻松，可以在分析型基础上加入20%讲故事要素（在案例部分）"
    },
    "structure": {
      "recommended": {"id": "phenomenon_cause_effect_trend", "reason": "现象-原因-影响-趋势结构最契合这类问题"},
      "alternative": {"id": "opinion_evidence_counter_close", "reason": "如果你的观点比较鲜明，也可以先用观点切入"}
    },
    "emotional_arc": {
      "recommended": "surprise_understand",
      "phases": [
        {"phase": "抓住注意力", "technique": "反常识钩子", "note": "用对比强烈的数据开场"},
        {"phase": "建基", "technique": "归因框架", "note": "先说这不是单一因素造成的"},
        {"phase": "深入", "technique": "论据链", "note": "每层加一个不同角度"},
        {"phase": "落地", "technique": "留白", "note": "给读者自己判断的空间"}
      ]
    },
    "techniques": {
      "recommended": [
        {"id": "attribution_framing", "placement": "展开分析前", "note": "用归因框架建立分析出发点"},
        {"id": "analogy_suggestion", "placement": "解释复杂原因时", "note": "用读者熟悉的类比简化理解"}
      ],
      "optional": [
        {"id": "concede_then_advance", "placement": "回应反方观点时", "note": "如果回答中涉及争议点"}
      ]
    },
    "image_suggestions": [
      {"type": "data_visualization", "description": "年轻人就业率/收入趋势折线图", "placement": "现象描述段"},
      {"type": "opinion_illustration", "description": "一个隐喻'躺平'的插画/场景图", "placement": "收束段"}
    ]
  },
  "outline": [
    {"section": "现象", "key_points": ["当前躺平话题的热度数据", "到底什么是'躺平'—不同人的定义不同"], "technique_hint": "反常识数据开场"},
    {"section": "原因", "key_points": ["经济因素：就业/房价", "社会因素：预期vs现实", "代际因素：价值观变化"], "technique_hint": "归因框架：分层而非单一归因"},
    {"section": "影响", "key_points": ["对个人的影响", "对劳动力市场的影响", "社会心态的长远变化"], "technique_hint": "类比暗示"},
    {"section": "趋势", "key_points": ["这不是中国独有现象", "历史上有类似先例", "真正的问题不是'躺平'而是'希望'"], "technique_hint": "留白"}
  ],
  "material_package": {
    "sources_used": 3,
    "core_viewpoints": [...],
    "argument_chain": [
      {"point": "躺平本质是对回报率下降的理性回应", "evidence": "...", "source": "..."}
    ],
    "case_stories": [...],
    "key_quotes": [...],
    "source_topics": ["青年就业", "社会心态"]
  },
  "risks": [
    {"level": "low", "message": "部分素材来自知乎，建议核实原始数据来源"}
  ]
}
```

### 2.3 `write-smart` CLI

```
zhihu2obsidian write-smart "<问题>"

  分析问题 → 输出写作策略（类型/文风/结构/钩子/技巧/大纲 + 素材包）

  参数:
    --question-file <path>     从文件读取问题（支持长文本）
    --style <id>               手动指定文风（默认为类型匹配推荐）
    --hook <id>                手动指定钩子（默认为类型匹配推荐）
    --outline-only             只输出大纲（不检索素材包）
    --json                     输出完整结构化 JSON
    --raw                      只输出策略正文（无装饰）
    --copy                     复制到剪贴板
    --no-context               不检索知识库（纯格式策略，无素材）
```

#### 降级行为

| 条件 | 行为 |
|---|---|
| 无知识库 | `question analyze` 正常工作（只输出类型+格式建议），`write-smart` 不加 `--no-context` 则报错提示 |
| 无 API Key | `question analyze` 正常工作。`write-smart` 报错并要求设置 Key |
| 分类置信度 < 0.7 | 输出候选类型让用户选择，不自动决策 |
| DeepSeek 超时/失败 | 降级为模板规则引擎（基于类型匹配推荐，无 LLM 生成大纲） |
| 检索到 0 篇素材 | `write-smart` 输出格式策略但标注"当前知识库无相关素材"，不加素材包 |

### 2.4 `question analyze` CLI

```
zhihu2obsidian question analyze "<问题>"

  输出: 问题分析报告（不涉及 LLM 调用，纯规则引擎）

  {
    type_candidates: [
      {type: "phenomenon_analysis", confidence: 0.85},
      {type: "opinion_debate", confidence: 0.20}
    ],
    keywords: ["躺平", "年轻人"],
    estimated_tone: "中立/犀利"
  }

  参数:
    --json     JSON 输出
    --raw      纯文本单行输出
```

无需 API Key，无需知识库。

### 2.5 浏览器插件

#### 2.5.1 触发机制

- ❌ 不自动弹出分析
- ❌ 页面加载时不调 LLM
- ✅ 页面加载时检测是否是知乎问题页 → 更新图标 badge（显示"📋"或颜色变化）
- ✅ 用户通过以下方式显式触发：
  - 点击插件图标
  - 右键菜单 "分析回答策略"
  - 快捷键（默认 `Alt+Shift+Z`）

#### 2.5.2 侧边栏

三层结构：

```
┌─── 策略 ──────────────────────────┐
│ 问题类型: 现象分析型               │
│ 推荐文风: 分析型                   │
│ 推荐结构: 现象-原因-影响-趋势       │
│ 推荐钩子: 反常识开头               │
│ 情绪曲线: 惊讶-理解                │
│ 预估长度: 1500-2500字              │
│ ───────────────────────────────── │
│ 🎣 钩子                           │
│ 推荐: 反常识 — 用对比数据开场      │
│ 备选: 故事开头                     │
│ ───────────────────────────────── │
│ 🎭 技巧                           │
│ 推荐: 归因框架 / 类比暗示          │
│ 备选: 以退为进                     │
│ ───────────────────────────────── │
│ 🖼 配图建议                        │
│ 2张：趋势图/隐喻图                 │
│（这是建议，执行在策略助手外部完成） │
└───────────────────────────────────┘

┌─── 素材 ──────────────────────────┐
│ 核心观点 (3)                      │
│ 论据链 (4)                        │
│ 案例库 (2)                        │
│ 金句 (2)                          │
│ 来源: 知识库 (3篇)                │
│ 关联主题: 青年就业 / 社会心态      │
└───────────────────────────────────┘

┌─── 大纲 ──────────────────────────┐
│ 1. 现象 — 数据/事实               │
│ 2. 原因 — 经济/社会/代际           │
│ 3. 影响 — 个人/市场/社会           │
│ 4. 趋势 — 历史/展望               │
│ ───────────────────────────────── │
│ [复制 MD] [下载]                   │
└───────────────────────────────────┘
```

#### 2.5.3 当前插件改动范围

| 文件 | 改动 |
|---|---|
| `manifest.json` | 只新增一个 `tabs` permission（用于检测 URL） |
| `content.js` | `zhihuKnowledgeSelection()` → `zhihuKnowledgeContext()` 多暴露 question title。新增 URL 检测返回 `{isQuestionPage, questionTitle}` |
| `background.js` | 新增 `/question-analysis` 调用链路。右键菜单加"分析回答策略"。图标 badge 自动检测。移除自动 LLM 调用 |
| `sidebar.html` | 改三 tab 布局 |
| `sidebar.js` | 重写渲染逻辑 |

---

## 3. API 契约

### 3.1 `/question-analysis` POST

```yaml
# Request
required:
  question_title: string        # 问题标题
optional:
  url: string                   # 来源 URL（用于记录）
  existing_answers: int         # 当前已有回答数（可选参考）
  style_preference: string      # 用户偏好的文风 ID（可选覆盖）
  hook_preference: string       # 用户偏好的钩子 ID

# Response 200
{
  "analysis": {
    "type_candidates": [
      {
        "type": "phenomenon_analysis",
        "type_name": "现象分析型",
        "confidence": 0.85
      },
      {
        "type": "opinion_debate",
        "type_name": "观点讨论型",
        "confidence": 0.20
      }
    ],
    "keywords": ["躺平", "年轻人", "就业"],
    "estimated_tone": "中立/犀利",
    "estimated_length": "1500-2500字",
    "is_confident": true    # true if primary type confidence >= 0.7
  },
  "format_recommendation": {
    "description": "对这个现象分析类问题，建议采用分析型文风 + 论证-说服情绪曲线 + 现象-原因-影响-趋势结构",
    "hook": {
      "recommended": [{"id": "counter_intuitive", "name": "反常识", "reason": "..."}],
      "alternatives": [{"id": "story_open", "name": "故事开头", "reason": "..."}]
    },
    "style": {
      "recommended": [{"id": "analytical", "name": "分析型", "reason": "..."}],
      "blend_suggestion": null
    },
    "structure": {
      "recommended": {"id": "phenomenon_cause_effect_trend", "name": "现象-原因-影响-趋势", "reason": "..."},
      "alternative": {"id": "opinion_evidence_counter_close", "name": "观点-论据-反方-总结", "reason": "..."}
    },
    "emotional_arc": {
      "recommended": {"id": "surprise_understand", "name": "惊讶-理解", "phases": [...]},
      "note": "..."
    },
    "techniques": {
      "recommended": [{"id": "attribution_framing", "name": "归因框架", "placement": "...", "note": "..."}],
      "optional": [{"id": "concede_then_advance", "name": "以退为进", "placement": "...", "note": "..."}]
    },
    "image_suggestions": [
      {"type": "data_visualization", "description": "...", "placement": "..."}
    ]
  },
  "material_package_available": true
}

# Response 200 (no knowledge base / no key — format only)
{
  "analysis": { ... same analysis object ... },
  "format_recommendation": { ... same format object ... },
  "material_package_available": false,
  "notes": ["知识库未构建，无需素材包"]
}

# Response 400
{
  "error": "question_title 不能为空"
}

# Response 500
{
  "error": "internal_error",
  "detail": "分类规则引擎异常（不会因为 LLM 挂掉而返回 500）"
}
```

### 3.2 `/write-smart` POST

```yaml
# Request
required:
  question_title: string
optional:
  url: string
  style: string               # 文风 ID（默认为推荐）
  hook: string                # 钩子 ID（默认为推荐）
  temperature: float          # 0-1，默认 0.5（推荐策略时用较低温）
  output_mode: "outline" | "full"  # 默认 full（策略+素材包+大纲）
  no_context: bool            # 默认 false
  existing_answers: int       # 已有回答数（参考）

# Response 200 (output_mode=full)
#  格式同 §2.2.2 输出结构

# Response 200 (no key)
{
  "error": "writing_strategy_disabled",
  "message": "write-smart 需要 DeepSeek API Key 才能生成大纲",
  "available_without_key": [
    "POST /question-analysis (格式建议 + 素材包模板，无大纲)"
  ]
}

# Response 200 (no knowledge base + no_context=false)
{
  "error": "knowledge_base_missing",
  "message": "知识库未构建。添加 --no-context 可跳过知识库检索获取纯格式策略",
  "available_without_key": ["POST /question-analysis"]
}

# Error codes
- "writing_strategy_disabled": 爬 API Key
- "knowledge_base_missing": 知识库不存在
- "invalid_style": 指定了不存在的文风 ID
- "invalid_hook": 指定了不存在的钩子 ID
- "llm_timeout": DeepSeek 超时，降级策略可用
- "internal_error": 代码故障
```

### 3.3 降级行为总表

| 组件 | 无 API Key | 无知识库 | DeepSeek 超时 | 分类置信度 < 0.7 |
|---|---|---|---|---|
| `question analyze` (CLI) | ✅ 正常工作 | ✅ 正常工作 | N/A（无 LLM） | 输出候选列表 |
| `POST /question-analysis` | ✅ 正常工作 | ✅ 正常工作 | N/A（无 LLM） |  输出候选列表 |
| `write-smart` (CLI) | ❌ 报错 | ❌ 报错（除非 `--no-context`） | 降级为规则引擎建议 | 提示用户选择类型 |
| `POST /write-smart` | ❌ 返回 200 + error | ❌ 返回 200 + error | 降级为规则 + 素材包 | 提示用户选择类型 |

---

## 4. 文件/代码变更

### Phase 1 变更清单

| 模块 | 变更类型 | 说明 |
|---|---|---|
| `writing_guide/templates/question_types.yaml` | 新增 | 8 种类型 schema + 实例 |
| `writing_guide/templates/hooks.yaml` | 新增 | 5 种钩子模板 |
| `writing_guide/templates/emotional_arcs.yaml` | 新增 | 3 条情绪曲线 |
| `writing_guide/templates/styles.yaml` | 新增 | 5 种文风 |
| `writing_guide/templates/structures.yaml` | 新增 | 9 种结构模板 |
| `writing_guide/templates/techniques.yaml` | 新增 | 5 种春秋笔法 + 安全约束 |
| `writing_guide/templates/image_guide.yaml` | 新增 | 5 种配图类型（占位文本） |
| `writing_guide/__init__.py` | 新增 | 格式指南加载器（读出 + 合并 `overrides.yaml`） |
| `agent/classifier.py` | 新增 | `QuestionClassifier` — 规则 + pattern 匹配，无 LLM |
| `agent/format_selector.py` | 新增 | `FormatSelector` — 基于权重排序，无 LLM |
| `agent/smart_writer.py` | 新增 | `SmartWriter` — 组装增强 prompt + 调用 DeepSeek |
| `__main__.py` | 修改 | 加 `write-smart` 和 `question analyze` 命令 |
| `server/app.py` | 修改 | 加 `/question-analysis` 端点 |
| `server/schemas.py` | 修改 | 加 request/response model |
| `extension/content.js` | 修改 | URL 检测 + 暴露 question title |
| `extension/background.js` | 修改 | 加 `/question-analysis` 调用，去掉自动 LLM |
| `extension/sidebar.html` | 修改 | 三 tab 布局 |
| `extension/sidebar.js` | 重写 | 三层渲染 |
| `extension/manifest.json` | 修改 | 加 `tabs` permission |

### 不改动的范围

- ❌ `.knowledge/writing-guide/overrides.yaml` — Phase 2（用户反馈机制）
- ❌ 图片搜索/生成 — 保持 `image_suggest` 占位文本
- ❌ 自动草稿生成 — 策略助手不做完整回答
- ❌ 多账号知识库视角
- ❌ 插件发布到商店

---

## 5. 验收标准（Phase 1）

| 维度 | 标准 | 方法 |
|---|---|---|
| 分类准确率 | 主要类型 top-1 命中率 ≥ 80% | 人工标注 30 个问题测试 |
| 分类置信度 | 置信度 < 0.7 时输出候选，不自作主张 | 规则硬编码 |
| 格式推荐合理度 | 推荐不被用户认为"离谱"的比例 ≥ 90% | 人工审查 10 个推荐结果 |
| 结构化 JSON 解析 | LLM 输出 JSON 解析成功率 ≥ 95% | 运行 20 次 `write-smart` |
| 无 Key 降级 | `question analyze` 完全可用，`write-smart` 给出清晰指引 | 测试 |
| 无知识库降级 | `question analyze` 完全可用，`write-smart` + `--no-context` 可用 | 测试 |
| 生成耗时 | `write-smart` 完整流程 ≤ 30s（含 DeepSeek） | 计时 10 次 |
| `/question-analysis` 响应 | 纯规则引擎，≤ 500ms | 计时 |
| 相似风险阈值 | 知识库检索结果与生成内容相似度 > 0.75 时标记风险 | 代码硬编码 |
| 来源覆盖率 | 素材包中每个论据/案例/金句标注来源 | 所有来源字段必填 |

---

## 6. 开放问题（留待产品评审后定）

1. `write-smart` 的 `--outline-only` 和 `full` 模式，是否都产出完整 JSON 交给上层，还是在 CLI 层面就只按需输出？建议全量 JSON 输出，前端/CLI 按需渲染。
2. 用户偏好系统是否要 Phase 1 就做最简单的版本（`overrides.yaml` 手写）还是等 Phase 2（基于使用记录自动调整）？建议 Phase 1 先手写。
3. 插件是否要有"记住我的选择"功能（上次选的文风/钩子）？建议 Phase 1 不做，Phase 2 补。
