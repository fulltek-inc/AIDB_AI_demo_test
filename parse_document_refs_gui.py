#!/usr/bin/env python3
"""文件引用 XML 解析工具（GUI 版）。"""

import json
import os
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext


# 中文註解：取得 XML 節點文字，避免 None 造成輸出錯誤
def get_node_text(parent_node, tag_name):
    return (parent_node.findtext(tag_name, "") or "").strip()


# 中文註解：解析 XmlDocumentList 並輸出以 Name_CN 為 key 的 JSON 結構
def parse_document_refs(xml_path):
    # 中文註解：載入 XML 根節點
    xml_tree = ET.parse(xml_path)
    xml_root = xml_tree.getroot()

    # 中文註解：收集文件引用資料與重複 Name_CN 資訊
    document_refs = {}
    duplicate_name_count = 0
    duplicate_names = []
    duplicate_name_set = set()
    skipped_empty_name_count = 0

    for document_node in xml_root.findall(".//XmlDocumentList/XmlDocumentData_CLS"):
        name_cn = get_node_text(document_node, "Name_CN")

        if not name_cn:
            skipped_empty_name_count += 1
            continue

        if name_cn in document_refs:
            duplicate_name_count += 1
            if name_cn not in duplicate_name_set:
                duplicate_names.append(name_cn)
                duplicate_name_set.add(name_cn)
            continue

        document_refs[name_cn] = {
            "DocumentType": get_node_text(document_node, "DocumentType"),
            "ParentName": get_node_text(document_node, "ParentName"),
            "FactFileName": get_node_text(document_node, "FactFileName"),
            "XmlNb": get_node_text(document_node, "XmlNb"),
        }

    return document_refs, duplicate_name_count, duplicate_names, skipped_empty_name_count


# 中文註解：GUI 主程式，提供 XML 選檔、JSON 另存與解析按鈕
class DocumentRefsParserApp:
    # 中文註解：初始化視窗與各輸入元件
    def __init__(self, root_window):
        self.root_window = root_window
        self.root_window.title("文件引用 XML 解析工具")
        self.root_window.geometry("820x580")

        # 中文註解：保存使用者選擇的來源 XML 與輸出 JSON 路徑
        self.xml_path_var = tk.StringVar()
        self.output_path_var = tk.StringVar()

        file_frame = tk.Frame(self.root_window, padx=10, pady=10)
        file_frame.pack(fill=tk.X)

        tk.Label(file_frame, text="XML 檔案：").grid(row=0, column=0, sticky="w")
        xml_entry = tk.Entry(file_frame, textvariable=self.xml_path_var, width=84)
        xml_entry.grid(row=0, column=1, sticky="ew", padx=(6, 6))
        xml_button = tk.Button(file_frame, text="瀏覽...", command=self.select_xml_file)
        xml_button.grid(row=0, column=2, sticky="e")

        tk.Label(file_frame, text="輸出 JSON：").grid(row=1, column=0, sticky="w", pady=(8, 0))
        output_entry = tk.Entry(file_frame, textvariable=self.output_path_var, width=84)
        output_entry.grid(row=1, column=1, sticky="ew", padx=(6, 6), pady=(8, 0))
        output_button = tk.Button(file_frame, text="另存...", command=self.select_output_file)
        output_button.grid(row=1, column=2, sticky="e", pady=(8, 0))

        file_frame.columnconfigure(1, weight=1)

        action_frame = tk.Frame(self.root_window, padx=10)
        action_frame.pack(fill=tk.X)

        run_button = tk.Button(
            action_frame,
            text="開始解析",
            command=self.run_parse,
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

    # 中文註解：彈出檔案對話框讓使用者選擇 XML 檔
    def select_xml_file(self):
        selected_path = filedialog.askopenfilename(
            title="選擇 XML 檔案",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
        )
        if selected_path:
            self.xml_path_var.set(selected_path)
            self.output_path_var.set(self.build_default_output_path(selected_path))

    # 中文註解：彈出檔案對話框讓使用者指定 JSON 輸出檔
    def select_output_file(self):
        initial_path = self.output_path_var.get().strip()
        initial_dir = os.path.dirname(initial_path) if initial_path else os.getcwd()
        initial_file = os.path.basename(initial_path) if initial_path else "document_refs.json"

        selected_path = filedialog.asksaveasfilename(
            title="指定輸出 JSON 檔案",
            defaultextension=".json",
            initialdir=initial_dir,
            initialfile=initial_file,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if selected_path:
            self.output_path_var.set(selected_path)

    # 中文註解：依來源 XML 產生預設輸出 JSON 檔名
    def build_default_output_path(self, xml_file_path):
        base_path = os.path.splitext(xml_file_path)[0]
        return f"{base_path}_document_refs.json"

    # 中文註解：將訊息附加到日誌區
    def append_log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    # 中文註解：檢查輸入路徑並回傳可使用的輸出 JSON 路徑
    def validate_paths(self):
        xml_file_path = self.xml_path_var.get().strip()
        output_json_path = self.output_path_var.get().strip()

        if not xml_file_path:
            messagebox.showwarning("提示", "請先選擇 XML 檔案")
            return None, None

        if not os.path.isfile(xml_file_path):
            messagebox.showerror("錯誤", f"找不到檔案：\n{xml_file_path}")
            return None, None

        if not output_json_path:
            output_json_path = self.build_default_output_path(xml_file_path)
            self.output_path_var.set(output_json_path)

        return xml_file_path, output_json_path

    # 中文註解：執行解析並輸出 JSON
    def run_parse(self):
        self.log_text.delete("1.0", tk.END)
        xml_file_path, output_json_path = self.validate_paths()

        if not xml_file_path or not output_json_path:
            return

        self.append_log(f"開始解析：{xml_file_path}")
        self.append_log("-" * 60)

        try:
            document_refs, duplicate_name_count, duplicate_names, skipped_empty_name_count = parse_document_refs(
                xml_file_path
            )
        except ET.ParseError as exc:
            messagebox.showerror("XML 解析錯誤", str(exc))
            return
        except Exception as exc:  # pylint: disable=broad-except
            messagebox.showerror("執行錯誤", str(exc))
            return

        output_dir = os.path.dirname(os.path.abspath(output_json_path))
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(output_json_path, "w", encoding="utf-8") as output_file:
            json.dump(document_refs, output_file, ensure_ascii=False, indent=2)

        self.append_log(f"XmlDocumentData_CLS 輸出筆數：{len(document_refs)}")

        if duplicate_name_count > 0:
            self.append_log(f"重複 Name_CN 略過筆數：{duplicate_name_count}")
            self.append_log("重複 Name_CN 清單：")
            for duplicate_name in duplicate_names:
                self.append_log(f"- {duplicate_name}")

        if skipped_empty_name_count > 0:
            self.append_log(f"略過空白 Name_CN 筆數：{skipped_empty_name_count}")

        self.append_log("-" * 60)
        self.append_log(f"輸出 JSON：{output_json_path}")
        self.append_log("完成")

        messagebox.showinfo("完成", f"解析完成，已輸出：\n{output_json_path}")


# 中文註解：程式入口，啟動 GUI
def main():
    root_window = tk.Tk()
    DocumentRefsParserApp(root_window)
    root_window.mainloop()


if __name__ == "__main__":
    main()