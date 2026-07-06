#!/usr/bin/env python3
"""SSP JSON 瀏覽器工具（GUI 版）。

功能：
    - 讀取 parse_ssp_xml_gui.py 輸出的 JSON 檔案（使用者選擇）
    - 上方下拉選單以「ParentName - Name_CN」格式列出所有 ProjectList 項目
    - 選擇後畫面分三個區塊：
            ① 頂部：8 個欄位的專案資訊
            ② 左下：依 FactFileName 顯示對應的 Document SVG 線路圖
            ③ 右下：includeObjectName 清單，並依對應的 PictureList_site / PictureList_pin 顯示按鈕
    - 點擊 Site / Pin 按鈕開啟獨立圖片查看視窗（支援縮放、捲動）

套件需求（可選）：
    - Pillow  → Site / Pin 圖片查看功能  （pip install Pillow）
    - tkinterweb → 左側 SVG 內嵌渲染（pip install tkinterweb）
    兩者皆未安裝時仍可執行，但左側 SVG 會退回顯示提示訊息。
"""

import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

# 中文註解：嘗試載入可選套件
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import fitz
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    import tkinterweb
    HAS_TKINTERWEB = True
except ImportError:
    HAS_TKINTERWEB = False


# ══════════════════════════════════════════════════════════════
#  Document XML → HTML / Text 轉換工具
# ══════════════════════════════════════════════════════════════

_HTML_CSS = """
body {
  font-family: 'Microsoft JhengHei', 'Microsoft YaHei', Arial, sans-serif;
  font-size: 13px;
  color: #1a4070;
  background: #fff;
  margin: 10px 14px;
  line-height: 1.7;
}
h1 { color: #1558a0; font-size: 16px; border-bottom: 2px solid #1558a0;
     padding-bottom: 4px; margin-top: 14px; }
h2 { color: #1e6dc0; font-size: 14px; border-bottom: 1px solid #cce; margin-top: 10px; }
h3 { color: #2a7ad5; font-size: 13px; margin-top: 8px; }
p  { margin: 3px 0 8px 0; }
ul { margin: 4px 0; padding-left: 22px; }
li { margin: 2px 0; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 12px; }
th, td { border: 1px solid #aabbcc; padding: 4px 8px;
         text-align: left; vertical-align: top; }
th { background: #dde7f5; font-weight: bold; }
img { max-width: 100%; height: auto; margin: 6px 0; border: 1px solid #ddd; }
.file-missing { color: #c00; font-style: italic; }
mark { background: #ffe680; color: #000; }
"""


def _elem_text(elem):
    """取得元素的直接文字（去除空白）。"""
    return (elem.text or "").strip()


def _convert_elem(elem, base_dir):
    """遞迴將 DIAGNOSISDOCUMENT 元素轉換為 HTML 字串。"""
    tag = elem.tag
    children = list(elem)

    # ── 容器 ────────────────────────────────────────────────────
    if tag == "DIAGNOSISDOCUMENT":
        return "".join(_convert_elem(c, base_dir) for c in children)

    if tag == "FUNCTIONALDESCRIPTION":
        parts = []
        h = elem.find("HEADING")
        if h is not None and _elem_text(h):
            parts.append(f"<h1>{_elem_text(h)}</h1>")
        d = elem.find("DOCUMENTTITLE")
        if d is not None and _elem_text(d):
            parts.append(f'<h2 style="color:#444">{_elem_text(d)}</h2>')
        for c in children:
            if c.tag not in ("HEADING", "DOCUMENTTITLE"):
                parts.append(_convert_elem(c, base_dir))
        return "".join(parts)

    if tag == "CHAPTER":
        h = elem.find("HEADING")
        parts = []
        if h is not None and _elem_text(h):
            parts.append(f"<h1>{_elem_text(h)}</h1>")
        for c in children:
            if c.tag != "HEADING":
                parts.append(_convert_elem(c, base_dir))
        return "".join(parts)

    if tag in ("SUBSECTION2", "SUBSECTION"):
        h = elem.find("HEADING")
        parts = []
        if h is not None and _elem_text(h):
            parts.append(f"<h2>{_elem_text(h)}</h2>")
        for c in children:
            if c.tag != "HEADING":
                parts.append(_convert_elem(c, base_dir))
        return "".join(parts)

    if tag == "FUNCDESCINTRODUCTORY":
        return "".join(_convert_elem(c, base_dir) for c in children)

    # ── 忽略已在父層處理的標籤 ───────────────────────────────────
    if tag in ("HEADING", "DOCUMENTTITLE"):
        return ""

    # ── 段落 ────────────────────────────────────────────────────
    if tag == "PARAGRAPH":
        content = _elem_text(elem)
        for c in children:
            content += _convert_elem(c, base_dir)
            if c.tail:
                content += c.tail.strip()
        return f"<p>{content}</p>" if content.strip() else "<p>&nbsp;</p>"

    if tag == "EMPHASIZE":
        return f"<strong>{_elem_text(elem)}</strong>"

    # ── 清單 ────────────────────────────────────────────────────
    if tag in ("GENERALLIST", "LIST"):
        items = "".join(_convert_elem(c, base_dir) for c in children)
        return f"<ul>{items}</ul>"

    if tag in ("LISTELEMENT", "LISTENTRY"):
        content = ""
        for c in children:
            if c.tag == "PARAGRAPH":
                ct = _elem_text(c)
                for cc in c:
                    ct += _convert_elem(cc, base_dir)
                content += ct
            elif c.tag != "LABEL":
                content += _convert_elem(c, base_dir)
        return f"<li>{content}</li>"

    # ── 表格 ────────────────────────────────────────────────────
    if tag == "TABLE":
        return _convert_table(elem)

    # ── 圖片 ────────────────────────────────────────────────────
    if tag == "GRAPHIC":
        src = elem.get("SRC", "")
        linkid = elem.get("LINKID", "")
        img_path = os.path.join(base_dir, "Picture", src)
        if os.path.exists(img_path):
            uri = "file:///" + img_path.replace("\\", "/")
            return f'<img src="{uri}" alt="{linkid}" />'
        return f'<p class="file-missing">[圖片未找到: {src}]</p>'

    # ── 其他：遞迴子元素 ─────────────────────────────────────────
    return "".join(_convert_elem(c, base_dir) for c in children)


