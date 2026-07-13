#!/usr/bin/env python3
"""explorer.html 文件索引建立工具（GUI 版）。"""

import json
import os
import shutil
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext


# 中文註解：統一取得 XML 子節點文字；輸入為父節點與標籤名稱，輸出為去除前後空白的字串。
def get_node_text(parent_node, tag_name):
    """讀取指定子節點文字，避免 None 或多餘空白影響 JSON 索引內容。"""
    return (parent_node.findtext(tag_name, "") or "").strip()


# 中文註解：依 FactFileName 產生實際文件 XML 檔名；輸入為 XML 內的檔案編號，輸出為保留原名規則的檔名。
def build_document_xml_filename(fact_file_name):
    """將 FactFileName 轉成文件 XML 檔名，避免已含副檔名時重複加上 .xml。"""
    if fact_file_name.lower().endswith(".xml"):
        return fact_file_name
    return f"{fact_file_name}.xml"


# 中文註解：解析 XmlDocumentList 並建立 explorer.html 需要的三層索引；輸入 XML 路徑，輸出索引資料與統計資訊。
def build_explorer_index(xml_path):
    """將來源 XML 轉成 DocumentType / ParentName / Name_CN 的 explorer 索引格式。"""
    # 中文註解：載入 XML 樹狀資料；格式錯誤會由呼叫端捕捉並顯示給使用者。
    xml_tree = ET.parse(xml_path)
    xml_root = xml_tree.getroot()

    # 中文註解：index_data 是 explorer.html 直接讀取的 JSON 主體，採三層分類方便左側樹狀選單呈現。
    index_data = {}
    total_document_count = 0
    output_document_count = 0
    skipped_missing_key_count = 0
    duplicate_key_count = 0
    duplicate_keys = []
    duplicate_key_set = set()
    document_file_names = []
    document_file_name_set = set()

    for document_node in xml_root.findall(".//XmlDocumentList/XmlDocumentData_CLS"):
        total_document_count += 1

        document_type = get_node_text(document_node, "DocumentType")
        parent_name = get_node_text(document_node, "ParentName")
        name_cn = get_node_text(document_node, "Name_CN")
        xml_nb = get_node_text(document_node, "XmlNb")
        fact_file_name = get_node_text(document_node, "FactFileName")

        # 中文註解：三層 key 任一空白時 explorer.html 無法放入正確分類，因此略過並計數。
        if not document_type or not parent_name or not name_cn:
            skipped_missing_key_count += 1
            continue

        if document_type not in index_data:
            index_data[document_type] = {}
        if parent_name not in index_data[document_type]:
            index_data[document_type][parent_name] = {}

        duplicate_key = (document_type, parent_name, name_cn)
        if name_cn in index_data[document_type][parent_name]:
            duplicate_key_count += 1
            if duplicate_key not in duplicate_key_set:
                duplicate_keys.append(" / ".join(duplicate_key))
                duplicate_key_set.add(duplicate_key)

        # 中文註解：與 explorer.html 的 buildIndexFromXml 行為一致，重複 key 時以後讀到的資料覆蓋前一筆。
        index_data[document_type][parent_name][name_cn] = {
            "XmlNb": xml_nb,
            "FactFileName": fact_file_name,
        }
        output_document_count += 1

        # 中文註解：文件 XML 的實體檔案依 FactFileName 對應 Document 資料夾中的同名 .xml，重複資料只複製一次。
        if fact_file_name:
            document_file_name = build_document_xml_filename(fact_file_name)
            if document_file_name not in document_file_name_set:
                document_file_names.append(document_file_name)
                document_file_name_set.add(document_file_name)

    summary = {
        "totalDocumentCount": total_document_count,
        "outputDocumentCount": output_document_count,
        "skippedMissingKeyCount": skipped_missing_key_count,
        "duplicateKeyCount": duplicate_key_count,
        "duplicateKeys": duplicate_keys,
        "documentFileNames": document_file_names,
        "uniqueDocumentFileCount": len(document_file_names),
    }

    return index_data, summary


