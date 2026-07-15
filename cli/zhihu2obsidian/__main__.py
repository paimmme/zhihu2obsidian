"""CLI 入口 — zhihu2obsidian."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from . import __version__
from .api import ZhihuAPI
from .auth import CookieJar
from .config import Config, DEFAULT_COOKIE_FILE
from .sync import SyncEngine
# knowledge/agent 模块在 handler 函数内延迟导入
# (避免可选依赖未安装时 CLI 基础命令崩溃)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="zhihu2obsidian",
        description="导出知乎收藏夹到 Obsidian Vault",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--debug", action="store_true", help="显示详细日志")

    sub = parser.add_subparsers(dest="command", required=True)

    # config
    config_p = sub.add_parser("config", help="配置管理")
    config_sub = config_p.add_subparsers(dest="config_cmd")
    config_sub.add_parser("init", help="创建默认配置")
    config_set = config_sub.add_parser("set", help="设置配置值")
    config_set.add_argument("key", help="配置 key (eg. vault)")
    config_set.add_argument("value", help="配置 value")
    config_sub.add_parser("show", help="查看配置")

    # auth
    auth_p = sub.add_parser("auth", help="Cookie 认证")
    auth_sub = auth_p.add_subparsers(dest="auth_cmd")
    auth_login = auth_sub.add_parser("login", help="交互式输入 Cookie")
    auth_login.add_argument("--platform", default="zhihu", choices=["zhihu", "bilibili"],
                            help="目标平台")
    auth_import = auth_sub.add_parser("import", help="导入 Cookie 文件")
    auth_import.add_argument("path", type=Path, nargs="?", default=DEFAULT_COOKIE_FILE,
                             help="Cookie JSON 文件路径")
    auth_import.add_argument("--platform", default="zhihu", choices=["zhihu", "bilibili"],
                             help="目标平台")
    auth_status = auth_sub.add_parser("status", help="检查 Cookie 是否有效")
    auth_status.add_argument("--platform", default="zhihu", choices=["zhihu", "bilibili"],
                             help="目标平台")

    # list
    list_p = sub.add_parser("list", help="列出收藏夹")
    list_p.add_argument("collection_id", type=int, nargs="?", help="查看指定收藏夹内容")

    # sync
    sync_p = sub.add_parser("sync", help="同步收藏夹到 vault")
    sync_p.add_argument("--id", type=int, dest="collection_id", help="只同步指定收藏夹")
    sync_p.add_argument("--limit", type=int, default=0, help="限制导出条数")
    sync_p.add_argument("--dry-run", action="store_true", help="预览模式（不写入）")
    sync_p.add_argument("--force", action="store_true", help="强制重新导出所有内容")
    sync_p.add_argument("--account", default="default", help="账号名称（多账号时切换）")

    # status
    status_p = sub.add_parser("status", help="查看同步状态")
    status_p.add_argument("--account", default="default", help="账号名称")

    # knowledge
    kn_p = sub.add_parser("knowledge", help="知识库管理")
    kn_sub = kn_p.add_subparsers(dest="knowledge_cmd")
    kn_sub.add_parser("build", help="构建知识库（分块 → 向量化 → 图谱 → 词云）")
    kn_rebuild = kn_sub.add_parser("rebuild", help="强制重建知识库（清空后重来）")
    kn_stats = kn_sub.add_parser("status", help="知识库统计")
    kn_stats.add_argument("--top-tags", type=int, default=0, help="显示热门标签数")

    # cards (知识库子命令)
    kn_cards = kn_sub.add_parser("cards", help="素材卡片（LLM 抽取）")
    kn_cards_sub = kn_cards.add_subparsers(dest="cards_cmd")
    kn_cards_build = kn_cards_sub.add_parser("build", help="增量抽取素材卡片")
    kn_cards_build.add_argument("--limit", type=int, default=0, help="限制抽取数（分批用）")
    kn_cards_sub.add_parser("rebuild", help="全量重新抽取所有卡片")
    kn_cards_sub.add_parser("status", help="卡片抽取统计")
    kn_cards_search = kn_cards_sub.add_parser("search", help="搜索素材卡片")
    kn_cards_search.add_argument("query", help="搜索关键词")
    kn_cards_search.add_argument("--n", type=int, default=5, help="返回结果数")

    # topics (知识库子命令)
    kn_topics = kn_sub.add_parser("topics", help="主题聚类管理")
    kn_topics_sub = kn_topics.add_subparsers(dest="topics_cmd")
    kn_topics_sub.add_parser("build", help="聚类生成主题页")
    kn_topics_sub.add_parser("rebuild", help="全量重新聚类")
    kn_topics_sub.add_parser("list", help="列出所有主题")
    kn_topics_view = kn_topics_sub.add_parser("view", help="查看单个主题")
    kn_topics_view.add_argument("id", help="主题 ID (eg. topic_001)")

    # tree (知识库子命令)
    kn_tree = kn_sub.add_parser("tree", help="知识树管理")
    kn_tree_sub = kn_tree.add_subparsers(dest="tree_cmd")
    kn_tree_sub.add_parser("build", help="从主题页生成知识树")
    kn_tree_sub.add_parser("list", help="列出知识树节点")
    kn_tree_view = kn_tree_sub.add_parser("view", help="查看知识树节点")
    kn_tree_view.add_argument("id", help="节点 ID (eg. node_topic_001)")
    kn_tree_sub.add_parser("graph", help="生成交互式主题图谱")

    # search
    search_p = sub.add_parser("search", help="语义搜索知识库")
    search_p.add_argument("query", help="搜索查询")
    search_p.add_argument("--n", type=int, default=5, help="返回结果数")
    search_p.add_argument("--author", help="按作者筛选")
    search_p.add_argument("--collection", help="按收藏夹筛选")
    search_p.add_argument("--platform", help="按平台筛选 (zhihu/bilibili/xiaoyuzhou)")
    search_p.add_argument("--flat", action="store_true", help="原始结果 (不去重)")

    # question
    q_p = sub.add_parser("question", help="写作策略分析与格式推荐")
    q_sub = q_p.add_subparsers(dest="question_cmd")
    q_analyze = q_sub.add_parser("analyze", help="分析问题类型+格式推荐")
    q_analyze.add_argument("question", help="问题标题")
    q_analyze.add_argument("--json", action="store_true", help="输出 JSON")
    q_analyze.add_argument("--top-n", type=int, default=3, help="候选类型数")
    q_analyze.add_argument("--no-knowledge", action="store_true", help="不检索知识库")
    q_analyze.add_argument("--personal", type=str, default="", help="用户个人观点")

    # write-smart
    ws_p = sub.add_parser("write-smart", help="格式感知写作策略（不含完整草稿。需生成完整草稿请用 write-draft）")
    ws_p.add_argument("question", help="问题标题")
    ws_p.add_argument("--model", default="deepseek-v4-flash", help="DeepSeek 模型名")
    ws_p.add_argument("--temperature", type=float, default=0.5, help="生成温度（策略用较低温）")
    ws_p.add_argument("--style", default="", help="偏好文风 ID")
    ws_p.add_argument("--hook", default="", help="偏好钩子 ID")
    ws_p.add_argument("--platform", default="zhihu", choices=["zhihu", "bilibili", "xiaoyuzhou"], help="目标平台")
    ws_p.add_argument("--no-context", action="store_true", help="不检索知识库")
    ws_p.add_argument("--outline-only", action="store_true", help="只输出大纲")
    ws_p.add_argument("--json", action="store_true", help="输出 JSON")

    # write-draft
    wd_p = sub.add_parser("write-draft", help="生成完整写作草稿（基于策略，含大纲+素材+草稿）")
    wd_p.add_argument("question", help="问题标题")
    wd_p.add_argument("--model", default="deepseek-v4-flash", help="DeepSeek 模型名")
    wd_p.add_argument("--temperature", type=float, default=0.6, help="生成温度（草稿用较高温 0.6）")
    wd_p.add_argument("--style", default="", help="偏好文风 ID")
    wd_p.add_argument("--hook", default="", help="偏好钩子 ID")
    wd_p.add_argument("--platform", default="zhihu", choices=["zhihu", "bilibili", "xiaoyuzhou"], help="目标平台")
    wd_p.add_argument("--no-context", action="store_true", help="不检索知识库")
    wd_p.add_argument("--json", action="store_true", help="输出 JSON（含 draft + strategy 字段）")

    # image
    img_p = sub.add_parser("image", help="配图搜索与建议")
    img_sub = img_p.add_subparsers(dest="image_cmd")
    img_search = img_sub.add_parser("search", help="搜索配图")
    img_search.add_argument("query", help="搜索关键词")
    img_search.add_argument("--source", default="auto", choices=["auto", "wikipedia", "unsplash"],
                            help="图片来源（auto 自动选择）")
    img_search.add_argument("--json", action="store_true", help="输出 JSON")
    img_suggest = img_sub.add_parser("suggest", help="为章节建议配图")
    img_suggest.add_argument("section", help="章节标题")
    img_suggest.add_argument("--key-points", "-k", nargs="+", default=[], help="要点列表")
    img_suggest.add_argument("--json", action="store_true", help="输出 JSON")

    # write
    write_p = sub.add_parser("write", help="AI 写作助手（生成知乎回答）")
    write_p.add_argument("topic", help="问题或主题")
    write_p.add_argument("--personal", "-p", help="你的个人观点（可选）")
    write_p.add_argument("--model", default="deepseek-v4-flash", help="DeepSeek 模型名")
    write_p.add_argument("--temperature", type=float, default=0.7, help="生成温度 0-1")
    write_p.add_argument("--no-context", action="store_true", help="不检索知识库上下文")
    write_p.add_argument("--raw", action="store_true", help="只输出文本")
    write_p.add_argument("--copy", action="store_true", help="输出到剪贴板")
    write_p.add_argument("--package", action="store_true", help="生成结构化素材包（非文章）")
    write_p.add_argument("--draft", action="store_true", help="素材包同时生成初稿（需 --package）")
    write_p.add_argument("--check", action="store_true", help="生成后自动质量检查（需 --draft）")

    # check
    check_p = sub.add_parser("check", help="写作质量检查（相似度/来源覆盖）")
    check_p.add_argument("--file", type=str, help="读取 Markdown 文件检查")
    check_p.add_argument("--text", type=str, help="直接传文本检查")
    check_p.add_argument("--rewrite", action="store_true", help="为高相似段落生成改写建议")
    check_p.add_argument("--raw", action="store_true", help="只输出报告正文")

    # writing-guide
    wg_p = sub.add_parser("writing-guide", help="写作指南查询（平台信息/格式推荐）")
    wg_sub = wg_p.add_subparsers(dest="wg_cmd", required=True)
    wg_platform = wg_sub.add_parser("platform", help="查看平台信息")
    wg_platform.add_argument("platform_id", nargs="?", default="zhihu",
                              choices=["list", "zhihu", "bilibili", "xiaoyuzhou"],
                              help="平台 ID 或 list（列出所有）")

    # analyze
    analyze_p = sub.add_parser("analyze", help="分析选中文本并匹配知识树")
    analyze_p.add_argument("--text", required=True, help="要分析的文本")
    analyze_p.add_argument("--url", default="", help="来源 URL")
    analyze_p.add_argument("--page-title", default="", help="页面标题")
    analyze_p.add_argument("--question-title", default="", help="知乎问题标题")
    analyze_p.add_argument("--author", default="", help="当前回答作者")
    analyze_p.add_argument("--json", action="store_true", help="输出 JSON")

    # serve
    serve_p = sub.add_parser("serve", help="启动本地浏览器插件 API")
    serve_p.add_argument("--host", default="127.0.0.1", help="监听地址")
    serve_p.add_argument("--port", type=int, default=8765, help="监听端口")

    # bilibili
    bili_p = sub.add_parser("bilibili", help="Bilibili 收藏夹操作")
    bili_sub = bili_p.add_subparsers(dest="bilibili_cmd", required=True)
    bili_sub.add_parser("list", help="列出 B 站收藏夹")
    bili_sync = bili_sub.add_parser("sync", help="同步 B 站收藏夹到 vault")
    bili_sync.add_argument("--id", type=str, dest="collection_id", help="只同步指定收藏夹 ID")
    bili_sync.add_argument("--limit", type=int, default=0, help="限制导出条数")
    bili_sync.add_argument("--force", action="store_true", help="强制重新导出")
    bili_sync.add_argument("--account", default="default", help="账号名称")

    # xiaoyuzhou
    xyz_p = sub.add_parser("xiaoyuzhou", help="小宇宙播客热门榜")
    xyz_sub = xyz_p.add_subparsers(dest="xiaoyuzhou_cmd", required=True)
    xyz_sub.add_parser("trending", help="显示热门播客榜")
    xyz_sub.add_parser("analyze", help="热门播客风格分析")
    xyz_outline = xyz_sub.add_parser("outline", help="从知识库生成播客大纲")
    xyz_outline.add_argument("topic", help="播客主题")
    xyz_outline.add_argument("--n", type=int, default=5, help="检索知识库结果数")
    xyz_outline.add_argument("--llm", action="store_true", help="使用 DeepSeek 生成（需设置 key）")

    # monthly
    monthly_p = sub.add_parser("monthly", help="月度全平台同步 + 知识库构建 + 卡片抽取")
    monthly_p.add_argument("--account", default="default", help="账号名称")

    # export
    export_p = sub.add_parser("export", help="导出资料为 AI 友好格式 (JSONL + 分块 + 素材卡)")
    export_p.add_argument("--output", "-o", help="输出目录（默认: Vault/.knowledge/export）")
    export_p.add_argument("--model", default="deepseek-v4-flash", help="DeepSeek 模型名（素材卡抽取用）")
    export_p.add_argument("--max-cards", type=int, default=0, help="限制素材卡抽取数（0=全部）")
    export_p.add_argument("--no-cards", action="store_true", help="跳过素材卡抽取")
    export_p.add_argument("--account", default="default", help="账号名称（筛选导出）")

    args = parser.parse_args()
    config = Config.load()

    if args.command == "config":
        _handle_config(config, args)
    elif args.command == "auth":
        _handle_auth(config, args)
    elif args.command == "list":
        _handle_list(config, args)
    elif args.command == "sync":
        _handle_sync(config, args)
    elif args.command == "bilibili":
        _handle_bilibili(config, args)
    elif args.command == "xiaoyuzhou":
        _handle_xiaoyuzhou(config, args)
    elif args.command == "status":
        _handle_status(config, args)
    elif args.command == "knowledge":
        _handle_knowledge(config, args)
    elif args.command == "search":
        _handle_search(config, args)
    elif args.command == "write":
        _handle_write(config, args)
    elif args.command == "check":
        _handle_check(config, args)
    elif args.command == "question":
        _handle_question(config, args)
    elif args.command == "write-smart":
        _handle_write_smart(config, args)
    elif args.command == "write-draft":
        _handle_write_draft(config, args)
    elif args.command == "image":
        _handle_image(config, args)
    elif args.command == "writing-guide":
        _handle_writing_guide(config, args)
    elif args.command == "analyze":
        _handle_analyze(config, args)
    elif args.command == "serve":
        _handle_serve(config, args)
    elif args.command == "monthly":
        _handle_monthly(config, args)
    elif args.command == "export":
        _handle_export(config, args)


def _get_api(config: Config) -> ZhihuAPI:
    """从配置创建 API 实例."""
    cookie_file = Path(config.cookie_file)
    if not cookie_file.exists():
        print("❌ Cookie 文件不存在。请先运行: zhihu2obsidian auth login")
        sys.exit(1)
    jar = CookieJar.from_file(cookie_file)
    return ZhihuAPI(jar, rate_min=config.rate_limit_min, rate_max=config.rate_limit_max)


def _handle_config(config: Config, args) -> None:
    if args.config_cmd == "init":
        config.save()
        print(f"✅ 配置已创建: ~/.zhihu2obsidian/config.yaml")
        print("   请设置 vault 路径: zhihu2obsidian config set vault /path/to/Obsidian")
    elif args.config_cmd == "set":
        if args.key == "vault":
            config.vault = args.value
        elif args.key == "output_prefix":
            config.output_prefix = args.value
        elif args.key == "cookie_file":
            config.cookie_file = args.value
        elif args.key in ("rate_limit_min",):
            config.rate_limit_min = float(args.value)
        elif args.key in ("rate_limit_max",):
            config.rate_limit_max = float(args.value)
        elif args.key == "image_concurrency":
            config.image_concurrency = int(args.value)
        elif args.key == "deepseek_api_key":
            config.deepseek_api_key = args.value
        elif args.key == "knowledge_dir":
            config.knowledge_dir = args.value
        elif args.key == "unsplash_api_key":
            config.unsplash_api_key = args.value
        else:
            print(f"❌ 未知配置 key: {args.key}")
            sys.exit(1)
        config.save()
        print(f"✅ {args.key} = {args.value}")
    elif args.config_cmd == "show":
        print(f"vault:            {config.vault or '(未设置)'}")
        print(f"output_prefix:    {config.output_prefix}")
        print(f"cookie_file:      {config.cookie_file}")
        print(f"rate_limit:       {config.rate_limit_min}-{config.rate_limit_max}s")
        print(f"image_concurrency: {config.image_concurrency}")
        print(f"collections:      {config.collections or '全部'}")
        print(f"deepseek_api_key: {'已设置' if config.deepseek_api_key else '未设置'}")
        print(f"unsplash_api_key: {'已设置' if config.unsplash_api_key else '未设置（可选）'}")
        print(f"knowledge_dir:    {config.knowledge_dir or '(默认: 使用 vault 内 .knowledge 目录)'}")


def _handle_auth(config: Config, args) -> None:
    # Platform-specific cookie management
    is_bilibili = getattr(args, 'platform', 'zhihu') == 'bilibili'

    if is_bilibili:
        bili_cookie_file = BILIBILI_COOKIE_FILE
        if args.auth_cmd == "login":
            import getpass
            print("请输入 Bilibili Cookie")
            print("（从浏览器 F12 → Application → Cookies → bilibili.com 复制 SESSDATA 值）")
            cookies = {}
            val = getpass.getpass("  SESSDATA: ").strip()
            if val:
                cookies["SESSDATA"] = val
            if not cookies:
                raise ValueError("至少需要 SESSDATA")
            bili_cookie_file.parent.mkdir(parents=True, exist_ok=True)
            import json
            bili_cookie_file.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
            # Verify
            from .platforms.bilibili import BilibiliPlatform
            bp = BilibiliPlatform(config, str(bili_cookie_file))
            ok, msg = bp.check_auth()
            print(f"{'✅' if ok else '❌'} {msg}")
            return
        elif args.auth_cmd == "status":
            from .platforms.bilibili import BilibiliPlatform
            bp = BilibiliPlatform(config, str(bili_cookie_file))
            ok, msg = bp.check_auth()
            print(f"{'✅' if ok else '❌'} {msg}")
            return
        return

    # Original Zhihu auth logic
    if args.auth_cmd == "login":
        jar = CookieJar.from_input()
    elif args.auth_cmd == "import":
        jar = CookieJar.from_file(args.path)
        # Save to default location
        DEFAULT_COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
        import json
        DEFAULT_COOKIE_FILE.write_text(json.dumps(jar.cookies, indent=2), encoding="utf-8")
        config.cookie_file = str(DEFAULT_COOKIE_FILE)
        config.save()
        print(f"✅ Cookie 已导入: {DEFAULT_COOKIE_FILE}")
    elif args.auth_cmd == "status" or not args.auth_cmd:
        cookie_file = Path(config.cookie_file)
        if not cookie_file.exists():
            print("❌ Cookie 文件不存在")
            sys.exit(1)
        jar = CookieJar.from_file(cookie_file)
        ok, msg = jar.check_valid()
        print(f"{'✅' if ok else '❌'} {msg}")
        return
    else:
        return

    # For `login`, save and check
    if args.auth_cmd == "login":
        DEFAULT_COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
        import json
        DEFAULT_COOKIE_FILE.write_text(json.dumps(jar.cookies, indent=2), encoding="utf-8")
        config.cookie_file = str(DEFAULT_COOKIE_FILE)
        config.save()

    ok, msg = jar.check_valid()
    print(f"{'✅' if ok else '❌'} {msg}")


def _handle_list(config: Config, args) -> None:
    api = _get_api(config)

    if args.collection_id:
        items = api.get_collection_items(args.collection_id)
        print(f"收藏夹 #{args.collection_id}: {len(items)} 条")
        for item in items[:20]:
            print(f"  [{item.type}] {item.question_title or item.content_id}")
            print(f"    {item.url}")
            print(f"    by {item.author_name}")
        if len(items) > 20:
            print(f"  ... 还有 {len(items) - 20} 条")
    else:
        collections = api.get_collections()
        print(f"共 {len(collections)} 个收藏夹:\n")
        for c in collections:
            import datetime
            dt = datetime.datetime.fromtimestamp(c.updated_time) if c.updated_time else None
            print(f"  #{c.id:>8}  {c.title}")
            print(f"         {c.item_count} 条  |  更新 {dt.strftime('%Y-%m-%d') if dt else '?'}")
        print()


def _handle_sync(config: Config, args) -> None:
    if not config.vault:
        print("❌ vault 路径未设置。请运行: zhihu2obsidian config set vault /path/to/Obsidian")
        sys.exit(1)

    api = _get_api(config)
    engine = SyncEngine(config, api, account=args.account)

    print(f"🔁 同步到: {config.output_path}\n")

    if args.collection_id:
        results = engine.sync_collection_by_id(args.collection_id, limit=args.limit,
                                               force=args.force, dry_run=args.dry_run)
    else:
        results = engine.sync_all(limit=args.limit, force=args.force, dry_run=args.dry_run)

    print(f"\n{'='*40}")
    print(f"📊 同步完成:")
    print(f"   新增:   {results['added']}")
    print(f"   更新:   {results['updated']}")
    print(f"   跳过:   {results['skipped']}")
    print(f"   失败:   {len(results['failed'])}")
    print(f"   图片:   {results['images_ok']} OK / {results['images_fail']} 失败")
    if results['failed']:
        print(f"\n❌ 失败详情:")
        for f in results['failed']:
            print(f"  - {f['id']}: {f['reason']}")


def _handle_status(config: Config, args) -> None:
    if not config.vault:
        print("❌ vault 路径未设置")
        return
    account = getattr(args, 'account', 'default')
    from .utils import state_path_for
    state_file = state_path_for(config.output_path, account)
    if not state_file.exists():
        print("📭 尚未同步")
        return
    from .models import SyncState
    state = SyncState.load(state_file)
    total = sum(len(cs.items) for cs in state.collections.values() if not cs.archived)
    archived = sum(len(cs.items) for cs in state.collections.values() if cs.archived)
    print(f"📊 同步状态:")
    print(f"   收藏夹:   {len([c for c in state.collections.values() if not c.archived])} 活跃 / {len(state.collections)} 总计")
    print(f"   条目:     {total} 活跃 / {archived} 已归档")
    print(f"   上次同步: {state.last_sync or '从未'}")
    for cid, cs in state.collections.items():
        print(f"  #{cid} {cs.title}: {len(cs.items)} 条{' 📦' if cs.archived else ''}")


def _handle_knowledge(config: Config, args) -> None:
    """知识库管理 (分派到 builder 模块)."""
    if not config.vault:
        print("❌ vault 路径未设置")
        sys.exit(1)

    vault_dir = config.output_path
    out = config.knowledge_path

    if args.knowledge_cmd in ("build", "rebuild"):
        # Lazy import (可选依赖)
        from .knowledge.builder import run_knowledge_build, run_knowledge_rebuild
        if args.knowledge_cmd == "build":
            run_knowledge_build(vault_dir, out)
        else:
            run_knowledge_rebuild(vault_dir, out)
    elif args.knowledge_cmd == "status" or not args.knowledge_cmd:
        if not out.exists():
            print("📭 知识库尚未构建")
            return
        try:
            from .knowledge.embedder import Embedder
            embedder = Embedder(out)
            s = embedder.stats()
            print(f"📊 知识库统计:")
            print(f"   向量块数: {s['total_chunks']}")
            print(f"   存储路径: {s['storage_path']}")
            wc = out / "wordcloud.png"
            if wc.exists():
                print(f"   词云:     {wc}")
            gh = out / "graph.html"
            if gh.exists():
                print(f"   图谱:     {gh}")
        except Exception as e:
            print(f"❌ 读取知识库失败: {e}")
    elif args.knowledge_cmd == "cards":
        _handle_knowledge_cards(config, args)
    elif args.knowledge_cmd == "topics":
        _handle_knowledge_topics(config, args)
    elif args.knowledge_cmd == "tree":
        _handle_knowledge_tree(config, args)
    else:
        print("未知子命令。用法: zhihu2obsidian knowledge {build|rebuild|status|cards|topics}")


# ── Bilibili ───────────────────────────────────────────
BILIBILI_COOKIE_FILE = Path.home() / ".zhihu2obsidian" / "bilibili_cookies.json"


def _get_bilibili_cookie_file(config: Config) -> Path:
    return BILIBILI_COOKIE_FILE


def _handle_bilibili(config: Config, args) -> None:
    """Bilibili 收藏夹操作."""
    cookie_file = str(BILIBILI_COOKIE_FILE)
    from .platforms.bilibili import BilibiliPlatform
    bp = BilibiliPlatform(config, cookie_file)

    if args.bilibili_cmd == "list":
        ok, msg = bp.check_auth()
        if not ok:
            print(f"❌ {msg}")
            print(f"   请先运行: zhihu2obsidian auth login --platform bilibili")
            sys.exit(1)
        print(f"✅ {msg}\n")
        cols = bp.list_collections()
        if not cols:
            print("📭 没有收藏夹")
            return
        print(f"📁 共 {len(cols)} 个收藏夹:\n")
        for c in cols:
            dt = "?"
            if c.updated_time:
                import datetime
                dt = datetime.datetime.fromtimestamp(c.updated_time).strftime("%Y-%m-%d")
            print(f"  #{c.id}  {c.title}")
            print(f"         {c.item_count} 条  |  更新 {dt}")
            if c.description:
                print(f"         {c.description[:60]}")
            print()
    elif args.bilibili_cmd == "sync":
        from .platforms.bilibili import sync_bilibili
        sync_bilibili(config, bp, account=getattr(args, 'account', 'default'),
                       collection_id=getattr(args, 'collection_id', None),
                       limit=getattr(args, 'limit', 0), force=getattr(args, 'force', False))


# ── 知识搜索与写作 ────────────────────────────────────
def _handle_search(config: Config, args) -> None:
    """语义搜索 (去重 + 加权 + 过滤)."""
    # Lazy import (可选依赖)
    from .agent.retriever import Retriever, adjusted_score, PLATFORM_ICON

    out = config.knowledge_path
    if not out.exists():
        print("❌ 知识库尚未构建。请先运行: zhihu2obsidian knowledge build")
        sys.exit(1)

    retriever = Retriever(out)
    filters = {}
    if args.author:
        filters["author"] = args.author
    if args.collection:
        filters["collection"] = args.collection
    if args.platform:
        filters["platform"] = args.platform

    if args.flat:
        results = retriever.search(args.query, n_results=args.n, **filters)
    else:
        results = retriever.search_grouped(args.query, n_results=args.n, **filters)

    if not results:
        print("📭 未找到匹配结果")
        return

    print(f"🔎 搜索 \"{args.query}\" — {len(results)} 条结果:")
    if not args.flat:
        print(f"   (已去重, 加权排序)")
    if filters:
        parts = []
        for k, v in filters.items():
            parts.append(f"{k}={v}")
        print(f"   筛选: {', '.join(parts)}")
    print()

    for i, r in enumerate(results, 1):
        meta = r["metadata"]
        title = meta.get("title", "(无标题)")
        author = meta.get("author", "")
        section = meta.get("section", "")
        platform = meta.get("platform", "")
        collection = meta.get("collection", "")
        content_id = meta.get("content_id", "")

        icon = PLATFORM_ICON.get(platform, "📄")
        score = adjusted_score(r)

        print(f"  {icon}  #{i}  score={score:.4f}  dist={r['distance']:.4f}")
        print(f"     {title}")
        if author:
            print(f"     作者: {author}")
        if section:
            print(f"     章节: {section}")
        if collection:
            print(f"     收藏: {collection}")
        if content_id:
            # Short source tag
            tag = content_id[:50] + ("..." if len(content_id) > 50 else "")
            print(f"     [{platform}] {tag}")

        # Show first 2 lines of content
        text = r["text"].split("\n")[:2]
        for line in text:
            stripped = line.strip()
            if stripped:
                preview = stripped[:120]
                print(f"     {preview}")
        print()


def _handle_xiaoyuzhou(config: Config, args) -> None:
    """小宇宙播客热门榜 + 风格分析 + 大纲生成."""
    import datetime
    from .platforms.xiaoyuzhou import (
        fetch_hot_episodes,
        analyze_style,
        format_style_report,
        generate_podcast_outline,
    )

    if args.xiaoyuzhou_cmd == "trending":
        print("🔍 抓取小宇宙热门榜...")
        eps = fetch_hot_episodes()
        print(f"\n📊 共 {len(eps)} 期热门播客\n")
        for e in eps[:20]:
            print(f"  #{eps.index(e)+1:<3} {e.play_count:>8,} 🎧 {e.duration_str:>6} {e.genre or '其他':<10s} {e.title[:50]}")
        print(f"\n... 共 {len(eps)} 期, 显示前 20")

    elif args.xiaoyuzhou_cmd == "analyze":
        print("🔍 抓取小宇宙热门榜并分析风格...")
        eps = fetch_hot_episodes()
        profile = analyze_style(eps)
        print()
        print(format_style_report(profile))

    elif args.xiaoyuzhou_cmd == "outline":
        topic = args.topic

        # 检索知识库
        if config.knowledge_path.exists():
            try:
                from .agent.retriever import Retriever
                print(f"🔎 检索知识库: '{topic}'...")
                retriever = Retriever(config.knowledge_path)
                results = retriever.search_with_context(topic, n_results=min(args.n, 10))
                texts = []
                for group in results:
                    for chunk in group.get("chunks", []):
                        texts.append(chunk["text"])
                print(f"   找到 {len(texts)} 段相关素材\n")
            except Exception as e:
                print(f"⚠ 知识库检索失败: {e}")
                texts = []
        else:
            texts = []
            print("⚠ 知识库未构建, 使用通用大纲\n")

        # 获取风格画像
        eps = fetch_hot_episodes()
        profile = analyze_style(eps)

        # 生成大纲
        use_llm = args.llm and bool(config.deepseek_api_key)
        api_key = config.deepseek_api_key if use_llm else ""

        print(f"✍️  生成 {'LLM' if use_llm else '模板'} 大纲...")
        outline = generate_podcast_outline(
            texts, topic, style_profile=profile,
            use_llm=use_llm, api_key=api_key,
        )
        print(f"\n{outline}\n")

        # Save to file with frontmatter
        fname = f"podcast_{topic[:20].strip()}.md"
        fname = re.sub(r'[\\/:*?"<>|]', "_", fname)
        fpath = config.output_path / fname
        now_iso = datetime.datetime.now().isoformat()
        fm = (
            "---\n"
            f'title: "播客大纲 — {topic}"\n'
            f'topic: "{topic}"\n'
            'platform: "xiaoyuzhou"\n'
            'type: "podcast_outline"\n'
            f'created: "{now_iso}"\n'
            "---\n\n"
        )
        fpath.write_text(fm + outline, encoding="utf-8")
        print(f"💾 已保存: {fpath}")


def _handle_question(config: Config, args) -> None:
    """分析问题类型 + 格式推荐."""
    import json

    if args.question_cmd == "analyze":
        from .agent.classifier import QuestionClassifier
        from .agent.format_selector import FormatSelector

        classifier = QuestionClassifier()
        selector = FormatSelector(config.knowledge_path if config.knowledge_path.exists() else None)

        # 分类
        candidates = classifier.classify(args.question, top_n=args.top_n)
        best = classifier.classify_best(args.question)

        if not candidates:
            print("❌ 无法分析该问题类型")
            return

        # 格式推荐
        format_rec = {}
        if best:
            format_rec = selector.recommend(best["type"])

        # 相似素材（可选）
        similar = []
        if not args.no_knowledge and config.knowledge_path.exists():
            try:
                from .agent.retriever import Retriever
                retriever = Retriever(config.knowledge_path)
                results = retriever.search_with_context(args.question, n_results=3)
                for group in results:
                    for chunk in group.get("chunks", []):
                        similar.append({
                            "title": chunk.get("title", ""),
                            "author": chunk.get("author", ""),
                            "platform": chunk.get("platform", ""),
                            "text_preview": chunk["text"][:120],
                        })
            except Exception:
                pass

        result = {
            "question": args.question,
            "classification": candidates,
            "best_type": best,
            "format_recommendation": format_rec,
            "similar_sources": similar[:5],
        }

        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        # ── 可读输出 ──
        print(f"\n📌 问题: {args.question}\n")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("🔎 类型分析:")
        for cand in candidates:
            marker = "★" if best and cand["type"] == best["type"] else " "
            print(f"  {marker} {cand['type_name']} (置信度: {cand['confidence']:.0%})")
            print(f"    基调: {cand['estimated_tone']}")
            print(f"    预估长度: {cand['estimated_length']}")
            if cand.get("avoid"):
                print(f"    禁忌: {'; '.join(cand['avoid'])}")
            print()

        if format_rec:
            print("📐 格式推荐:")
            print(f"  {format_rec.get('description', '')}\n")
            hook = format_rec.get("hook", {})
            if hook.get("recommended"):
                for h in hook["recommended"]:
                    print(f"  开头钩子: {h['name']} ({h['risk_level']}风险)")
                    print(f"    结构: {h['structure']}")
                    print(f"    理由: {h['reason']}")
                    print()
            style = format_rec.get("style", {})
            if style.get("recommended"):
                print(f"  文风: {' + '.join(s['name'] for s in style['recommended'])}")
                if style.get("blend_suggestion"):
                    print(f"    搭配: {style['blend_suggestion']}")
                print()
            struct_rec = format_rec.get("structure", {})
            if struct_rec.get("recommended"):
                st = struct_rec["recommended"]
                print(f"  结构: {st['name']}")
                print(f"    理由: {st.get('reason', '')}")
                print()
            arc_rec = format_rec.get("emotional_arc", {})
            if arc_rec.get("recommended"):
                arc = arc_rec["recommended"]
                print(f"  情绪曲线: {arc['name']}")
                for ph in arc.get("phases", []):
                    print(f"    · {ph.get('phase', '')}（{ph.get('emotion', '')}）")
                print(f"  提示: {arc.get('note', '')}")
                print()
            tech_rec = format_rec.get("techniques", {})
            if tech_rec.get("recommended"):
                print(f"  推荐技巧:")
                for t in tech_rec["recommended"]:
                    risk_mark = {"low": "✅", "medium": "⚠", "high": "🔴"}
                    print(f"    {risk_mark.get(t['risk_level'], '')} {t['name']}: {t['description']}")
                    if t.get("safety_instruction"):
                        print(f"      安全: {t['safety_instruction'][:80]}...")
                print()

        if similar:
            print("📚 知识库相似素材:")
            for s in similar[:3]:
                print(f"  [{s.get('platform', '')}] {s.get('title', '')} — {s.get('author', '')}")
                print(f"    {s['text_preview']}...")
                print()

        print("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("💡 提示: 使用 zhihu2obsidian write-smart \"问题\" 获取完整写作策略")


def _handle_write_draft(config: Config, args) -> None:
    """生成完整草稿（策略 + 完整回答）. """
    import json

    if not config.deepseek_api_key:
        print("❌ DeepSeek API Key 未设置")
        sys.exit(1)

    from .agent.retriever import Retriever
    from .agent.smart_writer import SmartWriter

    # Retriever
    retriever = None
    if not args.no_context and config.knowledge_path.exists():
        try:
            retriever = Retriever(config.knowledge_path)
        except Exception:
            pass

    writer = SmartWriter(
        api_key=config.deepseek_api_key,
        model=args.model,
        knowledge_dir=str(config.knowledge_path) if config.knowledge_path.exists() else None,
        retriever=retriever,
        platform=args.platform,
    )

    if config.unsplash_api_key:
        writer.set_image_api_key(config.unsplash_api_key)

    print(f"📌 问题: {args.question}\n")
    print(f"📌 平台: {args.platform}")
    print("✍️  生成策略 + 完整草稿（需要 60-120s）...")

    try:
        result = writer.generate_draft(
            question=args.question,
            temperature=args.temperature,
            style_preference=args.style,
            hook_preference=args.hook,
            with_context=not args.no_context,
            platform=args.platform,
        )
    except Exception as e:
        print(f"❌ 生成失败: {e}")
        return

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # ── 可读输出 ──
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━")
    strategy = result.get("strategy", {})
    outline = strategy.get("outline", [])
    if outline:
        print("📋 策略大纲:")
        for i, sec in enumerate(outline, 1):
            print(f"  {i}. {sec.get('section', '')}")
            for kp in sec.get("key_points", []):
                print(f"     · {kp}")
            if sec.get("technique_hint"):
                print(f"     🛠 {sec['technique_hint']}")
            print()

    draft = result.get("draft", "")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("✍️  草稿:\n")
    print(draft)

    sections = result.get("sections", [])
    if sections:
        print(f"\n📑 章节数: {len(sections)}")


def _handle_image(config: Config, args) -> None:
    """配图搜索与建议."""
    import json

    from .agent.image_searcher import ImageSearcher

    searcher = ImageSearcher(
        unsplash_api_key=config.unsplash_api_key or "",
    )

    if args.image_cmd == "search":
        results = searcher.search_with_sources(args.query)

        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
            return

        images = results.get("images", [])
        if not images:
            print(f"📷 未找到 '{args.query}' 的配图")
            return

        print(f"📷 搜索: {args.query}")
        print(f"来源: {results['source']}")
        print()
        for img in images:
            url = img.get("url", "")
            desc = img.get("description", "")
            source = img.get("source", "?")
            if url:
                print(f"  · {desc}")
                print(f"    {url}")
                if img.get("author"):
                    print(f"    摄影: {img['author']}")
                print(f"    [来源: {source}]")
            elif img.get("suggest_marker"):
                print(f"  · 建议配图: {img['suggest_marker']}")
            print()

    elif args.image_cmd == "suggest":
        suggestion = searcher.suggest_for_section(args.section, args.key_points)

        if args.json:
            print(json.dumps(suggestion, ensure_ascii=False, indent=2))
            return

        print(f"📷 章节: {args.section}")
        print(f"配图类型: {suggestion['image_type_name']}")
        print(f"搜索关键词: {suggestion['search_query']}")
        print()

        images = suggestion.get("images", [])
        if images:
            print(f"找到 {len(images)} 张图:")
            for img in images:
                print(f"  · {img.get('description', '')}")
                print(f"    {img.get('url', '')}")
                print()
        else:
            print(f"建议: {suggestion.get('suggest_marker', '')}")
            print()


def _handle_write_smart(config: Config, args) -> None:
    """格式感知写作策略生成."""
    import json

    if not config.deepseek_api_key:
        print("❌ DeepSeek API Key 未设置")
        sys.exit(1)

    from .agent.retriever import Retriever
    from .agent.smart_writer import SmartWriter

    # Retriever
    retriever = None
    if not args.no_context and config.knowledge_path.exists():
        try:
            retriever = Retriever(config.knowledge_path)
        except Exception:
            pass

    writer = SmartWriter(
        api_key=config.deepseek_api_key,
        model=args.model,
        knowledge_dir=str(config.knowledge_path) if config.knowledge_path.exists() else None,
        retriever=retriever,
        platform=args.platform,
    )

    # 可选 Unsplash
    if config.unsplash_api_key:
        writer.set_image_api_key(config.unsplash_api_key)

    print(f"📌 问题: {args.question}\n")
    print(f"📌 平台: {args.platform}")
    print("✍️  生成写作策略...")

    output_mode = "outline" if args.outline_only else "full"

    try:
        result = writer.generate(
            question=args.question,
            temperature=args.temperature,
            style_preference=args.style,
            hook_preference=args.hook,
            with_context=not args.no_context,
            output_mode=output_mode,
            platform=args.platform,
        )
    except Exception as e:
        print(f"❌ 生成失败: {e}")
        return

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # ── 可读输出 ──
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━")
    analysis = result.get("question_analysis", {})
    if analysis:
        type_name = analysis.get("type_name", "未知")
        tone = analysis.get("estimated_tone", "")
        print(f"🔎 问题分类: {type_name} | 基调: {tone}")

    format_rec = result.get("format_recommendation", {})
    if format_rec:
        print(f"📐 格式策略:")
        print(f"  {format_rec.get('description', '')}")

    # Outline
    outline = result.get("outline", [])
    if outline:
        print(f"\n📋 策略大纲:")
        for i, sec in enumerate(outline, 1):
            print(f"  {i}. {sec.get('section', '')}")
            for kp in sec.get("key_points", []):
                print(f"     · {kp}")
            if sec.get("technique_hint"):
                print(f"     🛠 {sec['technique_hint']}")
            print()

    # Material package
    material = result.get("material_package", {})
    if material:
        core = material.get("core_viewpoints", [])
        if core:
            print(f"💡 核心观点 ({len(core)}):")
            for v in core:
                print(f"  · {v}")
            print()
        chain = material.get("argument_chain", [])
        if chain:
            print(f"🔗 论据链 ({len(chain)}):")
            for a in chain:
                src = a.get("source_title", "")
                print(f"  · {a.get('point', '')}")
                print(f"    证据: {a.get('evidence', '')[:80]}...")
                if src:
                    print(f"    来源: {src}")
                print()
        cases = material.get("case_stories", [])
        if cases:
            print(f"📖 案例 ({len(cases)}):")
            for c in cases:
                print(f"  · {c.get('story', '')[:80]}...")
                print(f"    用法: {c.get('usage', '')}")
                print()
        quotes = material.get("key_quotes", [])
        if quotes:
            print(f"💬 金句参考:")
            for q in quotes:
                print(f"  · 「{q.get('quote', '')}」— {q.get('source', '')}")

    # Image suggestions
    img_suggestions = result.get("image_suggestions", [])
    if img_suggestions:
        print(f"\n📷 配图建议:")
        for sec_img in img_suggestions:
            sec_name = sec_img.get("section", "")
            img_type = sec_img.get("image_type_name", "")
            print(f"  {sec_name} [{img_type}]")
            images = sec_img.get("images", [])
            if images:
                for img in images[:2]:
                    url = img.get("url", "")
                    desc = img.get("description", "")
                    source = img.get("source", "")
                    if source == "suggest":
                        print(f"    建议: {img.get('suggest_marker', '')}")
                    else:
                        print(f"    · {desc}")
                        print(f"      {url}")
            else:
                print(f"    建议: {sec_img.get('suggest_marker', '')}")
            print()

    # Risks
    risks = result.get("risks", [])
    if risks:
        print(f"\n⚠ 风险提示:")
        for r in risks:
            level_mark = {"low": "ℹ", "medium": "⚠", "high": "🔴"}
            print(f"  {level_mark.get(r.get('level', 'low'), '')} {r.get('message', '')}")


def _handle_write(config: Config, args) -> None:
    """AI 写作助手."""
    if not config.deepseek_api_key:
        print("❌ DeepSeek API Key 未设置。请先运行:")
        print("   zhihu2obsidian config set deepseek_api_key sk-xxx")
        sys.exit(1)

    # ── 素材包模式 ──
    if getattr(args, "package", False):
        _handle_write_package(config, args)
        return

    # ── 文章模式（原有逻辑）──
    # Lazy import (可选依赖)
    from .agent.writer import Writer

    out = config.knowledge_path

    writer = Writer(api_key=config.deepseek_api_key, model=args.model)

    context = ""
    if not args.no_context:
        if out.exists():
            # Lazy import (可选依赖)
            from .agent.retriever import Retriever

            print("🔎 检索知识库...")
            retriever = Retriever(out)
            results = retriever.search_with_context(args.topic, n_results=min(args.n if hasattr(args, 'n') else 5, 10))

            context_parts = []
            for group in results:
                for chunk in group.get("chunks", []):
                    context_parts.append(chunk["text"])
            context = "\n\n---\n\n".join(context_parts)

            if context:
                print(f"   找到 {len(results)} 篇相关文章\n")
            else:
                print("   未找到相关素材，将仅用 AI 生成\n")
        else:
            print("⚠ 知识库未构建，将仅用 AI 生成（无参考资料）\n")

    print("✍️  生成中...")
    try:
        answer = writer.write_answer(
            question=args.topic,
            context=context,
            personal_take=args.personal or "",
            temperature=args.temperature,
        )

        if args.raw:
            print(answer)
        else:
            print(f"\n{'='*40}")
            print(answer)
            print(f"{'='*40}")

        if args.copy:
            try:
                import pyperclip
                pyperclip.copy(answer)
                print("\n📋 已复制到剪贴板")
            except ImportError:
                print("\n⚠ 需要 pyperclip: pip install pyperclip")
    except Exception as e:
        print(f"\n❌ 生成失败: {e}")


def _handle_write_package(config: Config, args) -> None:
    """写作素材包模式."""
    from .agent.package import WritingPackageBuilder
    from .agent.retriever import Retriever

    out = config.knowledge_path

    # Build retriever if knowledge base exists
    retriever = None
    if out.exists():
        try:
            retriever = Retriever(out)
        except Exception:
            pass

    cards_dir = out / "cards"
    if not cards_dir.exists():
        cards_dir = None

    topics_dir = out / "topics"
    if not topics_dir.exists():
        topics_dir = None

    builder = WritingPackageBuilder(
        api_key=config.deepseek_api_key,
        model=args.model,
        retriever=retriever,
        cards_dir=cards_dir,
        topics_dir=topics_dir,
    )

    print("🔎 检索素材（知识库 + 卡片 + 主题）...")
    package = builder.build(
        topic=args.topic,
        personal_take=args.personal or "",
        with_draft=getattr(args, "draft", False),
    )

    # Render and output
    output = builder.render_text(package)

    if args.raw:
        print(output)
    else:
        print(output)

    if args.copy:
        try:
            import pyperclip
            pyperclip.copy(output)
            print("\n📋 已复制到剪贴板")
        except ImportError:
            print("\n⚠ 需要 pyperclip: pip install pyperclip")

    # Summary
    print(f"\n{'─'*40}")
    print(f"📊 素材包统计:")
    print(f"   核心观点: {len(package.core_viewpoints)}")
    print(f"   论据链:   {len(package.argument_chain)}")
    print(f"   案例库:   {len(package.case_stories)}")
    print(f"   金句:     {len(package.key_quotes)}")
    print(f"   使用素材: {len(package.sources)} 篇")
    if package.source_topics:
        print(f"   关联主题: {', '.join(package.source_topics[:5])}")

    # ── Check draft if requested ──
    if getattr(args, "check", False) and package.draft:
        _handle_draft_check(package, config)


def _handle_draft_check(package, config: Config) -> None:
    """对素材包初稿执行质量检查."""
    from .agent.checker import WritingChecker
    from .agent.retriever import Retriever

    retriever = None
    out = config.knowledge_path
    if out.exists():
        try:
            retriever = Retriever(out)
        except Exception:
            pass

    checker = WritingChecker(
        retriever=retriever,
        api_key=config.deepseek_api_key,
    )

    print(f"\n{'='*40}")
    print("🔍 运行质量检查...")
    report = checker.check(package.draft, title=package.topic)

    # Generate rewrites for flagged paragraphs
    if report.flagged_high > 0 and config.deepseek_api_key:
        print("  生成改写建议（高相似段落）...")
        checker._generate_rewrite(report.paragraphs)

    print(checker.render_report(report))


def _handle_knowledge_cards(config: Config, args) -> None:
    """素材卡片管理."""
    if not config.vault:
        print("❌ vault 路径未设置")
        return

    vault_dir = config.output_path
    if not vault_dir.exists():
        print(f"❌ vault 不存在: {vault_dir}")
        return

    # status/search are local reads, no API key needed
    if args.cards_cmd in ("status", "search"):
        from .knowledge.cards import CardExtractor

        ext = CardExtractor(
            api_key="",
            knowledge_dir=config.knowledge_path,
        )
        if args.cards_cmd == "status":
            cards_dir = config.knowledge_path / "cards"
            if not cards_dir.exists():
                print("📂 暂无卡片目录")
                return
            manifest = cards_dir / "manifest.json"
            if manifest.exists():
                import json
                data = json.loads(manifest.read_text())
                total = len(data.get("cards", {}))
                print(f"📂 素材卡片: {total} 张")
            else:
                print("📂 暂无卡片")
        elif args.cards_cmd == "search":
            results = ext.search(args.query)
            if not results:
                print("🔍 未找到匹配卡片")
                return
            for r in results[:20]:
                tags = ", ".join(r.topics)
                print(f"  📄 {r.title}")
                if tags:
                    print(f"    标签: {tags}")
                print()
        return

    # build/rebuild need DeepSeek API Key
    if not config.deepseek_api_key:
        print("❌ 需要 DeepSeek API Key: zhihu2obsidian config set deepseek_api_key sk-xxx")
        return

    from .knowledge.cards import CardExtractor

    extractor = CardExtractor(
        api_key=config.deepseek_api_key,
        knowledge_dir=config.knowledge_path,
    )

    if args.cards_cmd in ("build", "rebuild"):
        if args.cards_cmd == "rebuild":
            ext = CardExtractor(
                api_key=config.deepseek_api_key,
                knowledge_dir=config.knowledge_path,
            )
            ext.reset()
            extractor = ext
            print("🧹 已清空所有卡片\n")

        # Clean orphaned
        orphaned = extractor.clean_orphaned(vault_dir)
        if orphaned:
            print(f"🧹 清理 {orphaned} 个孤立卡片\n")

        # Find changed files
        changed = extractor.get_changed_files(vault_dir)
        # Apply --limit
        if args.cards_cmd == "build" and args.limit and args.limit < len(changed):
            changed = changed[:args.limit]
        total = len(changed)

        if not total:
            st = extractor.stats()
            print(f"   无变更 (已有 {st['total_cards']} 张卡片)")
            return

        print(f"📇 需抽取 {total} 张卡片...")
        ok = 0
        fail = 0
        for idx, fpath in enumerate(changed, 1):
            rel = str(fpath.relative_to(vault_dir))
            print(f"  [{idx}/{total}] {rel}", end=" ... ")
            card = extractor.extract_card(fpath, vault_dir)
            if card:
                print(f"✅ {card.card_type} ({len(card.core_points) or len(card.key_points)} 观点)")
                ok += 1
            else:
                print("❌")
                fail += 1

        print(f"\n✅ {ok} 张卡片抽取成功", end="")
        if fail:
            print(f", ❌ {fail} 失败", end="")
        print()

    elif args.cards_cmd == "status":
        st = extractor.stats()
        print(f"📇 素材卡片统计")
        print(f"   总数: {st['total_cards']}")
        print(f"   知乎(全文): {st['full_cards']}")
        print(f"   B站(轻量): {st['light_cards']}")
        print(f"   存储: {st['cards_dir']}")

    elif args.cards_cmd == "search":
        if not args.query:
            print("❌ 请提供搜索关键词")
            return
        cards = extractor.search(args.query, top_n=args.n)
        if not cards:
            print("   未找到相关卡片")
            return
        print(f"🔎 卡片搜索 \"{args.query}\" — {len(cards)} 条结果:\n")
        for i, c in enumerate(cards, 1):
            icon = "📺" if c.platform == "bilibili" else "💬"
            tag_str = ", ".join(c.topics[:4]) if c.topics else ""
            print(f"  {icon} #{i}  {c.title}")
            print(f"     作者: {c.author}  |  平台: {c.platform}")
            if c.core_points:
                print(f"     观点: {c.core_points[0][:60]}...")
            elif c.key_points:
                print(f"     要点: {c.key_points[0][:60]}...")
            elif c.arguments:
                first_arg = c.arguments[0]
                if isinstance(first_arg, dict):
                    txt = first_arg.get("point", str(first_arg))[:60]
                else:
                    txt = str(first_arg)[:60]
                print(f"     论据: {txt}...")
            if tag_str:
                print(f"     标签: {tag_str}")
            print()


def _handle_knowledge_topics(config: Config, args) -> None:
    """主题聚类管理."""
    if not config.vault:
        print("❌ vault 路径未设置")
        return

    from .knowledge.embedder import Embedder
    from .knowledge.topics import TopicClusterer

    out = config.knowledge_path
    out.mkdir(parents=True, exist_ok=True)
    embedder = Embedder(out)
    clusterer = TopicClusterer(
        embedder=embedder,
        knowledge_dir=out,
        api_key=config.deepseek_api_key,
    )

    vault_dir = config.output_path

    if args.topics_cmd in ("build", "rebuild"):
        if args.topics_cmd == "rebuild":
            clusterer.reset()
            print("🧹 已清空主题页\n")

        # Quick validation
        count = embedder.count()
        if count < 3:
            print(f"❌ 知识库向量不足 ({count})。请先运行 knowledge build。")
            return

        topics = clusterer.cluster()
        if topics:
            print(f"\n✅ 生成 {len(topics)} 个主题页")
            print(f"   存储: {clusterer.topics_dir}")
        else:
            print("❌ 主题聚类失败")

    elif args.topics_cmd == "list":
        topics = clusterer.list_topics()
        if not topics:
            print("   无主题页。请先运行: zhihu2obsidian knowledge topics build")
            return
        print(f"📂 共 {len(topics)} 个主题:\n")
        for t in topics:
            kw = ", ".join(t.get("keywords", [])[:4]) or "-"
            pf = ", ".join(t.get("source_platforms", []))
            print(f"  {t['id']}: {t['title']}")
            print(f"     素材: {t['content_count']} 篇 | 标签: {kw} | 平台: {pf}")
            print()

    elif args.topics_cmd == "view":
        if not args.id:
            print("❌ 请提供主题 ID: zhihu2obsidian knowledge topics view topic_001")
            return
        topic = clusterer.get_topic(args.id)
        if not topic:
            print(f"❌ 主题不存在: {args.id}")
            return
        print(f"\n📌 {topic.title}")
        print(f"   主题 ID: {topic.id}")
        print(f"   素材数: {topic.content_count}")
        print(f"   平台: {', '.join(topic.source_platforms)}")
        print(f"\n📝 摘要: {topic.summary}")
        if topic.keywords:
            print(f"\n🏷 关键词: {', '.join(topic.keywords)}")
        if topic.viewpoints:
            print(f"\n💡 主要观点:")
            for vp in topic.viewpoints:
                print(f"  • {vp}")
        if topic.counterpoints:
            print(f"\n⚡ 反方观点/争议:")
            for cp in topic.counterpoints:
                print(f"  • {cp}")
        if topic.writing_ideas:
            print(f"\n✍️ 可写选题:")
            for wi in topic.writing_ideas:
                print(f"  • {wi}")
        if topic.representative_contents:
            print(f"\n📄 代表素材:")
            for rc in topic.representative_contents:
                print(f"  [{rc.get('platform', '?')}] {rc.get('title', '')} — {rc.get('author', '')}")
        print()

    else:
        print("用法: zhihu2obsidian knowledge topics {build|rebuild|list|view}")


def _handle_knowledge_tree(config: Config, args) -> None:
    """知识树管理."""
    if not config.vault:
        print("❌ vault 路径未设置")
        return

    from .tree.builder import KnowledgeTreeBuilder

    builder = KnowledgeTreeBuilder(config.knowledge_path)
    cmd = args.tree_cmd or "list"

    if cmd == "build":
        tree = builder.build()
        print(f"🌳 知识树已生成: {builder.index_file}")
        print(f"   节点: {len(tree.get('nodes', []))}")
    elif cmd == "list":
        nodes = builder.list_nodes()
        if not nodes:
            print("📭 暂无知识树。请先运行: zhihu2obsidian knowledge tree build")
            return
        print(f"🌳 共 {len(nodes)} 个知识树节点:\n")
        for node in nodes:
            keywords = ", ".join(node.get("keywords", [])[:5]) or "-"
            print(f"  {node['id']}: {node.get('title', '')}")
            print(f"     素材: {len(node.get('content_ids', []))} 条 | 关键词: {keywords}")
            print()
    elif cmd == "view":
        node = builder.get_node(args.id)
        if not node:
            print(f"❌ 节点不存在: {args.id}")
            return
        print(f"\n🌳 {node.get('title', '')}")
        print(f"   节点 ID: {node.get('id')}")
        if node.get("parent_id"):
            print(f"   父节点: {node.get('parent_id')}")
        print(f"   素材数: {len(node.get('content_ids', []))}")
        print(f"\n📝 摘要: {node.get('summary', '')}")
        if node.get("keywords"):
            print(f"\n🏷 关键词: {', '.join(node.get('keywords', []))}")
        if node.get("representative_chunks"):
            print("\n📄 代表素材:")
            for rc in node.get("representative_chunks", [])[:5]:
                print(f"  [{rc.get('platform', '?')}] {rc.get('title', '')} — {rc.get('author', '')}")
        print()
    elif cmd == "graph":
        from .knowledge.graph import save_topic_graph_html
        tree_path = config.knowledge_path / "tree" / "index.json"
        if not tree_path.exists():
            print("❌ 知识树不存在。请先运行: zhihu2obsidian knowledge tree build")
            return
        output_path = config.knowledge_path / "topic-graph.html"
        save_topic_graph_html(tree_path, output_path)
        print(f"🌐 交互式主题图谱已生成: {output_path}")
        print(f"   主题数: {len(builder.list_nodes())}")
        print(f"   使用浏览器打开查看")
    else:
        print("用法: zhihu2obsidian knowledge tree {build|list|view|graph}")


def _handle_check(config: Config, args) -> None:
    """写作质量检查."""
    from .agent.checker import check_text
    from .agent.retriever import Retriever

    # Get text
    text = ""
    title = ""
    if args.file:
        try:
            fpath = Path(args.file)
            text = fpath.read_text(encoding="utf-8")
            title = fpath.stem
        except FileNotFoundError:
            print(f"❌ 文件不存在: {args.file}")
            return
    elif args.text:
        text = args.text
    else:
        print("❌ 请提供 --text 或 --file")
        return

    # Build retriever
    retriever = None
    out = config.knowledge_path
    if out.exists():
        try:
            retriever = Retriever(out)
        except Exception:
            pass

    print("🔍 分析中...")
    report = check_text(
        text=text,
        title=title,
        retriever=retriever,
        api_key=config.deepseek_api_key,
        with_rewrite=getattr(args, "rewrite", False),
    )

    # Render
    from .agent.checker import WritingChecker
    checker = WritingChecker()
    output = checker.render_report(report)

    if args.raw:
        print(output)
    else:
        print(output)


def _handle_writing_guide(config: Config, args) -> None:
    """写作指南查询."""
    from .writing_guide import WritingGuide, get_by_id

    guide = WritingGuide(
        config.knowledge_path if config.knowledge_path.exists() else None
    )

    if args.wg_cmd == "platform":
        pid = args.platform_id
        if pid == "list":
            platforms = guide.get_platforms()
            print(f"📋 共 {len(platforms)} 个平台:\n")
            for p in platforms.values():
                print(f"  {p['id']}: {p['name']} ({p['type']})")
                print(f"    受众: {p.get('audience', '')}")
                print(f"    默认风格: {p.get('style_default', '')}")
                print(f"    推荐字数: {p.get('length_default', '')}")
                print()
            return

        pf = guide.get_platform(pid)
        if not pf:
            print(f"❌ 未知平台: {pid}")
            return

        print(f"\n📌 {pf['name']} 平台画像")
        print(f"{'=' * 40}")
        print(f"  类型: {pf.get('type', '')}")
        print(f"  受众: {pf.get('audience', '')}")
        print(f"  默认调性: {pf.get('tone_default', '')}")
        print(f"  默认文风: {pf.get('style_default', '')}")
        print(f"  推荐字数: {pf.get('length_default', '')}")
        print(f"  段落节奏: {pf.get('paragraph_flow', '')}")
        print(f"  平台礼仪: {pf.get('etiquette', '')}")
        if pf.get("taboos"):
            print(f"  禁忌: {'; '.join(pf['taboos'])}")
        print(f"\n  推荐结构:")
        for sid in pf.get("structure_defaults", []):
            struct = get_by_id(guide.data.get("structures", []), sid)
            if struct:
                print(f"    · {struct['name']}")
        print(f"\n  推荐开头:")
        for hid in pf.get("hooks_preferred", []):
            hk = get_by_id(guide.data.get("hooks", []), hid)
            if hk:
                print(f"    · {hk['name']}")
        print(f"\n  避免开头:")
        for hid in pf.get("hooks_avoid", []):
            hk = get_by_id(guide.data.get("hooks", []), hid)
            if hk:
                print(f"    · {hk['name']}")
        print(f"\n  配图风格: {pf.get('image_style', '')}")
        print(f"  举例问题: {pf.get('example_question', '')}")

        # 显示该平台支持的提问类型
        qtypes = guide.filter_by_platform(
            guide.data.get("question_types", []), pid
        )
        if qtypes:
            print(f"\n  支持的问题类型 ({len(qtypes)}):")
            for qt in qtypes:
                print(f"    · {qt['name']} ({qt['id']})")
        print()


def _handle_analyze(config: Config, args) -> None:
    """分析选中文本."""
    import json

    retriever = None
    if config.knowledge_path.exists():
        try:
            from .agent.retriever import Retriever
            retriever = Retriever(config.knowledge_path)
        except Exception:
            retriever = None

    from .server.analyzer import SelectionAnalyzer

    analyzer = SelectionAnalyzer(
        knowledge_dir=config.knowledge_path,
        retriever=retriever,
        api_key=config.deepseek_api_key,
    )
    result = analyzer.analyze(
        text=args.text,
        url=args.url,
        page_title=args.page_title,
        question_title=args.question_title,
        author=args.author,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print("🔎 分析结果\n")
    if result["matched_tree_nodes"]:
        print("🌳 知识树匹配:")
        for node in result["matched_tree_nodes"]:
            print(f"  - {' / '.join(node['path'])}  score={node['score']}")
            print(f"    {node['reason']}")
    else:
        print("🌳 未匹配到知识树节点")

    if result["similar_sources"]:
        print("\n📚 相似素材:")
        for src in result["similar_sources"]:
            print(f"  - [{src.get('platform', '')}] {src.get('title', '')} ({src.get('author', '')}) score={src.get('score')}")
            if src.get("quote"):
                print(f"    {src['quote'][:120]}")

    if result["writing_suggestions"]:
        print("\n✍️ 写作建议:")
        for item in result["writing_suggestions"]:
            print(f"  - {item}")

    if result["risks"]:
        print("\n⚠ 相似风险:")
        for risk in result["risks"]:
            print(f"  - [{risk['level']}] {risk['message']}")


def _handle_serve(config: Config, args) -> None:
    """启动本地 API 服务."""
    try:
        import uvicorn
    except ImportError:
        print("❌ 需要安装 uvicorn: pip install uvicorn fastapi")
        return

    from .server.app import create_app

    app = create_app(config)
    print(f"🚀 本地 API: http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)


def _handle_monthly(config: Config, args) -> None:
    """月度全平台同步 + 知识库构建 + 卡片抽取."""
    import subprocess
    import sys

    account = getattr(args, 'account', 'default')
    acc_args = ["--account", account] if account != "default" else []

    base = [sys.executable, "-m", "zhihu2obsidian"]
    cmds: list[list[str]] = [
        [*base, "sync", *acc_args],
        [*base, "bilibili", "sync", *acc_args],
        [*base, "knowledge", "build"],
    ]
    if config.deepseek_api_key:
        cmds.append([*base, "knowledge", "cards", "build"])
    cmds.append([*base, "export", "--no-cards", *acc_args])

    print("🌙 月度全平台同步\n")
    for cmd in cmds:
        print(f"▶ {' '.join(cmd[3:])}")
        result = subprocess.run(cmd, capture_output=False)
        if result.returncode != 0:
            print(f"   ⚠ 命令退出码: {result.returncode}")

    print("\n✅ 月度同步完成")


# ── AI 友好导出 ────────────────────────────────────
def _handle_export(config: Config, args) -> None:
    """导出资料为 AI 友好格式 (JSONL + 分块 + 素材卡 + 分层语料库)."""
    out_dir = Path(args.output) if args.output else config.output_path / "export"
    from .export import run_export
    api_key = config.deepseek_api_key or ""
    if getattr(args, 'no_cards', False):
        api_key = ""
    account = getattr(args, 'account', 'default')
    run_export(
        vault_dir=config.output_path,
        out_dir=out_dir,
        api_key=api_key,
        model=getattr(args, 'model', "deepseek-v4-flash"),
        max_cards=getattr(args, 'max_cards', 0) or 0,
        account=account if account != "default" else None,
    )


# ── CLI 入口 ──────────────────────────────────────
if __name__ == "__main__":
    main()