def _convert_table(table_elem):
    """將 TABLE 元素轉為 HTML 表格。"""
    out = ["<table>"]
    tgroup = table_elem.find("TGROUP")
    if tgroup is None:
        out.append("</table>")
        return "".join(out)

    for section_tag, row_tag in (("THEAD", "th"), ("TBODY", "td")):
        section = tgroup.find(section_tag)
        if section is None:
            continue
        out.append(f"<{'thead' if row_tag == 'th' else 'tbody'}>")
        for row in section.findall("ROW"):
            out.append("<tr>")
            for entry in row.findall("ENTRY"):
                cell = " ".join(
                    (_elem_text(p) + " ".join(
                        (_elem_text(cc) for cc in p)
                    )).strip()
                    for p in entry.findall("PARAGRAPH")
                ).strip()
                out.append(f"<{row_tag}>{cell}</{row_tag}>")
            out.append("</tr>")
        out.append(f"</{'thead' if row_tag == 'th' else 'tbody'}>")

    out.append("</table>")
    return "".join(out)


def document_xml_to_html(xml_path, base_dir):
    """將 Document XML 檔案轉換為完整 HTML 字串。"""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception as exc:
        return f"<html><body><p style='color:red'>無法解析 XML：{exc}</p></body></html>"

    body = _convert_elem(root, base_dir)
    return (
        f"<html><head><meta charset='UTF-8'>"
        f"<style>{_HTML_CSS}</style></head>"
        f"<body>{body}</body></html>"
    )


def document_xml_to_segments(xml_path):
    """將 Document XML 轉為 (tag, text) 片段列表供 ScrolledText 使用。"""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception as exc:
        return [("error", f"無法解析 XML：{exc}\n")]

    segments = []

    def process(elem, depth=0):
        tag = elem.tag
        children = list(elem)

        if tag in ("HEADING",):
            txt = _elem_text(elem)
            if txt:
                level = "h1" if depth <= 2 else "h2" if depth <= 3 else "h3"
                segments.append((level, txt + "\n"))
            return

        if tag == "DOCUMENTTITLE":
            txt = _elem_text(elem)
            if txt:
                segments.append(("title", txt + "\n"))
            return

        if tag == "PARAGRAPH":
            content = _elem_text(elem)
            for c in children:
                content += _elem_text(c)
                if c.tail:
                    content += c.tail.strip()
            if content.strip():
                segments.append(("normal", content + "\n"))
            return

        if tag == "GRAPHIC":
            src = elem.get("SRC", "")
            if src:
                segments.append(("italic", f"[圖片: {src}]\n"))
            return

        if tag in ("LISTELEMENT", "LISTENTRY"):
            content = ""
            for c in children:
                if c.tag == "PARAGRAPH":
                    ct = _elem_text(c)
                    for cc in c:
                        ct += _elem_text(cc)
                    content += ct
            if content.strip():
                segments.append(("bullet", "  • " + content + "\n"))
            return

        if tag == "TABLE":
            segments.append(("table_sep", "─" * 60 + "\n"))
            tgroup = elem.find("TGROUP")
            if tgroup:
                for section in (tgroup.find("THEAD"), tgroup.find("TBODY")):
                    if section is None:
                        continue
                    for row in section.findall("ROW"):
                        cells = []
                        for entry in row.findall("ENTRY"):
                            cells.append(" ".join(
                                _elem_text(p) for p in entry.findall("PARAGRAPH")
                            ))
                        segments.append(("table_row", " │ ".join(cells) + "\n"))
            segments.append(("table_sep", "─" * 60 + "\n"))
            return

        for c in children:
            process(c, depth + 1)

    process(root)
    return segments