# 中文註解：依索引中的文件檔名複製 Document 資料夾 XML；輸入來源主 XML、目的資料夾與檔名清單，輸出複製統計。
def copy_document_xml_files(xml_path, target_folder_path, document_file_names):
    """將來源 XML 同層 Document 資料夾內的文件 XML 複製到指定資料夾，檔名保持不變。"""
    source_document_dir = os.path.join(os.path.dirname(os.path.abspath(xml_path)), "Document")
    target_dir = os.path.abspath(target_folder_path)

    # 中文註解：目的資料夾由使用者指定；不存在時建立，讓複製流程可以一次完成。
    os.makedirs(target_dir, exist_ok=True)

    copied_count = 0
    missing_files = []
    skipped_same_file_count = 0

    for document_file_name in document_file_names:
        source_file_path = os.path.join(source_document_dir, document_file_name)
        target_file_path = os.path.join(target_dir, document_file_name)

        # 中文註解：來源文件不存在時不中斷整批作業，改由日誌列出缺少清單方便補檔。
        if not os.path.isfile(source_file_path):
            missing_files.append(document_file_name)
            continue

        # 中文註解：若使用者誤選來源 Document 資料夾本身，避免 SameFileError 並保留原檔。
        if os.path.abspath(source_file_path) == os.path.abspath(target_file_path):
            skipped_same_file_count += 1
            continue

        # 中文註解：copy2 會覆蓋同名檔並保留檔案時間等中繼資訊，符合「檔名保留一樣」的複製需求。
        shutil.copy2(source_file_path, target_file_path)
        copied_count += 1

    return {
        "sourceDocumentDir": source_document_dir,
        "targetDir": target_dir,
        "copiedCount": copied_count,
        "missingCount": len(missing_files),
        "missingFiles": missing_files,
        "skippedSameFileCount": skipped_same_file_count,
    }


