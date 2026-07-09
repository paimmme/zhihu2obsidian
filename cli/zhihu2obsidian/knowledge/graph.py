"""知识图谱 — NetworkX + Pyvis."""

from __future__ import annotations

from pathlib import Path


def build_graph_from_chunks(chunks: list) -> str:
    """从 chunk 元数据构建知识图谱，返回 Pyvis HTML 字符串.

    Nodes:
    - content: 内容节点
    - author: 作者节点
    - collection: 收藏夹节点
    - section: 章节节点

    Edges:
    - content → author
    - content → collection
    - content → section
    """
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

        # Content node
        if content_id and content_id not in seen_contents:
            G.add_node(content_id, label=title[:30], type="content", title=title)
            seen_contents.add(content_id)

        # Author node
        if author and f"author_{author}" not in seen_authors:
            G.add_node(f"author_{author}", label=author, type="author", title=author)
            seen_authors.add(f"author_{author}")

        # Collection node
        if collection and collection_key not in seen_collections:
            G.add_node(collection_key, label=collection[:20], type="collection", title=collection)
            seen_collections.add(collection_key)

        # Edges
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
