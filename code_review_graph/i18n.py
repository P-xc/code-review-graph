"""UI language for generated artifacts.

Only the human-facing output is translated — currently the visualization
HTML. Machine-facing surfaces are deliberately NOT translated:

  * JSON returned by the MCP tools and the CLI's JSON mode is consumed by
    AI agents, which match on those strings. Translating `status`,
    `summary`, `description` or `hint` would break every agent that reads
    them and would fragment the MCP tool contract across locales.
  * Node names, signatures and file paths come from the source under
    analysis. They are that project's identifiers, not our UI, and must
    never be rewritten.

Resolution order, first match wins:
  1. ``--lang`` / an explicit ``lang`` argument
  2. the ``CRG_LANG`` environment variable
  3. the process locale (``LC_ALL`` / ``LC_MESSAGES`` / ``LANG``)
  4. the OS user-interface language (Windows: GetUserDefaultUILanguage)
  5. English

Anything that does not resolve to a known locale falls back to English, so
this can never make output unreadable.
"""

from __future__ import annotations

import ctypes
import locale
import os
from typing import Mapping

EN = "en"
ZH = "zh"

# Locale prefixes we ship, longest first so zh-Hans wins over zh.
_SUPPORTED: tuple[tuple[str, str], ...] = (
    ("zh", ZH),
    ("en", EN),
)

DEFAULT_LANGUAGE = EN

# The user-facing strings of the generated HTML page. Keys are stable; the
# English value lives here so a missing translation still renders English
# rather than a bare key.
_MESSAGES: Mapping[str, Mapping[str, str]] = {
    EN: {
        "page.title": "Code Review Graph",
        "skip.to_graph": "Skip to graph",
        "stats.heading": "Graph statistics",
        "stats.nodes": "Nodes",
        "stats.edges": "Edges",
        "legend.heading": "Graph legend",
        "legend.community": "Community legend",
        "filter.heading": "Filter by Kind",
        "filter.flows": "Flows",
        "filter.select_flow": "Select execution flow to highlight",
        "view.heading": "View Mode",
        "view.communities": "Communities",
        "view.toggle_community": "Toggle community coloring",
        "view.labels": "Labels",
        "view.toggle_labels": "Toggle labels",
        "view.toggle_node_labels": "Toggle node labels",
        "search.placeholder": "Search graph nodes by name",
        "search.results": "Search results",
        "detail.heading": "Node detail",
        "detail.close": "Close detail panel",
        "detail.lines": "Lines: ",
        "detail.params": "Params: ",
        "detail.returns": "Returns: ",
        "detail.community": "Community: ",
        "neighbourhood.heading": "Neighbourhood view",
        "neighbourhood.back": "Back to overview",
        "neighbourhood.all_seeds": "All neighbourhood seeds",
        "neighbourhood.hop": "hop ",
        "neighbourhood.path": "path: ",
        "neighbourhood.trimmed": "trimmed to ",
        "help.heading": "Graph Interactions",
        "help.interactions": "Graph Interactions",
        "help.click_file": "Click a file",
        "help.click_file_desc": "Expand/collapse contained symbols",
        "help.click_symbol": "Click symbol",
        "help.click_symbol_desc": "Show detail panel with callers/callees",
        "help.hover": "Hover",
        "help.hover_desc": "Highlight connected nodes and edges",
        "help.drag": "Drag",
        "help.drag_desc": "Pin a node in place",
        "help.scroll": "Scroll",
        "help.scroll_desc": "Zoom in/out",
        "help.click_drag_bg": "Click+drag background",
        "help.pan_desc": "Pan the view",
        "help.search": "Search",
        "help.search_desc": "Type to filter \u2014 matching nodes stay bright",
        "help.legend_edges": "Legend edges",
        "help.legend_edges_desc": "Click edge types in the legend to toggle visibility",
        "help.frontier": "Click frontier node",
        "help.frontier_desc": "Neighbourhood view: reveal that node\u2019s neighbours",
        "keys.heading": "Keyboard Shortcuts",
        "keys.focus_search": "Focus search",
        "keys.toggle_help": "Toggle this help",
        "keys.activate": "Activate focused node",
        "keys.navigate": "Navigate between nodes",
        "help.dismiss": "Click anywhere outside to dismiss",
        "help.overlay": "Help overlay",
        "help.close": "Close help",
        "help.show": "Show keyboard shortcuts",
        "help.shortcuts": "Keyboard shortcuts",
        "empty.title": "No nodes to display",
        "reset": "Reset",
        "fit": "Fit to screen",
        "fit_graph": "Fit graph to screen",
        "svg.desc": "Interactive code knowledge graph visualization. Use search to find nodes, click files to expand.",
        "svg.desc.aggregated": "Interactive code knowledge graph visualization (aggregated view).",
    },
    ZH: {
        "page.title": "代码审查图谱",
        "skip.to_graph": "跳到图谱",
        "stats.heading": "图谱统计",
        "stats.nodes": "节点",
        "stats.edges": "关系",
        "legend.heading": "图例",
        "legend.community": "社区图例",
        "filter.heading": "按类型筛选",
        "filter.flows": "执行流",
        "filter.select_flow": "选择要高亮的执行流",
        "view.heading": "视图模式",
        "view.communities": "社区",
        "view.toggle_community": "切换社区着色",
        "view.labels": "标签",
        "view.toggle_labels": "切换标签显示",
        "view.toggle_node_labels": "切换节点标签显示",
        "search.placeholder": "按名称搜索节点",
        "search.results": "搜索结果",
        "detail.heading": "节点详情",
        "detail.close": "关闭详情面板",
        "detail.lines": "行号：",
        "detail.params": "参数：",
        "detail.returns": "返回：",
        "detail.community": "社区：",
        "neighbourhood.heading": "邻域视图",
        "neighbourhood.back": "返回总览",
        "neighbourhood.all_seeds": "全部邻域起点",
        "neighbourhood.hop": "跳 ",
        "neighbourhood.path": "路径：",
        "neighbourhood.trimmed": "已截断至 ",
        "help.heading": "图谱交互",
        "help.interactions": "图谱交互",
        "help.click_file": "点击文件",
        "help.click_file_desc": "展开/折叠包含的代码符号",
        "help.click_symbol": "点击符号",
        "help.click_symbol_desc": "显示详情面板，含调用者/被调用者",
        "help.hover": "悬停",
        "help.hover_desc": "高亮相连的节点与关系",
        "help.drag": "拖拽",
        "help.drag_desc": "将节点固定在当前位置",
        "help.scroll": "滚轮",
        "help.scroll_desc": "缩放视图",
        "help.click_drag_bg": "点击并拖拽空白处",
        "help.pan_desc": "平移视图",
        "help.search": "搜索",
        "help.search_desc": "输入以筛选 —— 匹配的节点保持高亮",
        "help.legend_edges": "图例中的关系",
        "help.legend_edges_desc": "点击图例中的关系类型可切换显示",
        "help.frontier": "点击前沿节点",
        "help.frontier_desc": "邻域视图：显示该节点的邻居",
        "keys.heading": "键盘快捷键",
        "keys.focus_search": "聚焦搜索框",
        "keys.toggle_help": "显示/隐藏本帮助",
        "keys.activate": "激活当前聚焦节点",
        "keys.navigate": "在节点间移动",
        "help.dismiss": "点击外部任意处关闭",
        "help.overlay": "帮助浮层",
        "help.close": "关闭帮助",
        "help.show": "显示键盘快捷键",
        "help.shortcuts": "键盘快捷键",
        "empty.title": "没有可显示的节点",
        "reset": "重置",
        "fit": "适应屏幕",
        "fit_graph": "图谱适应屏幕",
        "svg.desc": "交互式代码知识图谱可视化。使用搜索查找节点，点击文件可展开。",
        "svg.desc.aggregated": "交互式代码知识图谱可视化（聚合视图）。",
    },
}


