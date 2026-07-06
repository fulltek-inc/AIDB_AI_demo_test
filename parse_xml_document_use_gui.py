#!/usr/bin/env python3
"""從 SSP XML 的 PictureList 匯出 XMLDocumentUse 圖片對照表（GUI 版）。"""

import json
import os
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext


# 中文註解：統一清理 XML 節點文字，避免 None、換行或前後空白影響比對與輸出。
def clean_text(raw_text):
    """將輸入文字轉成去除前後空白的字串；輸入可為 None，輸出固定為字串。"""
    return (raw_text or "").strip()


# 中文註解：解析 PictureList 中 PictureType 為 XMLDocumentUse 的資料，輸出 Name_CN 對 FileID 的字典。
def parse_xml_document_use(xml_path):
    """讀取指定 XML 檔，回傳 XMLDocumentUse 對照表與統計資訊。"""
    # 中文註解：載入 XML 根節點；若 XML 格式錯誤，讓呼叫端統一顯示錯誤訊息。
    xml_tree = ET.parse(xml_path)
    xml_root = xml_tree.getroot()

    document_use_map = {}
    duplicate_items = []
    duplicate_item_keys = set()
    skipped_empty_name_count = 0
    skipped_empty_file_id_count = 0
    matched_picture_count = 0

    for picture_node in xml_root.findall(".//PictureList/PictureData_CLS"):
        picture_type = clean_text(picture_node.findtext("PictureType"))

        # 中文註解：需求只需要 XMLDocumentUse，其他 PictureType 不納入輸出。
        if picture_type != "XMLDocumentUse":
            continue

        matched_picture_count += 1
        name_cn = clean_text(picture_node.findtext("Name_CN"))
        file_id = clean_text(picture_node.findtext("FileID"))

        # 中文註解：Name_CN 是 JSON key，空白時無法建立可用索引，因此略過並計數。
        if not name_cn:
            skipped_empty_name_count += 1
            continue

        # 中文註解：FileID 是 JSON value，空白時輸出沒有實際用途，因此略過並計數。
        if not file_id:
            skipped_empty_file_id_count += 1
            continue

        # 中文註解：同一個 Name_CN 重複時保留第一筆；若 FileID 相同代表只是同資料重複，不需提醒。
        if name_cn in document_use_map:
            kept_file_id = document_use_map[name_cn]
            if kept_file_id != file_id:
                duplicate_key = (name_cn, kept_file_id, file_id)
                if duplicate_key not in duplicate_item_keys:
                    duplicate_items.append(
                        {
                            "Name_CN": name_cn,
                            "keptFileID": kept_file_id,
                            "skippedFileID": file_id,
                        }
                    )
                    duplicate_item_keys.add(duplicate_key)
            continue

        document_use_map[name_cn] = file_id

    summary = {
        "matchedPictureCount": matched_picture_count,
        "outputCount": len(document_use_map),
        "duplicateNameDifferentFileIdCount": len(duplicate_items),
        "duplicateItems": duplicate_items,
        "skippedEmptyNameCount": skipped_empty_name_count,
        "skippedEmptyFileIdCount": skipped_empty_file_id_count,
    }

    return document_use_map, summary


