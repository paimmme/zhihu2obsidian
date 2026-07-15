"""知识图谱 — NetworkX + Pyvis + vis-network 交互式主题图."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ── 已有：Chunk 级图谱（Pyvis）──────────────────

def build_graph_from_chunks(chunks: list) -> str:
    """从 chunk 元数据构建知识图谱，返回 Pyvis HTML 字符串."""
    try:
        import networkx as nx
    except ImportError:
        return "<p>需要 networkx: pip install networkx</p>"

    G: nx.Graph = nx.Graph()
    seen_contents: set = set()
    seen_authors: set = set()
    seen_collections: set = set()

    for c in chunks:
        meta = getattr(c, 'metadata', {}) or {}
        content_id = str(meta.get("content_id", ""))
        title = str(meta.get("title", content_id))
        author = str(meta.get("author", ""))
        collection = str(meta.get("collection", ""))
        collection_key = f"col_{meta.get('collection_id', collection) or collection}"
        section = str(meta.get("section", ""))

        if content_id and content_id not in seen_contents:
            G.add_node(content_id, label=title[:30], type="content", title=title)
            seen_contents.add(content_id)
        if author and f"author_{author}" not in seen_authors:
            G.add_node(f"author_{author}", label=author, type="author", title=author)
            seen_authors.add(f"author_{author}")
        if collection and collection_key not in seen_collections:
            G.add_node(collection_key, label=collection[:20], type="collection", title=collection)
            seen_collections.add(collection_key)
        if content_id and author:
            G.add_edge(content_id, f"author_{author}", title="authored_by")
        if content_id and collection:
            G.add_edge(content_id, collection_key, title="belongs_to")
        if content_id and section:
            section_id = f"{content_id}_sec_{section[:20]}"
            if not G.has_node(section_id):
                G.add_node(section_id, label=section[:20], type="section", title=section)
            G.add_edge(content_id, section_id, title="has_section")

    try:
        from pyvis.network import Network

        net = Network(height="600px", width="100%", bgcolor="#ffffff", font_color="#333333")
        net.set_options("""
        {
          "nodes": {
            "font": {"size": 14, "face": "Arial"},
            "scaling": {"min": 10, "max": 30}
          },
          "edges": {
            "color": {"color": "#cccccc"},
            "font": {"size": 10},
            "smooth": {"type": "continuous"}
          },
          "physics": {
            "stabilization": {"iterations": 100},
            "barnesHut": {"gravitationalConstant": -3000}
          }
        }
        """)

        color_map = {"content": "#4CAF50", "author": "#2196F3", "collection": "#FF9800", "section": "#9C27B0"}

        for node, data in G.nodes(data=True):
            ntype = data.get("type", "content")
            net.add_node(
                node,
                label=data.get("label", node)[:20],
                title=f"{ntype}: {data.get('title', '')}",
                color=color_map.get(ntype, "#999999"),
                size=20,
            )

        for src, dst, data in G.edges(data=True):
            net.add_edge(src, dst, title=data.get("title", ""), color="#cccccc")

        return net.generate_html()
    except ImportError:
        return "<p>需要 pyvis: pip install pyvis</p>"


def save_graph_html(chunks: list, output_path: Path) -> None:
    """Build and save knowledge graph to HTML file."""
    html = build_graph_from_chunks(chunks)
    output_path.write_text(html, encoding="utf-8")


# ── 新增：主题级交互式图谱（vis-network CDN）───────

def load_tree_data(tree_path: Path) -> dict[str, Any]:
    """加载知识树 index.json."""
    if tree_path.exists():
        return json.loads(tree_path.read_text(encoding="utf-8"))
    return {"version": 1, "generated_at": "", "nodes": []}


def _compute_topic_edges(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """计算主题间边.

    策略：共享 content_ids + 关键词 Jaccard 相似度.
    """
    edges: list[dict[str, Any]] = []
    seen_pairs: set = set()

    for i, a in enumerate(nodes):
        a_cids = set(a.get("content_ids", []))
        a_kws = set(k.lower() for k in a.get("keywords", []))
        for j in range(i + 1, len(nodes)):
            b = nodes[j]
            pair = (a["id"], b["id"])
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            b_cids = set(b.get("content_ids", []))
            b_kws = set(k.lower() for k in b.get("keywords", []))

            shared_cids = a_cids & b_cids
            shared_kws = a_kws & b_kws

            weight = 0
            reasons: list[str] = []

            if shared_cids:
                weight += len(shared_cids) * 2
                reasons.append(f"共享 {len(shared_cids)} 篇素材")

            if shared_kws:
                # Jaccard-like: 共享关键词数 / min(keyword set size)
                min_kw = min(len(a_kws), len(b_kws)) or 1
                jaccard_kw = len(shared_kws) / min_kw
                weight += jaccard_kw * 5
                kws_str = ", ".join(sorted(shared_kws)[:3])
                reasons.append(f"关键词: {kws_str}")

            if weight > 0 and (len(shared_cids) >= 1 or len(shared_kws) >= 1):
                edges.append({
                    "source": a["id"],
                    "target": b["id"],
                    "weight": round(weight, 1),
                    "shared_content": list(shared_cids),
                    "shared_keywords": list(shared_kws),
                    "title": " | ".join(reasons),
                })

    edges.sort(key=lambda e: e["weight"], reverse=True)
    return edges


def build_topic_graph_html(tree_path: Path) -> str:
    """生成交互式主题图谱 HTML（vis-network CDN）."""
    tree = load_tree_data(tree_path)
    nodes = tree.get("nodes", [])

    if not nodes:
        return "<p>知识树为空</p>"

    edges = _compute_topic_edges(nodes)

    # 序列化为 JSON
    nodes_json = []
    for n in nodes:
        cids = n.get("content_ids", [])
        count = len(cids)
        confidence = n.get("confidence", 0.5)
        title = n.get("title", "")
        keywords = n.get("keywords", [])
        summary = n.get("summary", "")[:200]

        nodes_json.append({
            "id": n["id"],
            "label": title[:25],
            "title": f"{title}\n{count} 篇素材 | 置信度 {confidence}",
            "value": count * 5 + 5,  # node size
            "color": _confidence_color(confidence),
            "contentCount": count,
            "confidence": confidence,
            "fullTitle": title,
            "keywords": keywords,
            "summary": summary,
        })

    edges_json = []
    for e in edges:
        edges_json.append({
            "from": e["source"],
            "to": e["target"],
            "value": min(e["weight"], 10),
            "title": e["title"],
            "weight": e["weight"],
        })

    # 嵌入 vis-network HTML
    return _make_graph_html(
        topic_data=json.dumps(nodes_json, ensure_ascii=False),
        edge_data=json.dumps(edges_json, ensure_ascii=False),
    )


def build_topic_graph_json(tree_path: Path) -> dict[str, Any]:
    """返回主题图谱 JSON 数据（供 API 使用）."""
    tree = load_tree_data(tree_path)
    nodes = tree.get("nodes", [])

    node_list = []
    for n in nodes:
        node_list.append({
            "id": n["id"],
            "title": n.get("title", ""),
            "keywords": n.get("keywords", []),
            "summary": n.get("summary", "")[:300],
            "content_count": len(n.get("content_ids", [])),
            "confidence": n.get("confidence", 0),
            "color": _confidence_color(n.get("confidence", 0.5)),
        })

    edges = _compute_topic_edges(nodes)

    return {
        "generated_at": tree.get("generated_at", ""),
        "nodes": node_list,
        "edges": edges,
        "stats": {
            "topic_count": len(node_list),
            "edge_count": len(edges),
        },
    }


def _confidence_color(confidence: float) -> str:
    """置信度 → 色阶."""
    if confidence >= 0.9:
        return "#166534"  # dark green
    if confidence >= 0.7:
        return "#16a34a"  # green
    if confidence >= 0.5:
        return "#ca8a04"  # amber
    return "#94a3b8"  # gray


# ── vis-network HTML 模板 ──

def _make_graph_html(topic_data: str, edge_data: str) -> str:
    """组装主题图谱 HTML."""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>知识主题图谱</title>
<script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font:14px/1.6 system-ui,sans-serif; background:#f8fafc; color:#1f2937; }}
  #mynetwork {{ width:100%; height:600px; border:1px solid #e2e8f0; border-radius:8px; background:#fff; }}
  #toolbar {{ display:flex; gap:8px; padding:8px 0; flex-wrap:wrap; align-items:center; }}
  #toolbar input {{ flex:1; min-width:160px; padding:6px 10px; border:1px solid #cbd5e1; border-radius:6px; font-size:13px; }}
  #toolbar button {{ padding:6px 12px; border:1px solid #cbd5e1; border-radius:6px; background:#fff; cursor:pointer; font-size:13px; }}
  #toolbar button:hover {{ background:#f1f5f9; }}
  #toolbar .stats {{ font-size:12px; color:#64748b; }}
  #node-info {{ margin-top:8px; padding:10px; background:#fff; border:1px solid #e2e8f0; border-radius:8px; display:none; max-height:300px; overflow-y:auto; }}
  #node-info h3 {{ font-size:15px; margin-bottom:4px; }}
  #node-info p {{ font-size:13px; color:#475569; }}
  #node-info .keyword-tag {{ display:inline-block; background:#eef2ff; color:#4338ca; border-radius:4px; padding:2px 8px; font-size:12px; margin:2px; }}
  .legend {{ display:flex; gap:12px; font-size:12px; color:#64748b; padding:4px 0; }}
  .legend-item {{ display:flex; align-items:center; gap:4px; }}
  .legend-dot {{ width:12px; height:12px; border-radius:50%; display:inline-block; }}
</style>
</head>
<body>

<div id="toolbar">
  <input id="search-input" type="text" placeholder="🔍 搜索主题关键词..." oninput="filterNodes(this.value)">
  <button onclick="resetView()">重置视图</button>
  <button onclick="toggleHighlight()">高亮关联</button>
  <span class="stats" id="stats-bar"></span>
</div>

<div class="legend">
  <span class="legend-item"><span class="legend-dot" style="background:#166534"></span> 高置信度 &ge;0.9</span>
  <span class="legend-item"><span class="legend-dot" style="background:#16a34a"></span> 中置信度 0.7-0.9</span>
  <span class="legend-item"><span class="legend-dot" style="background:#ca8a04"></span> 低置信度 0.5-0.7</span>
  <span class="legend-item"><span class="legend-dot" style="background:#94a3b8"></span> 待完善 &lt;0.5</span>
  <span class="legend-item">节点大小 = 素材数量</span>
  <span class="legend-item">边粗细 = 关联强度</span>
</div>

<div id="mynetwork"></div>
<div id="node-info"></div>

<script>
  const nodesData = {topic_data};
  const edgesData = {edge_data};
  let highlightListeners = [];

  document.getElementById('stats-bar').textContent =
    nodesData.length + ' 主题 · ' + edgesData.length + ' 关联';

  const nodes = new vis.DataSet(nodesData);
  const edges = new vis.DataSet(edgesData);

  const container = document.getElementById('mynetwork');
  const options = {{
    nodes: {{
      font: {{ size: 13, face: 'system-ui' }},
      shape: 'dot',
      scaling: {{ min: 12, max: 50 }},
      borderWidth: 0,
    }},
    edges: {{
      color: {{ color: '#94a3b8', highlight: '#6366f1' }},
      smooth: {{ type: 'continuous' }},
      scaling: {{ min: 1, max: 6 }},
    }},
    physics: {{
      stabilization: {{ iterations: 150 }},
      barnesHut: {{ gravitationalConstant: -4000, springConstant: 0.04, springLength: 200 }},
    }},
    interaction: {{
      hover: true,
      tooltipDelay: 200,
      navigationButtons: true,
      keyboard: true,
    }},
    manipulation: {{ enabled: false }},
  }};

  const network = new vis.Network(container, {{ nodes, edges }}, options);

  // ── 点击节点展示详情 ──
  network.on('click', function(params) {{
    if (params.nodes.length > 0) {{
      const nodeId = params.nodes[0];
      const node = nodes.get(nodeId);
      if (node) {{
        const info = document.getElementById('node-info');
        info.style.display = 'block';
        let kwHtml = (node.keywords || []).map(k => '<span class="keyword-tag">' + k + '</span>').join(' ');
        info.innerHTML = '<h3>' + (node.fullTitle || node.label) + '</h3>' +
          '<p>素材: ' + node.contentCount + ' 篇 | 置信度: ' + (node.confidence * 100).toFixed(0) + '%</p>' +
          '<p>' + (node.summary || '') + '</p>' +
          '<p style="margin-top:4px">关键词: ' + (kwHtml || '无') + '</p>';
      }}
    }}
  }});

  // ── 双击取消选中 ──
  network.on('doubleClick', function() {{
    document.getElementById('node-info').style.display = 'none';
    network.unselectAll();
  }});

  // ── 搜索过滤 ──
  function filterNodes(query) {{
    const q = query.toLowerCase().trim();
    if (!q) {{
      nodes.forEach(n => nodes.update({{ id: n.id, hidden: false }}));
      edges.forEach(e => edges.update({{ id: e.id, hidden: false }}));
      return;
    }}
    const matched = new Set();
    nodes.forEach(n => {{
      const match = (n.fullTitle || n.label || '').toLowerCase().includes(q)
        || (n.keywords || []).some(k => k.toLowerCase().includes(q));
      nodes.update({{ id: n.id, hidden: !match }});
      if (match) matched.add(n.id);
    }});
    edges.forEach(e => {{
      const visible = matched.has(e.from) && matched.has(e.to);
      edges.update({{ id: e.id, hidden: !visible }});
    }});
  }}

  // ── 高亮相连节点 ──
  let highlightActive = false;
  let highlightHandler = null;
  function toggleHighlight() {{
    highlightActive = !highlightActive;
    if (highlightHandler) {{
      network.off('click', highlightHandler);
      highlightHandler = null;
    }}
    if (!highlightActive) {{
      nodes.forEach(n => nodes.update({{ id: n.id, opacity: 1, color: n.color }}));
      edges.forEach(e => edges.update({{ id: e.id, opacity: 1, color: {{ color: '#94a3b8' }} }}));
      return;
    }}
    highlightHandler = function(params) {{
      if (params.nodes.length === 0) return;
      const connected = network.getConnectedNodes(params.nodes[0]);
      const connectedEdges = network.getConnectedEdges(params.nodes[0]);
      const sel = params.nodes[0];
      nodes.forEach(n => {{
        nodes.update({{ id: n.id, opacity: (n.id === sel || connected.includes(n.id)) ? 1 : 0.15 }});
      }});
      edges.forEach(e => {{
        edges.update({{ id: e.id, opacity: (connectedEdges.includes(e.id) || e.from === sel || e.to === sel) ? 1 : 0.1 }});
      }});
    }};
    network.on('click', highlightHandler);
    const selected = network.getSelectedNodes();
    if (selected.length) network.emit('click', {{ nodes: selected }});
  }}

  // ── 重置 ──
  function resetView() {{
    document.getElementById('search-input').value = '';
    document.getElementById('node-info').style.display = 'none';
    if (highlightActive) toggleHighlight();
    filterNodes('');
    network.fit({{ animation: true }});
  }}

  // ── 初始适配 ──
  network.once('stabilized', function() {{ network.fit({{ animation: false }}); }});
</script>
</body>
</html>"""


def save_topic_graph_html(tree_path: Path, output_path: Path) -> None:
    """生成并保存交互式主题图谱 HTML."""
    html = build_topic_graph_html(tree_path)
    output_path.write_text(html, encoding="utf-8")
