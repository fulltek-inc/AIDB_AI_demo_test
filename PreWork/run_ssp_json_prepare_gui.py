#!/usr/bin/env python3
"""ssp_json_tabs.html 前置 JSON 統一產生工具（GUI 版）。"""

import json
import os
import tkinter as tk
import xml.etree.ElementTree as ET
from tkinter import filedialog, messagebox, scrolledtext

from build_explorer_index_gui import build_explorer_index
from extract_compe_plugs_gui import group_same_component_sources, merge_component_maps, parse_document_xml
from parse_ssp_xml_gui import parse_ssp_xml
from parse_xml_document_use_gui import parse_xml_document_use


# 中文註解：依來源檔案與指定 suffix 組合輸出 JSON 路徑；輸入為來源路徑、輸出資料夾與檔名後綴，輸出為完整 JSON 路徑。
def build_output_json_path(source_path, output_folder_path, suffix):
    """使用來源檔名主體產生統一輸出路徑，避免各工具各自輸出到不同資料夾。"""
    source_name = os.path.splitext(os.path.basename(source_path))[0]
    return os.path.join(output_folder_path, f"{source_name}{suffix}.json")


# 中文註解：將資料以 UTF-8 JSON 寫入指定位置；輸入為輸出路徑與可序列化資料，無回傳值。
def write_json_file(output_json_path, output_data):
    """統一 JSON 寫檔格式，確保中文不被 ASCII escape 且方便人工檢視。"""
    output_dir = os.path.dirname(os.path.abspath(output_json_path))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_json_path, "w", encoding="utf-8") as output_file:
        json.dump(output_data, output_file, ensure_ascii=False, indent=2)


# 中文註解：從主 JSON 結構取出 Document XML 編號；輸入為 parse_ssp_xml 的輸出資料，輸出為去重後的 FactFileName 清單。
def collect_fact_file_names(ssp_json_data):
    """依 ProjectList 順序收集 FactFileName，供後續從 Document 資料夾解析元件插頭。"""
    fact_file_names = []
    seen_fact_file_names = set()

    for project_item in ssp_json_data.get("ProjectList", []):
        # 中文註解：FactFileName 是 Document 資料夾內 XML 的檔名主體，空值無法定位檔案所以略過。
        fact_file_name = (project_item.get("FactFileName") or "").strip()
        if not fact_file_name or fact_file_name in seen_fact_file_names:
            continue

        seen_fact_file_names.add(fact_file_name)
        fact_file_names.append(fact_file_name)

    return fact_file_names


# 中文註解：依主 XML 同層 Document 資料夾產生元件插頭資料；輸入為主 XML 路徑與主 JSON 資料，輸出為結果資料與統計。
def build_compe_plugs_from_ssp_data(xml_path, ssp_json_data):
    """不依賴輸出資料夾位置，固定從主 XML 同層 Document 資料夾解析 CompeData。"""
    base_dir = os.path.dirname(os.path.abspath(xml_path))
    document_dir = os.path.join(base_dir, "Document")

    if not os.path.isdir(document_dir):
        raise FileNotFoundError(f"找不到 Document 資料夾：{document_dir}")

    fact_file_names = collect_fact_file_names(ssp_json_data)
    result_map = {}
    missing_xml_files = []
    parse_error_files = []
    parsed_xml_count = 0

    for fact_file_name in fact_file_names:
        xml_file_name = fact_file_name if fact_file_name.lower().endswith(".xml") else f"{fact_file_name}.xml"
        document_xml_path = os.path.join(document_dir, xml_file_name)

        # 中文註解：單一 Document XML 缺漏時不中斷整批流程，保留清單讓使用者在日誌中確認。
        if not os.path.isfile(document_xml_path):
            missing_xml_files.append(document_xml_path)
            continue

        try:
            document_component_map = parse_document_xml(document_xml_path)
        except ET.ParseError as exc:
            # 中文註解：XML 格式錯誤只記錄該檔，避免一份壞檔阻擋其他文件完成輸出。
            parse_error_files.append({"path": document_xml_path, "error": str(exc)})
            continue

        source_file_name = os.path.splitext(os.path.basename(xml_file_name))[0]
        merge_component_maps(result_map, source_file_name, document_component_map)
        parsed_xml_count += 1

    grouped_result_map = group_same_component_sources(result_map)
    summary = {
        "factFileNameCount": len(fact_file_names),
        "parsedXmlCount": parsed_xml_count,
        "componentCount": len(result_map),
        "componentSourceCount": sum(len(source_map) for source_map in result_map.values()),
        "componentGroupCount": sum(len(group_items) for group_items in grouped_result_map.values()),
        "missingXmlFiles": missing_xml_files,
        "parseErrorFiles": parse_error_files,
    }

    return grouped_result_map, summary