# 中文註解：GUI 主程式，提供 XML 選檔、JSON 另存與解析按鈕。
class XmlDocumentUseParserApp:
    """XMLDocumentUse 對照表匯出工具的 GUI 應用程式。"""

    # 中文註解：初始化視窗與所有互動元件；輸入為 tkinter 根視窗，無回傳值。
    def __init__(self, root_window):
        self.root_window = root_window
        self.root_window.title("XMLDocumentUse 對照表匯出工具")
        self.root_window.geometry("840x580")

        # 中文註解：保存使用者選擇的來源 XML 與輸出 JSON 路徑，供按鈕事件共用。
        self.xml_path_var = tk.StringVar()
        self.output_path_var = tk.StringVar()

        file_frame = tk.Frame(self.root_window, padx=10, pady=10)
        file_frame.pack(fill=tk.X)

        tk.Label(file_frame, text="XML 檔案：").grid(row=0, column=0, sticky="w")
        xml_entry = tk.Entry(file_frame, textvariable=self.xml_path_var, width=86)
        xml_entry.grid(row=0, column=1, sticky="ew", padx=(6, 6))
        tk.Button(file_frame, text="瀏覽...", command=self.select_xml_file).grid(row=0, column=2)

        tk.Label(file_frame, text="輸出 JSON：").grid(row=1, column=0, sticky="w", pady=(8, 0))
        output_entry = tk.Entry(file_frame, textvariable=self.output_path_var, width=86)
        output_entry.grid(row=1, column=1, sticky="ew", padx=(6, 6), pady=(8, 0))
        tk.Button(file_frame, text="另存...", command=self.select_output_file).grid(row=1, column=2, pady=(8, 0))

        file_frame.columnconfigure(1, weight=1)

        action_frame = tk.Frame(self.root_window, padx=10)
        action_frame.pack(fill=tk.X)

        run_button = tk.Button(
            action_frame,
            text="開始匯出",
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

    # 中文註解：彈出檔案對話框讓使用者選擇來源 XML，並自動帶入預設輸出路徑。
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
        initial_file = os.path.basename(initial_path) if initial_path else "xml_document_use.json"

        selected_path = filedialog.asksaveasfilename(
            title="指定輸出 JSON 檔案",
            defaultextension=".json",
            initialdir=initial_dir,
            initialfile=initial_file,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if selected_path:
            self.output_path_var.set(selected_path)

    # 中文註解：依來源 XML 檔名產生預設輸出 JSON 路徑，避免覆蓋 parse_ssp_xml_gui.py 的主 JSON。
    def build_default_output_path(self, xml_file_path):
        base_path = os.path.splitext(xml_file_path)[0]
        return f"{base_path}_xml_document_use.json"

    # 中文註解：將訊息附加到日誌區，方便使用者確認輸出筆數與略過原因。
    def append_log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    # 中文註解：檢查來源 XML 與輸出 JSON 路徑是否可用；回傳清理後的路徑供主流程使用。
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

    # 中文註解：執行 XMLDocumentUse 解析並寫出 JSON；此方法負責 GUI 錯誤處理與結果日誌。
    def run_parse(self):
        self.log_text.delete("1.0", tk.END)
        xml_file_path, output_json_path = self.validate_paths()

        if not xml_file_path or not output_json_path:
            return

        self.append_log(f"開始解析：{xml_file_path}")
        self.append_log("-" * 60)

        try:
            document_use_map, summary = parse_xml_document_use(xml_file_path)
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
            json.dump(document_use_map, output_file, ensure_ascii=False, indent=2)

        self.append_log(f"XMLDocumentUse 符合筆數：{summary['matchedPictureCount']}")
        self.append_log(f"輸出筆數：{summary['outputCount']}")

        if summary["duplicateNameDifferentFileIdCount"] > 0:
            self.append_log(
                f"重複 Name_CN 但 FileID 不同的略過組數：{summary['duplicateNameDifferentFileIdCount']}"
            )
            self.append_log("重複 Name_CN / FileID 差異清單：")
            for duplicate_item in summary["duplicateItems"]:
                self.append_log(
                    "- "
                    f"{duplicate_item['Name_CN']} "
                    f"保留 FileID={duplicate_item['keptFileID']}，"
                    f"略過 FileID={duplicate_item['skippedFileID']}"
                )

        if summary["skippedEmptyNameCount"] > 0:
            self.append_log(f"略過空白 Name_CN 筆數：{summary['skippedEmptyNameCount']}")

        if summary["skippedEmptyFileIdCount"] > 0:
            self.append_log(f"略過空白 FileID 筆數：{summary['skippedEmptyFileIdCount']}")

        self.append_log("-" * 60)
        self.append_log(f"輸出 JSON：{output_json_path}")
        self.append_log("完成")

        messagebox.showinfo("完成", f"匯出完成，已輸出：\n{output_json_path}")


# 中文註解：程式入口，啟動 GUI；讓此檔案可直接用 python 執行。
def main():
    root_window = tk.Tk()
    XmlDocumentUseParserApp(root_window)
    root_window.mainloop()


if __name__ == "__main__":
    main()