def normalize(raw: str | None) -> str:
    """Map a locale string to a supported language code, else English."""
    if not raw:
        return DEFAULT_LANGUAGE
    token = raw.strip().lower().replace("-", "_")
    if not token:
        return DEFAULT_LANGUAGE
    # "zh_CN.UTF-8" / "zh-Hans" / "zh" all mean Chinese.
    for prefix, lang in _SUPPORTED:
        if token == prefix or token.startswith(prefix + "_"):
            return lang
    return DEFAULT_LANGUAGE


def _windows_ui_language() -> str | None:
    """The Windows user-interface language as a locale string, or None."""
    if os.name != "nt":
        return None
    try:
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
    except (AttributeError, OSError):
        return None
    if not lang_id:
        return None
    # Low byte is the primary language id; 0x04 is Chinese.
    primary = lang_id & 0xFF
    sub = (lang_id >> 10) & 0x3F
    if primary == 0x04:
        # 0x01 zh-Hans, 0x02 zh-Hant; both map to zh for now.
        return "zh"
    if primary == 0x09:
        return "en"
    _ = sub
    return None


def detect_language(explicit: str | None = None) -> str:
    """Resolve the UI language. See the module docstring for the order."""
    # An explicit choice is authoritative even when it asks for the
    # default: on a zh locale box, `--lang en` must produce English.
    if explicit:
        return normalize(explicit)
    # CRG_LANG is a deliberate override: it must win even when it asks
    # for the default, or setting it to "en" on a zh box does nothing.
    crg_lang = os.environ.get("CRG_LANG")
    if crg_lang:
        return normalize(crg_lang)
    for candidate in (
        os.environ.get("LC_ALL"),
        os.environ.get("LC_MESSAGES"),
        os.environ.get("LANG"),
    ):
        lang = normalize(candidate)
        if lang != DEFAULT_LANGUAGE:
            return lang
    try:
        lang = normalize(locale.getlocale()[0])
    except (locale.Error, IndexError, TypeError):
        lang = DEFAULT_LANGUAGE
    if lang != DEFAULT_LANGUAGE:
        return lang
    win = _windows_ui_language()
    if win:
        lang = normalize(win)
        if lang != DEFAULT_LANGUAGE:
            return lang
    return DEFAULT_LANGUAGE


class Translator:
    """Looks UI strings up in the resolved language, falling back to English."""

    def __init__(self, language: str | None = None) -> None:
        self.language = normalize(language) if language else detect_language()
        self.table = _MESSAGES.get(self.language, _MESSAGES[EN])

    def __call__(self, key: str) -> str:
        """Translate one key. An unknown key renders as itself, never blank."""
        value = self.table.get(key)
        if value is not None:
            return value
        return _MESSAGES[EN].get(key, key)

    # Convenience for the call sites that read as attribute access.
    def t(self, key: str) -> str:
        return self(key)