# ══════════════════════════════════════════════════════════════
#  圖片查看視窗
# ══════════════════════════════════════════════════════════════

class ImageViewerWindow:
    """獨立的縮放圖片查看視窗。"""

    def __init__(self, parent, image_path, title="圖片查看"):
        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.geometry("900x700")

        if not HAS_PIL:
            tk.Label(self.win,
                     text="需要 Pillow 套件才能顯示圖片\n"
                          "請執行：pip install Pillow",
                     font=("Microsoft JhengHei UI", 12), fg="red").pack(expand=True)
            return

        if not os.path.exists(image_path):
            tk.Label(self.win,
                     text=f"圖片檔案不存在：\n{image_path}",
                     font=("Microsoft JhengHei UI", 11), fg="red").pack(expand=True)
            return

        # ── 工具列 ──────────────────────────────────────────────
        bar = tk.Frame(self.win, bg="#f0f0f0", pady=5)
        bar.pack(fill=tk.X)

        tk.Label(bar, text=f"{os.path.basename(image_path)}",
                 bg="#f0f0f0",
                 font=("Consolas", 10), fg="#333").pack(side=tk.LEFT, padx=10)

        for text, delta in (("放大 +", 0.25), ("縮小 -", -0.25)):
            tk.Button(bar, text=text,
                      command=lambda d=delta: self._zoom(d),
                      padx=8).pack(side=tk.RIGHT, padx=3)
        tk.Button(bar, text="100%",
                  command=lambda: self._set_zoom(1.0),
                  padx=8).pack(side=tk.RIGHT, padx=3)
        tk.Button(bar, text="適合視窗",
                  command=self._fit_window,
                  padx=8).pack(side=tk.RIGHT, padx=3)

        self._zoom_label = tk.Label(bar, text="100%", bg="#f0f0f0",
                                     font=("Consolas", 10), width=6)
        self._zoom_label.pack(side=tk.RIGHT, padx=6)

        # ── Canvas + 捲軸 ────────────────────────────────────────
        hbar = tk.Scrollbar(self.win, orient=tk.HORIZONTAL)
        hbar.pack(side=tk.BOTTOM, fill=tk.X)
        vbar = tk.Scrollbar(self.win, orient=tk.VERTICAL)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._canvas = tk.Canvas(self.win, bg="#777",
                                  xscrollcommand=hbar.set,
                                  yscrollcommand=vbar.set,
                                  highlightthickness=0)
        self._canvas.pack(fill=tk.BOTH, expand=True)
        hbar.config(command=self._canvas.xview)
        vbar.config(command=self._canvas.yview)

        self._canvas.bind("<MouseWheel>",
                          lambda e: self._zoom(0.15 if e.delta > 0 else -0.15))

        self._orig = Image.open(image_path)
        self._zoom_level = 1.0
        self.win.update_idletasks()
        self._fit_window()

    def _fit_window(self):
        """縮放到適合視窗大小。"""
        cw = self._canvas.winfo_width() or 800
        ch = self._canvas.winfo_height() or 600
        ratio = min(cw / self._orig.width, ch / self._orig.height, 1.0)
        self._set_zoom(ratio)

    def _zoom(self, delta):
        """調整縮放比例。"""
        self._set_zoom(max(0.05, min(8.0, self._zoom_level + delta)))

    def _set_zoom(self, level):
        """設定縮放比例並重繪。"""
        self._zoom_level = level
        w = max(1, int(self._orig.width * level))
        h = max(1, int(self._orig.height * level))
        resized = self._orig.resize((w, h), Image.LANCZOS)
        self._tk_img = ImageTk.PhotoImage(resized)
        self._canvas.delete("all")
        self._canvas.create_image(0, 0, anchor="nw", image=self._tk_img)
        self._canvas.configure(scrollregion=(0, 0, w, h))
        self._zoom_label.config(text=f"{int(level * 100)}%")


# ══════════════════════════════════════════════════════════════
#  主應用程式
# ══════════════════════════════════════════════════════════════