# 中文註解：GUI 主程式，提供 XML 選檔、JSON 另存與索引建立按鈕。
class ExplorerIndexBuilderApp:
    """explorer.html 文件索引建立工具的 Tkinter 應用程式。"""

    # 中文註解：初始化視窗與所有互動元件；輸入為 tkinter 根視窗，無回傳值。
    def __init__(self, root_window):
        self.root_window = root_window
        self.root_window.title("explorer.html 文件索引建立工具")
        self.root_window.geometry("860x640")

        # 中文註解：保存來源 XML、輸出 JSON 與文件複製目的資料夾，讓選檔、另存與執行流程共用。
        self.xml_path_var = tk.StringVar()
        self.output_path_var = tk.StringVar()
        self.copy_folder_var = tk.StringVar()

        file_frame = tk.Frame(self.root_window, padx=10, pady=10)
        file_frame.pack(fill=tk.X)

        tk.Label(file_frame, text="XML 檔案：").grid(row=0, column=0, sticky="w")
        xml_entry = tk.Entry(file_frame, textvariable=self.xml_path_var, width=88)
        xml_entry.grid(row=0, column=1, sticky="ew", padx=(6, 6))
        tk.Button(file_frame, text="瀏覽...", command=self.select_xml_file).grid(row=0, column=2)

        tk.Label(file_frame, text="輸出 JSON：").grid(row=1, column=0, sticky="w", pady=(8, 0))
        output_entry = tk.Entry(file_frame, textvariable=self.output_path_var, width=88)
        output_entry.grid(row=1, column=1, sticky="ew", padx=(6, 6), pady=(8, 0))
        tk.Button(file_frame, text="另存...", command=self.select_output_file).grid(row=1, column=2, pady=(8, 0))

        tk.Label(file_frame, text="文件 XML 複製到：").grid(row=2, column=0, sticky="w", pady=(8, 0))
        copy_entry = tk.Entry(file_frame, textvariable=self.copy_folder_var, width=88)
        copy_entry.grid(row=2, column=1, sticky="ew", padx=(6, 6), pady=(8, 0))
        tk.Button(file_frame, text="瀏覽...", command=self.select_copy_folder).grid(row=2, column=2, pady=(8, 0))

        file_frame.columnconfigure(1, weight=1)

        action_frame = tk.Frame(self.root_window, padx=10)
        action_frame.pack(fill=tk.X)

        run_button = tk.Button(
            action_frame,
            text="開始建立索引",
            command=self.run_build,
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

    # 中文註解：彈出檔案對話框讓使用者選擇來源 XML，並自動帶入預設輸出 JSON 路徑。
    def select_xml_file(self):
        selected_path = filedialog.askopenfilename(
            title="選擇 XML 檔案",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
        )
        if selected_path:
            self.xml_path_var.set(selected_path)
            self.output_path_var.set(self.build_default_output_path(selected_path))

    # 中文註解：彈出另存對話框，讓使用者指定 JSON 輸出檔名與位置。
    def select_output_file(self):
        initial_path = self.output_path_var.get().strip()
        initial_dir = os.path.dirname(initial_path) if initial_path else os.getcwd()
        initial_file = os.path.basename(initial_path) if initial_path else "document_index.json"

        selected_path = filedialog.asksaveasfilename(
            title="指定輸出 JSON 檔案",
            defaultextension=".json",
            initialdir=initial_dir,
            initialfile=initial_file,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if selected_path:
            self.output_path_var.set(selected_path)

    # 中文註解：彈出資料夾對話框，讓使用者指定找到的文件 XML 要複製到哪個資料夾。
    def select_copy_folder(self):
        selected_folder = filedialog.askdirectory(title="選擇文件 XML 複製目的資料夾")
        if selected_folder:
            self.copy_folder_var.set(selected_folder)

    # 中文註解：依來源 XML 檔名產生預設輸出路徑；輸出檔名符合「${來源XML檔名}_document_index.json」。
    def build_default_output_path(self, xml_file_path):
        base_path = os.path.splitext(xml_file_path)[0]
        return f"{base_path}_document_index.json"

    # 中文註解：將訊息附加到日誌區，方便確認輸出筆數、略過原因與重複索引。
    def append_log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    # 中文註解：檢查來源 XML、輸出 JSON 與可選複製資料夾；輸出清理後的路徑供建立索引流程使用。
    def validate_paths(self):
        xml_file_path = self.xml_path_var.get().strip()
        output_json_path = self.output_path_var.get().strip()
        copy_folder_path = self.copy_folder_var.get().strip()

        if not xml_file_path:
            messagebox.showwarning("提示", "請先選擇 XML 檔案")
            return None, None, None

        if not os.path.isfile(xml_file_path):
            messagebox.showerror("錯誤", f"找不到檔案：\n{xml_file_path}")
            return None, None, None

        if not output_json_path:
            output_json_path = self.build_default_output_path(xml_file_path)
            self.output_path_var.set(output_json_path)

        return xml_file_path, output_json_path, copy_folder_path

    # 中文註解：執行索引建立、寫出 JSON 並更新日誌；此方法負責 GUI 錯誤處理與完成提示。
    def run_build(self):
        self.log_text.delete("1.0", tk.END)
        xml_file_path, output_json_path, copy_folder_path = self.validate_paths()

        if not xml_file_path or not output_json_path:
            return

        self.append_log(f"開始建立索引：{xml_file_path}")
        self.append_log("-" * 60)

        try:
            index_data, summary = build_explorer_index(xml_file_path)
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
            json.dump(index_data, output_file, ensure_ascii=False, indent=2)

        self.append_log(f"XmlDocumentData_CLS 總筆數：{summary['totalDocumentCount']}")
        self.append_log(f"輸出索引筆數：{summary['outputDocumentCount']}")
        self.append_log(f"找到文件 XML 檔名數：{summary['uniqueDocumentFileCount']}")
        self.append_log(f"略過缺少 DocumentType / ParentName / Name_CN 筆數：{summary['skippedMissingKeyCount']}")

        if summary["duplicateKeyCount"] > 0:
            self.append_log(f"重複索引覆蓋筆數：{summary['duplicateKeyCount']}")
            self.append_log("重複索引清單：")
            for duplicate_key in summary["duplicateKeys"]:
                self.append_log(f"- {duplicate_key}")

        if copy_folder_path:
            copy_summary = copy_document_xml_files(
                xml_file_path,
                copy_folder_path,
                summary["documentFileNames"],
            )
            self.append_log("-" * 60)
            self.append_log(f"文件 XML 來源資料夾：{copy_summary['sourceDocumentDir']}")
            self.append_log(f"文件 XML 複製目的資料夾：{copy_summary['targetDir']}")
            self.append_log(f"成功複製文件 XML 數：{copy_summary['copiedCount']}")

            if copy_summary["skippedSameFileCount"] > 0:
                self.append_log(f"來源與目的相同而略過數：{copy_summary['skippedSameFileCount']}")

            if copy_summary["missingCount"] > 0:
                self.append_log(f"找不到來源文件 XML 數：{copy_summary['missingCount']}")
                self.append_log("找不到來源文件 XML 清單（最多顯示前 50 筆）：")
                for missing_file_name in copy_summary["missingFiles"][:50]:
                    self.append_log(f"- {missing_file_name}")

        self.append_log("-" * 60)
        self.append_log(f"輸出 JSON：{output_json_path}")
        self.append_log("完成")

        if copy_folder_path:
            messagebox.showinfo("完成", f"索引建立完成，文件 XML 也已複製到：\n{copy_folder_path}")
        else:
            messagebox.showinfo("完成", f"索引建立完成，已輸出：\n{output_json_path}")


# 中文註解：程式入口，啟動 explorer.html 文件索引建立 GUI。
def main():
    root_window = tk.Tk()
    ExplorerIndexBuilderApp(root_window)
    root_window.mainloop()


if __name__ == "__main__":
    main()