# 中文註解：GUI 主程式，集中執行 ssp_json_tabs.html 需要的四份 JSON 前置資料。
class SspJsonPrepareApp:
    """前置 JSON 產生工具的 Tkinter 應用程式。"""

    # 中文註解：初始化視窗、路徑欄位與操作按鈕；輸入為 tkinter 根視窗，無回傳值。
    def __init__(self, root_window):
        self.root_window = root_window
        self.root_window.title("ssp_json_tabs.html 前置 JSON 產生工具")
        self.root_window.geometry("900x580")

        # 中文註解：保存使用者選擇的 SSP 主 XML 與統一輸出資料夾，其他 JSON 會由主 XML 自動產生。
        self.xml_path_var = tk.StringVar()
        self.output_folder_path_var = tk.StringVar()

        file_frame = tk.Frame(self.root_window, padx=10, pady=10)
        file_frame.pack(fill=tk.X)

        tk.Label(file_frame, text="SSP 主 XML：").grid(row=0, column=0, sticky="w")
        tk.Entry(file_frame, textvariable=self.xml_path_var, width=90).grid(row=0, column=1, sticky="ew", padx=(6, 6))
        tk.Button(file_frame, text="瀏覽...", command=self.select_xml_file).grid(row=0, column=2)

        tk.Label(file_frame, text="輸出資料夾：").grid(row=1, column=0, sticky="w", pady=(8, 0))
        tk.Entry(file_frame, textvariable=self.output_folder_path_var, width=90).grid(
            row=1,
            column=1,
            sticky="ew",
            padx=(6, 6),
            pady=(8, 0),
        )
        tk.Button(file_frame, text="瀏覽...", command=self.select_output_folder).grid(row=1, column=2, pady=(8, 0))

        file_frame.columnconfigure(1, weight=1)

        action_frame = tk.Frame(self.root_window, padx=10)
        action_frame.pack(fill=tk.X)

        run_button = tk.Button(
            action_frame,
            text="開始產生 JSON",
            command=self.run_prepare,
            bg="#2E7D32",
            fg="white",
            font=("Microsoft JhengHei UI", 11, "bold"),
            padx=14,
            pady=6,
        )
        run_button.pack(pady=(4, 8))

        log_frame = tk.Frame(self.root_window, padx=10, pady=6)
        log_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(log_frame, text="執行結果：", anchor="w").pack(fill=tk.X)
        self.log_text = scrolledtext.ScrolledText(log_frame, font=("Consolas", 10), height=23)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    # 中文註解：選擇 SSP 主 XML；輸入來自檔案對話框，並自動預設輸出資料夾為 XML 所在資料夾。
    def select_xml_file(self):
        """讓使用者選擇原始 SSP XML，供主 JSON 與其他三份輔助 JSON 流程共用。"""
        selected_path = filedialog.askopenfilename(
            title="選擇 SSP 主 XML",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
        )
        if selected_path:
            self.xml_path_var.set(selected_path)
            if not self.output_folder_path_var.get().strip():
                self.output_folder_path_var.set(os.path.dirname(selected_path))

    # 中文註解：選擇四份 JSON 的統一輸出資料夾；輸入為資料夾對話框結果，無回傳值。
    def select_output_folder(self):
        """讓使用者指定所有轉出 JSON 要集中放置的位置。"""
        selected_folder = filedialog.askdirectory(title="選擇輸出資料夾")
        if selected_folder:
            self.output_folder_path_var.set(selected_folder)

    # 中文註解：寫入 GUI 日誌並自動捲到最下方；輸入為要顯示的文字，無回傳值。
    def append_log(self, message):
        """集中處理執行狀態顯示，讓使用者能確認每一步輸出與統計。"""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root_window.update_idletasks()

    # 中文註解：檢查使用者輸入路徑是否完整可用；輸出清理後的兩個絕對路徑供主流程使用。
    def validate_paths(self):
        """驗證 SSP 主 XML、輸出資料夾與 Document 資料夾，避免執行到一半才失敗。"""
        xml_path = self.xml_path_var.get().strip()
        output_folder_path = self.output_folder_path_var.get().strip()

        if not xml_path:
            messagebox.showwarning("提示", "請先選擇 SSP 主 XML")
            return None, None

        if not os.path.isfile(xml_path):
            messagebox.showerror("錯誤", f"找不到 SSP 主 XML：\n{xml_path}")
            return None, None

        # 中文註解：元件插頭解析會從主 XML 同層尋找 Document 資料夾，因此在開始前先提示路徑問題。
        document_folder_path = os.path.join(os.path.dirname(os.path.abspath(xml_path)), "Document")
        if not os.path.isdir(document_folder_path):
            messagebox.showerror(
                "錯誤",
                "找不到 SSP 主 XML 同層的 Document 資料夾，無法產生 _compe_plugs.json：\n"
                f"{document_folder_path}",
            )
            return None, None

        if not output_folder_path:
            output_folder_path = os.path.dirname(os.path.abspath(xml_path))
            self.output_folder_path_var.set(output_folder_path)

        return os.path.abspath(xml_path), os.path.abspath(output_folder_path)

    # 中文註解：執行四段轉檔流程；輸入取自 GUI 欄位，輸出為四份集中放置的 JSON。
    def run_prepare(self):
        """依序產生主 JSON、XMLDocumentUse、explorer index、compe plugs；不執行文件 XML 搬移功能。"""
        self.log_text.delete("1.0", tk.END)
        xml_path, output_folder_path = self.validate_paths()

        if not xml_path or not output_folder_path:
            return

        os.makedirs(output_folder_path, exist_ok=True)

        self.append_log(f"SSP 主 XML：{xml_path}")
        self.append_log(f"輸出資料夾：{output_folder_path}")
        self.append_log("-" * 60)

        try:
            ssp_json_data = self.export_main_json(xml_path, output_folder_path)
            self.export_xml_document_use(xml_path, output_folder_path)
            self.export_document_index(xml_path, output_folder_path)
            self.export_compe_plugs(xml_path, ssp_json_data, output_folder_path)
        except ET.ParseError as exc:
            messagebox.showerror("XML 解析錯誤", str(exc))
            self.append_log(f"XML 解析錯誤：{exc}")
            return
        except Exception as exc:  # pylint: disable=broad-except
            messagebox.showerror("執行錯誤", str(exc))
            self.append_log(f"執行錯誤：{exc}")
            return

        self.append_log("-" * 60)
        self.append_log("全部完成")
        messagebox.showinfo("完成", "四份 JSON 已產生完成")

    # 中文註解：產生 ssp_json_tabs.html 主要載入的 JSON；輸入為 SSP XML 與輸出資料夾，輸出為主 JSON 資料。
    def export_main_json(self, xml_path, output_folder_path):
        """呼叫 parse_ssp_xml 核心函式，產出原本需要先手動執行的主 JSON。"""
        self.append_log("開始產生主 JSON...")
        ssp_json_data, missing_picture_count = parse_ssp_xml(xml_path)
        output_json_path = build_output_json_path(xml_path, output_folder_path, "_data")
        write_json_file(output_json_path, ssp_json_data)

        self.append_log(f"ProjectList 筆數：{len(ssp_json_data['ProjectList'])}")
        self.append_log(f"PictureList_site 筆數：{len(ssp_json_data['PictureList_site'])}")
        self.append_log(f"PictureList_pin 筆數：{len(ssp_json_data['PictureList_pin'])}")
        if missing_picture_count > 0:
            self.append_log(f"未找到對應圖片的筆數：{missing_picture_count}")
        self.append_log(f"輸出 JSON：{output_json_path}")
        self.append_log("-" * 60)

        return ssp_json_data

    # 中文註解：產生 XMLDocumentUse 對照 JSON；輸入為 SSP XML 與輸出資料夾，輸出檔名固定為來源 XML 加後綴。
    def export_xml_document_use(self, xml_path, output_folder_path):
        """呼叫 parse_xml_document_use 核心函式，輸出 ssp_json_tabs.html 可讀取的圖片對照表。"""
        self.append_log("開始產生 XMLDocumentUse JSON...")
        document_use_map, summary = parse_xml_document_use(xml_path)
        output_json_path = build_output_json_path(xml_path, output_folder_path, "_xml_document_use")
        write_json_file(output_json_path, document_use_map)

        self.append_log(f"XMLDocumentUse 符合筆數：{summary['matchedPictureCount']}")
        self.append_log(f"XMLDocumentUse 輸出筆數：{summary['outputCount']}")
        self.append_log(f"輸出 JSON：{output_json_path}")
        self.append_log("-" * 60)

    # 中文註解：產生 explorer.html 文件索引 JSON；此處只建立 JSON，不呼叫文件 XML 複製功能。
    def export_document_index(self, xml_path, output_folder_path):
        """呼叫 build_explorer_index 核心函式，刻意略過 copy_document_xml_files 搬移檔案流程。"""
        self.append_log("開始產生 Document Index JSON...")
        index_data, summary = build_explorer_index(xml_path)
        output_json_path = build_output_json_path(xml_path, output_folder_path, "_document_index")
        write_json_file(output_json_path, index_data)

        self.append_log(f"XmlDocumentData_CLS 總筆數：{summary['totalDocumentCount']}")
        self.append_log(f"Document Index 輸出筆數：{summary['outputDocumentCount']}")
        self.append_log(f"略過缺少分類 key 筆數：{summary['skippedMissingKeyCount']}")
        self.append_log(f"輸出 JSON：{output_json_path}")
        self.append_log("-" * 60)

    # 中文註解：產生元件插頭 JSON；輸入為主 XML、主 JSON 資料與輸出資料夾，會讀取主 XML 同層 Document XML。
    def export_compe_plugs(self, xml_path, ssp_json_data, output_folder_path):
        """從 parse_ssp_xml 結果取得 FactFileName，將元件插頭結果集中輸出到指定資料夾。"""
        self.append_log("開始產生 Compe Plugs JSON...")
        compe_plugs_data, summary = build_compe_plugs_from_ssp_data(xml_path, ssp_json_data)
        output_json_path = build_output_json_path(xml_path, output_folder_path, "_compe_plugs")
        write_json_file(output_json_path, compe_plugs_data)

        self.append_log(f"FactFileName 數：{summary['factFileNameCount']}")
        self.append_log(f"成功解析 Document XML 數：{summary['parsedXmlCount']}")
        self.append_log(f"元件群組數：{summary['componentGroupCount']}")
        self.append_log(f"找不到 Document XML 數：{len(summary['missingXmlFiles'])}")
        self.append_log(f"輸出 JSON：{output_json_path}")


# 中文註解：程式進入點；建立 Tkinter 根視窗並啟動 GUI 事件迴圈。
def main():
    """啟動 ssp_json_tabs.html 前置 JSON 產生工具。"""
    root_window = tk.Tk()
    SspJsonPrepareApp(root_window)
    root_window.mainloop()


if __name__ == "__main__":
    main()