class SspViewerApp:
    """SSP JSON 瀏覽器主類別。"""

    # ── 初始化 ────────────────────────────────────────────────
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("SSP JSON 瀏覽器")
        self.root.geometry("1440x920")
        self.root.minsize(900, 650)

        # 中文註解：資料狀態
        self._json_path = None
        self._base_dir = None
        self._project_list = []
        self._site_lookup: dict[str, list] = {}   # name → [{file_id, path, entry}]
        self._pin_lookup: dict[str, list] = {}
        self._selected_row_frame = None            # 目前選中的右側行 frame
        self._all_row_frames: list[tuple[tk.Frame, str]] = []  # (frame, name)
        self._current_project = None
        self._svg_orig_image = None
        self._svg_tk_image = None
        self._svg_zoom_level = 1.0

        self._build_ui()

    # ── UI 建構 ───────────────────────────────────────────────
    def _build_ui(self):
        """建構整體 UI 結構。"""

        # ── 頂端工具列 ─────────────────────────────────────────
        top_bar = tk.Frame(self.root, bg="#dde6f0", pady=5)
        top_bar.pack(fill=tk.X, side=tk.TOP)

        tk.Button(top_bar, text="📂 開啟 JSON",
                  command=self._open_json,
                  bg="#1e6dc0", fg="white",
                  font=("Microsoft JhengHei UI", 10, "bold"),
                  padx=12, pady=3, relief=tk.FLAT,
                  cursor="hand2").pack(side=tk.LEFT, padx=10)

        tk.Label(top_bar, text="線路圖：",
                 bg="#dde6f0",
                 font=("Microsoft JhengHei UI", 10)).pack(side=tk.LEFT, padx=(4, 2))

        self._project_var = tk.StringVar()
        self._combo = ttk.Combobox(top_bar,
                                    textvariable=self._project_var,
                                    state="readonly", width=58,
                                    font=("Microsoft JhengHei UI", 10))
        self._combo.pack(side=tk.LEFT, padx=4)
        self._combo.bind("<<ComboboxSelected>>", self._on_project_select)

        self._status_lbl = tk.Label(top_bar, text="請開啟 JSON 檔案",
                                     bg="#dde6f0", fg="#888",
                                     font=("Microsoft JhengHei UI", 9))
        self._status_lbl.pack(side=tk.RIGHT, padx=12)

        # ── 資訊面板 ─────────────────────────────────────────────
        info_outer = tk.Frame(self.root, bg="#f5f8ff",
                               relief=tk.GROOVE, bd=1)
        info_outer.pack(fill=tk.X, padx=6, pady=(4, 0))

        info_grid = tk.Frame(info_outer, bg="#f5f8ff", pady=5)
        info_grid.pack(fill=tk.X, padx=8)

        # 中文註解：8 個資訊欄位，排成 2 列 × 4 欄
        _fields = [
            ("SSPNb",         "SSP 編號"),
            ("FactCls",       "工廠分類"),
            ("Name_CN",       "中文名稱"),
            ("FactFileName",  "文件檔名"),
            ("ParentName",    "上層系統"),
            ("Specify_AutoInt","車型識別碼"),
            ("Specify_Nb",    "線路圖編號"),
            ("Specify_Tw",    "繁體名稱"),
        ]
        self._info_vars: dict[str, tk.StringVar] = {}
        for i, (key, label) in enumerate(_fields):
            col = (i % 4) * 3
            row = i // 4
            tk.Label(info_grid, text=f"{label}：",
                     bg="#f5f8ff",
                     font=("Microsoft JhengHei UI", 9, "bold"),
                     anchor="e", fg="#444").grid(
                row=row, column=col, sticky="e", padx=(10, 2), pady=2)
            var = tk.StringVar(value="—")
            self._info_vars[key] = var
            tk.Label(info_grid, textvariable=var,
                     bg="#f5f8ff",
                     font=("Microsoft JhengHei UI", 9), fg="#1a4070",
                     anchor="w", width=24).grid(
                row=row, column=col + 1, sticky="w", padx=(0, 14), pady=2)

        # ── 主體：左文件 ╋ 右清單（PanedWindow）──────────────────
        self._main_pane = tk.PanedWindow(self.root,
                                          orient=tk.HORIZONTAL,
                                          sashrelief=tk.RAISED, sashwidth=6,
                                          bg="#aabbcc")
        self._main_pane.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self._build_left_panel()
        self._build_right_panel()

    def _build_left_panel(self):
        """建構左側 Project SVG 預覽面板。"""
        left_frame = tk.LabelFrame(self._main_pane,
                                    text="Project SVG 線路圖",
                                    font=("Microsoft JhengHei UI", 9),
                                    bg="#ffffff", fg="#1558a0")
        self._main_pane.add(left_frame, minsize=380)

        toolbar = tk.Frame(left_frame, bg="#f1f5fa", pady=4)
        toolbar.pack(fill=tk.X)

        self._left_file_label = tk.Label(
            toolbar, text="請先開啟 JSON 檔案",
            bg="#f1f5fa", fg="#666666",
            font=("Microsoft JhengHei UI", 9), anchor="w")
        self._left_file_label.pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)

        if HAS_PIL and HAS_PYMUPDF:
            self._svg_hint_text = None
            self._svg_frame = None

            hbar = tk.Scrollbar(left_frame, orient=tk.HORIZONTAL)
            hbar.pack(side=tk.BOTTOM, fill=tk.X)
            vbar = tk.Scrollbar(left_frame, orient=tk.VERTICAL)
            vbar.pack(side=tk.RIGHT, fill=tk.Y)

            self._svg_canvas = tk.Canvas(
                left_frame,
                bg="#ffffff",
                xscrollcommand=hbar.set,
                yscrollcommand=vbar.set,
                highlightthickness=0)
            self._svg_canvas.pack(fill=tk.BOTH, expand=True)
            hbar.config(command=self._svg_canvas.xview)
            vbar.config(command=self._svg_canvas.yview)

            # 中文註解：視窗大小變更後可重新計算適合畫面的縮放
            self._svg_canvas.bind("<Configure>", self._on_svg_canvas_resize)
            self._svg_canvas.bind(
                "<MouseWheel>",
                lambda e: self._zoom_svg(0.15 if e.delta > 0 else -0.15))
        elif HAS_TKINTERWEB:
            self._svg_frame = tkinterweb.HtmlFrame(left_frame, messages_enabled=False)
            self._svg_frame.pack(fill=tk.BOTH, expand=True)
            self._svg_hint_text = None
            self._svg_canvas = None
        else:
            self._svg_hint_text = ScrolledText(
                left_frame,
                font=("Microsoft JhengHei UI", 10),
                wrap=tk.WORD,
                state=tk.DISABLED,
                bg="#fafcff")
            self._svg_hint_text.pack(fill=tk.BOTH, expand=True)
            self._svg_frame = None
            self._svg_canvas = None

    def _build_right_panel(self):
        """建構右側 includeObjectName 清單面板。"""
        right_frame = tk.LabelFrame(
            self._main_pane,
            text="包含零件清單（includeObjectName）",
            font=("Microsoft JhengHei UI", 9),
            bg="#fafcff", fg="#1558a0")
        self._main_pane.add(right_frame, minsize=280)

        # ── 篩選搜尋列 ──────────────────────────────────────────
        search_bar = tk.Frame(right_frame, bg="#fafcff", pady=4)
        search_bar.pack(fill=tk.X, padx=6)
        tk.Label(search_bar, text="篩選：",
                 bg="#fafcff",
                 font=("Microsoft JhengHei UI", 9)).pack(side=tk.LEFT)
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search_change)
        tk.Entry(search_bar, textvariable=self._search_var,
                 width=16, font=("Consolas", 10)).pack(side=tk.LEFT, padx=4)
        tk.Button(search_bar, text="×", command=lambda: self._search_var.set(""),
                  padx=3, font=("Arial", 9)).pack(side=tk.LEFT)

        self._count_label = tk.Label(search_bar, text="",
                                      bg="#fafcff",
                                      font=("Microsoft JhengHei UI", 9), fg="#666")
        self._count_label.pack(side=tk.RIGHT, padx=8)

        # ── 可捲動的清單容器（Canvas + inner Frame）───────────────
        container = tk.Frame(right_frame, bg="#fafcff")
        container.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self._list_canvas = tk.Canvas(container, bg="white",
                                       highlightthickness=0)
        vscroll = tk.Scrollbar(container, orient=tk.VERTICAL,
                                command=self._list_canvas.yview)
        self._list_canvas.configure(yscrollcommand=vscroll.set)
        vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._list_inner = tk.Frame(self._list_canvas, bg="white")
        self._canvas_win = self._list_canvas.create_window(
            (0, 0), window=self._list_inner, anchor="nw")

        # 中文註解：綁定尺寸事件確保捲動正確
        self._list_inner.bind("<Configure>",
                               lambda e: self._list_canvas.configure(
                                   scrollregion=self._list_canvas.bbox("all")))
        self._list_canvas.bind("<Configure>",
                                lambda e: self._list_canvas.itemconfig(
                                    self._canvas_win, width=e.width))

        # 中文註解：在 Canvas 上綁定滑鼠滾輪
        def _on_mousewheel(e):
            self._list_canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")

        self._list_canvas.bind("<MouseWheel>", _on_mousewheel)
        self._list_inner.bind("<MouseWheel>", _on_mousewheel)

        # 中文註解：儲存的滾輪綁定函式供子元件使用
        self._mw_func = _on_mousewheel

    # ── JSON 載入 ──────────────────────────────────────────────

    def _open_json(self):
        """彈出檔案對話框讓使用者選擇 JSON 檔案。"""
        path = filedialog.askopenfilename(
            title="選擇 JSON 檔案",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if path:
            self._load_json(path)

    def _load_json(self, path):
        """載入 JSON 並初始化所有查找表及下拉選單。"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            messagebox.showerror("讀取錯誤", f"無法讀取 JSON 檔案：\n{exc}")
            return

        self._json_path = path
        self._base_dir = os.path.dirname(os.path.abspath(path))
        self._project_list = data.get("ProjectList", [])

        # 中文註解：建立 Site 查找表（Name_CN → 對應記錄清單）
        self._site_lookup = {}
        for entry in data.get("PictureList_site", []):
            fid = entry.get("FileID", "")
            img = os.path.join(self._base_dir, "Picture", "Site", f"{fid}.png")
            for name in entry.get("Name_CN", []):
                if name:
                    self._site_lookup.setdefault(name, []).append(
                        {"file_id": fid, "path": img, "entry": entry}
                    )

        # 中文註解：建立 Pin 查找表
        self._pin_lookup = {}
        for entry in data.get("PictureList_pin", []):
            fid = entry.get("FileID", "")
            img = os.path.join(self._base_dir, "Picture", "Pin", f"{fid}.png")
            for name in entry.get("Name_CN", []):
                if name:
                    self._pin_lookup.setdefault(name, []).append(
                        {"file_id": fid, "path": img, "entry": entry}
                    )

        # 中文註解：更新下拉選單選項
        options = [
            f"{p.get('ParentName', '')} - {p.get('Name_CN', '')}"
            for p in self._project_list
        ]
        self._combo["values"] = options
        if options:
            self._combo.current(0)
            self._on_project_select()

        self._status_lbl.config(
            text=f"已載入 {len(self._project_list)} 筆｜{os.path.basename(path)}",
            fg="#2e7d32"
        )

    # ── 專案選擇 ──────────────────────────────────────────────

    def _on_project_select(self, event=None):
        """下拉選單切換後更新所有面板。"""
        idx = self._combo.current()
        if idx < 0 or idx >= len(self._project_list):
            return
        project = self._project_list[idx]
        self._current_project = project
        self._update_info_panel(project)
        self._load_project_svg(project)
        self._update_include_list(project.get("includeObjectName", []))

    def _update_info_panel(self, project):
        """更新頂部 8 個欄位的資訊。"""
        for key, var in self._info_vars.items():
            val = project.get(key, "—")
            var.set(str(val) if val else "—")

    # ── 左側 Project SVG 預覽 ─────────────────────────────────

    def _find_project_svg(self, fact_filename):
        """依 FactFileName 搜尋 Project 對應的 SVG 檔案。"""
        if not fact_filename or not self._base_dir:
            return None

        candidates = [
            os.path.join(self._base_dir, "Document", f"{fact_filename}.svg"),
            os.path.join(self._base_dir, "new-data", f"{fact_filename}.svg"),
            os.path.join(self._base_dir, f"{fact_filename}.svg"),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate
        return None

    def _load_project_svg(self, project):
        """載入並顯示目前 Project 對應的 SVG。"""
        fact_filename = project.get("FactFileName", "")
        svg_path = self._find_project_svg(fact_filename)

        if not svg_path:
            self._show_svg_hint(f"找不到對應的 SVG：Document/{fact_filename}.svg")
            return

        self._left_file_label.config(
            text=f"{os.path.basename(svg_path)}  ｜  {project.get('ParentName', '')} - {project.get('Name_CN', '')}",
            fg="#1558a0")

        if self._svg_canvas and HAS_PIL and HAS_PYMUPDF:
            try:
                # 中文註解：使用 PyMuPDF 直接開啟 SVG 並光柵化，避免 Cairo DLL 依賴問題
                svg_doc = fitz.open(svg_path)
                svg_page = svg_doc[0]
                svg_pixmap = svg_page.get_pixmap(dpi=144, alpha=True)
                self._svg_orig_image = Image.frombytes(
                    "RGBA",
                    (svg_pixmap.width, svg_pixmap.height),
                    svg_pixmap.samples)
                svg_doc.close()
                self._fit_svg_to_canvas()
            except Exception as exc:
                self._show_svg_hint(f"無法載入 SVG：\n{exc}")
        elif self._svg_frame:
            try:
                # 中文註解：Windows 本機路徑需先轉成標準 file URI，避免 tkinterweb 組出錯誤的 file://C:\... 格式
                svg_uri = Path(svg_path).resolve().as_uri()
                self._svg_frame.load_url(svg_uri)
            except Exception as exc:
                self._show_svg_hint(f"無法載入 SVG：\n{exc}")
        else:
            self._show_svg_hint(
                f"已找到 SVG：\n{svg_path}\n\n"
                "若要在左側直接顯示 SVG，請安裝：\n"
                "pip install pillow pymupdf\n"
                "或\n"
                "pip install tkinterweb"
            )

    def _on_svg_canvas_resize(self, event=None):
        """左側 Canvas 尺寸改變時，重新套用適合視窗的 SVG 縮放。"""
        if self._svg_orig_image:
            self._fit_svg_to_canvas()

    def _fit_svg_to_canvas(self):
        """依左側 Canvas 尺寸自動縮放 SVG 圖片。"""
        if not self._svg_orig_image or not self._svg_canvas:
            return

        canvas_width = self._svg_canvas.winfo_width() or 800
        canvas_height = self._svg_canvas.winfo_height() or 600
        ratio = min(
            canvas_width / self._svg_orig_image.width,
            canvas_height / self._svg_orig_image.height,
            1.0)
        self._set_svg_zoom(max(ratio, 0.05))

    def _zoom_svg(self, delta):
        """調整左側 SVG 預覽縮放比例。"""
        if not self._svg_orig_image:
            return
        self._set_svg_zoom(max(0.05, min(8.0, self._svg_zoom_level + delta)))

    def _set_svg_zoom(self, zoom_level):
        """設定左側 SVG 預覽的縮放並重繪。"""
        if not self._svg_orig_image or not self._svg_canvas:
            return

        self._svg_zoom_level = zoom_level
        width = max(1, int(self._svg_orig_image.width * zoom_level))
        height = max(1, int(self._svg_orig_image.height * zoom_level))
        resized = self._svg_orig_image.resize((width, height), Image.LANCZOS)
        self._svg_tk_image = ImageTk.PhotoImage(resized)

        self._svg_canvas.delete("all")
        self._svg_canvas.create_image(0, 0, anchor="nw", image=self._svg_tk_image)
        self._svg_canvas.configure(scrollregion=(0, 0, width, height))

    def _show_svg_hint(self, message):
        """在左側顯示 SVG 提示訊息。"""
        self._left_file_label.config(text="Project SVG 線路圖", fg="#666666")
        if self._svg_canvas:
            self._svg_canvas.delete("all")
            self._svg_orig_image = None
            self._svg_tk_image = None
            self._svg_canvas.create_text(
                24, 24,
                anchor="nw",
                text=message,
                fill="#666666",
                font=("Microsoft JhengHei UI", 10),
                width=max((self._svg_canvas.winfo_width() or 500) - 48, 300))
            self._svg_canvas.configure(scrollregion=self._svg_canvas.bbox("all"))
        elif self._svg_frame:
            html = (
                "<html><body style='font-family:Microsoft JhengHei UI,sans-serif;"
                "padding:24px;color:#666;background:#f8fbff;white-space:pre-wrap'>"
                f"{message}</body></html>"
            )
            self._svg_frame.load_html(html)
        elif self._svg_hint_text:
            self._svg_hint_text.configure(state=tk.NORMAL)
            self._svg_hint_text.delete("1.0", tk.END)
            self._svg_hint_text.insert(tk.END, message)
            self._svg_hint_text.configure(state=tk.DISABLED)

    # ── includeObjectName 清單 ────────────────────────────────

    def _update_include_list(self, items):
        """重建右側零件清單。"""
        # 中文註解：清除所有舊行
        for widget in self._list_inner.winfo_children():
            widget.destroy()
        self._all_row_frames.clear()
        self._selected_row_frame = None
        self._search_var.set("")

        for idx, name in enumerate(items):
            self._add_list_row(idx, name)

        self._update_count_label(len(items))
        self._list_canvas.update_idletasks()
        self._list_canvas.configure(scrollregion=self._list_canvas.bbox("all"))

    def _add_list_row(self, idx, name):
        """建立清單中的一行（包含名稱標籤與 Site/Pin 按鈕）。"""
        bg = "#ffffff" if idx % 2 == 0 else "#f4f8ff"

        row_frame = tk.Frame(self._list_inner, bg=bg, pady=3)
        row_frame.pack(fill=tk.X, padx=2, pady=0)
        row_frame._default_bg = bg  # 記錄原始背景色

        # 中文註解：點擊後只標示此行為選中；左側維持顯示目前 project 的 SVG
        def on_click(f=row_frame):
            self._select_row(f)

        # 序號
        tk.Label(row_frame, text=f"{idx + 1:3d}.",
                 bg=bg, fg="#999",
                 font=("Consolas", 9), width=4).pack(side=tk.LEFT, padx=(4, 0))

        # 零件名稱
        name_lbl = tk.Label(row_frame, text=name, bg=bg,
                              font=("Consolas", 10), fg="#1a4070",
                              anchor="w", cursor="hand2")
        name_lbl.pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)
        name_lbl.bind("<Button-1>", lambda e, f=row_frame: on_click(f))
        row_frame.bind("<Button-1>", lambda e, f=row_frame: on_click(f))

        # 中文註解：Site 按鈕（若有對應）
        if name in self._site_lookup:
            entries = self._site_lookup[name]
            btn = tk.Button(row_frame, text="Site",
                             bg="#2e7d32", fg="white",
                             font=("Microsoft JhengHei UI", 8, "bold"),
                             padx=5, pady=0, relief=tk.FLAT, cursor="hand2",
                             command=lambda e=entries, n=name:
                                 self._open_image_picker(n, e, "Site"))
            btn.pack(side=tk.LEFT, padx=2)
            btn.bind("<MouseWheel>", self._mw_func)

        # 中文註解：Pin 按鈕（若有對應）
        if name in self._pin_lookup:
            entries = self._pin_lookup[name]
            btn = tk.Button(row_frame, text="Pin",
                             bg="#1565c0", fg="white",
                             font=("Microsoft JhengHei UI", 8, "bold"),
                             padx=5, pady=0, relief=tk.FLAT, cursor="hand2",
                             command=lambda e=entries, n=name:
                                 self._open_image_picker(n, e, "Pin"))
            btn.pack(side=tk.LEFT, padx=(0, 4))
            btn.bind("<MouseWheel>", self._mw_func)

        # 中文註解：讓子元件的滾輪也能捲動清單
        for child in row_frame.winfo_children():
            child.bind("<MouseWheel>", self._mw_func)

        self._all_row_frames.append((row_frame, name))

    def _select_row(self, frame):
        """高亮選中行，取消前一行高亮。"""
        if self._selected_row_frame and self._selected_row_frame.winfo_exists():
            prev_bg = self._selected_row_frame._default_bg
            self._selected_row_frame.configure(bg=prev_bg)
            for child in self._selected_row_frame.winfo_children():
                try:
                    if child.cget("bg") != "#2e7d32" and child.cget("bg") != "#1565c0":
                        child.configure(bg=prev_bg)
                except tk.TclError:
                    pass
        self._selected_row_frame = frame
        frame.configure(bg="#c8e0ff")
        for child in frame.winfo_children():
            try:
                if child.cget("bg") not in ("#2e7d32", "#1565c0"):
                    child.configure(bg="#c8e0ff")
            except tk.TclError:
                pass

    def _on_search_change(self, *_):
        """根據搜尋文字篩選清單行的顯示。"""
        kw = self._search_var.get().strip().lower()
        visible = 0
        for frame, name in self._all_row_frames:
            if kw and kw not in name.lower():
                frame.pack_forget()
            else:
                frame.pack(fill=tk.X, padx=2, pady=0)
                visible += 1
        self._update_count_label(visible)
        self._list_canvas.configure(scrollregion=self._list_canvas.bbox("all"))

    def _update_count_label(self, count):
        """更新右側計數標籤。"""
        total = len(self._all_row_frames)
        if count == total:
            self._count_label.config(text=f"共 {total} 筆")
        else:
            self._count_label.config(text=f"{count}/{total} 筆")

    # ── 圖片查看 ──────────────────────────────────────────────

    def _open_image_picker(self, name, entries, location):
        """若有多筆對應先讓使用者選擇，再開啟圖片。"""
        if len(entries) == 1:
            e = entries[0]
            self._open_image_viewer(e["path"],
                                    f"{location} ─ {name}（{e['file_id']}）")
            return

        # 中文註解：多筆對應 → 選擇對話框
        picker = tk.Toplevel(self.root)
        picker.title(f"選擇 {location} 圖片 — {name}")
        picker.geometry("500x300")
        picker.grab_set()

        tk.Label(picker,
                 text=f"「{name}」在 {location} 中找到 {len(entries)} 筆對應，請選擇：",
                 font=("Microsoft JhengHei UI", 10),
                 wraplength=460).pack(pady=10, padx=10)

        lb_frame = tk.Frame(picker)
        lb_frame.pack(fill=tk.BOTH, expand=True, padx=10)
        lb = tk.Listbox(lb_frame, font=("Consolas", 10),
                         selectmode=tk.SINGLE, activestyle="dotbox")
        lb_scroll = tk.Scrollbar(lb_frame, command=lb.yview)
        lb.configure(yscrollcommand=lb_scroll.set)
        lb_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        lb.pack(fill=tk.BOTH, expand=True)

        for entry in entries:
            parent = entry["entry"].get("ParentName", "")
            lb.insert(tk.END,
                       f"FileID: {entry['file_id']}  |  {parent}")
        lb.selection_set(0)

        def open_sel():
            sel = lb.curselection()
            if not sel:
                return
            e = entries[sel[0]]
            picker.destroy()
            self._open_image_viewer(e["path"],
                                    f"{location} ─ {name}（{e['file_id']}）")

        tk.Button(picker, text="開啟圖片",
                   command=open_sel,
                   bg="#1e6dc0", fg="white",
                   font=("Microsoft JhengHei UI", 10, "bold"),
                   padx=14).pack(pady=8)

        lb.bind("<Double-Button-1>", lambda e: open_sel())

    def _open_image_viewer(self, path, title):
        """開啟獨立圖片查看視窗。"""
        ImageViewerWindow(self.root, path, title)


# ══════════════════════════════════════════════════════════════
#  程式入口
# ══════════════════════════════════════════════════════════════

def main():
    """啟動 SSP JSON 瀏覽器。"""
    if not HAS_PIL:
        print("[提示] 未安裝 Pillow，圖片查看功能將無法使用。")
        print("       請執行：pip install Pillow")
    if not HAS_TKINTERWEB:
        print("[提示] 未安裝 tkinterweb，文件將以純文字模式顯示。")
        print("       如需 HTML 渲染品質：pip install tkinterweb")

    root = tk.Tk()
    SspViewerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
