#!/usr/bin/env python3
"""依 JSON 清單複製 Site、Pin、Document 檔案的 GUI 工具。"""

import json
import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext


# 中文註解：定義 JSON key、來源子資料夾與輸出子資料夾的對應關係；集中管理可避免三組複製規則散落在程式中。
MOVE_RULES = {
    "site": {
        "source_folder": os.path.join("Picture", "Site"),
        "output_folder": os.path.join("parse", "site"),
    },
    "pin": {
        "source_folder": os.path.join("Picture", "Pin"),
        "output_folder": os.path.join("parse", "pin"),
    },
    "doc": {
        "source_folder": "Document",
        "output_folder": os.path.join("parse", "doc"),
    },
}


# 中文註解：讀取 JSON 檔並驗證必要結構；輸入為 JSON 路徑，輸出為已解析的 dict，格式錯誤時拋出 ValueError。
def load_refs_json(json_path):
    """載入包含 site、pin、doc 陣列的 JSON，並確認每個項目都是可複製的檔名字串。"""
    with open(json_path, "r", encoding="utf-8") as input_file:
        refs_data = json.load(input_file)

    if not isinstance(refs_data, dict):
        raise ValueError("JSON 最外層必須是物件，並包含 site、pin、doc 三個陣列")

    for refs_key in MOVE_RULES:
        refs_items = refs_data.get(refs_key, [])

        if not isinstance(refs_items, list):
            raise ValueError(f"JSON 欄位 {refs_key} 必須是陣列")

        for item_index, refs_item in enumerate(refs_items, start=1):
            if not isinstance(refs_item, str):
                raise ValueError(f"JSON 欄位 {refs_key} 第 {item_index} 筆必須是檔名字串")

    return refs_data


# 中文註解：避免 JSON 中的相對路徑跳出指定來源資料夾；輸入為根目錄與檔名，輸出為安全的完整路徑。
def build_safe_child_path(parent_folder, child_name):
    """將檔名組成完整路徑，並阻擋 .. 等可能複製到資料夾外的路徑。"""
    parent_abs_path = os.path.abspath(parent_folder)
    child_abs_path = os.path.abspath(os.path.join(parent_abs_path, child_name))

    if os.path.commonpath([parent_abs_path, child_abs_path]) != parent_abs_path:
        raise ValueError(f"路徑超出允許範圍：{child_name}")

    return child_abs_path


# 中文註解：複製單一類別的檔案清單；輸入為類別 key、檔名清單與來源/輸出根目錄，輸出統計與詳細訊息。
def copy_ref_files(refs_key, refs_items, source_root_path, output_root_path):
    """依 MOVE_RULES 將指定類別的檔案複製到 parse 子資料夾，目標已存在時略過避免覆蓋。"""
    rule = MOVE_RULES[refs_key]
    source_folder = os.path.join(source_root_path, rule["source_folder"])
    output_folder = os.path.join(output_root_path, rule["output_folder"])
    os.makedirs(output_folder, exist_ok=True)

    summary = {
        "totalCount": len(refs_items),
        "copiedCount": 0,
        "missingCount": 0,
        "skippedExistingCount": 0,
        "invalidPathCount": 0,
        "messages": [],
    }

    for refs_item in refs_items:
        item_name = refs_item.strip()

        # 中文註解：空字串沒有可複製的檔案名稱，記錄為無效路徑並繼續處理其他項目。
        if not item_name:
            summary["invalidPathCount"] += 1
            summary["messages"].append("略過空白檔名")
            continue

        try:
            source_file_path = build_safe_child_path(source_folder, item_name)
            output_file_path = build_safe_child_path(output_folder, item_name)
        except ValueError as exc:
            summary["invalidPathCount"] += 1
            summary["messages"].append(str(exc))
            continue

        if not os.path.isfile(source_file_path):
            summary["missingCount"] += 1
            summary["messages"].append(f"找不到來源：{source_file_path}")
            continue

        if os.path.exists(output_file_path):
            summary["skippedExistingCount"] += 1
            summary["messages"].append(f"目標已存在，略過：{output_file_path}")
            continue

        output_file_dir = os.path.dirname(output_file_path)
        if output_file_dir:
            os.makedirs(output_file_dir, exist_ok=True)

        shutil.copy2(source_file_path, output_file_path)
        summary["copiedCount"] += 1
        summary["messages"].append(f"已複製：{source_file_path} -> {output_file_path}")

    return summary


# 中文註解：GUI 主程式，提供 JSON 選檔、來源根目錄、輸出根目錄與複製按鈕。
class JsonRefsCopyApp:
    """依 JSON 清單複製 Site、Pin、Document 檔案的 Tkinter 應用程式。"""

    # 中文註解：初始化視窗與路徑欄位；輸入為 tkinter 根視窗，無回傳值。
    def __init__(self, root_window):
        self.root_window = root_window
        self.root_window.title("JSON 檔案複製工具")
        self.root_window.geometry("900x640")

        # 中文註解：保存使用者選擇的 JSON、來源根目錄與輸出根目錄，供按鈕事件共用。
        self.json_path_var = tk.StringVar()
        self.source_root_path_var = tk.StringVar()
        self.output_root_path_var = tk.StringVar()

        file_frame = tk.Frame(self.root_window, padx=10, pady=10)
        file_frame.pack(fill=tk.X)

        tk.Label(file_frame, text="來源 JSON：").grid(row=0, column=0, sticky="w")
        tk.Entry(file_frame, textvariable=self.json_path_var, width=90).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(6, 6),
        )
        tk.Button(file_frame, text="瀏覽...", command=self.select_json_file).grid(row=0, column=2)

        tk.Label(file_frame, text="來源根目錄：").grid(row=1, column=0, sticky="w", pady=(8, 0))
        tk.Entry(file_frame, textvariable=self.source_root_path_var, width=90).grid(
            row=1,
            column=1,
            sticky="ew",
            padx=(6, 6),
            pady=(8, 0),
        )
        tk.Button(file_frame, text="瀏覽...", command=self.select_source_root_folder).grid(row=1, column=2, pady=(8, 0))

        tk.Label(file_frame, text="輸出根目錄：").grid(row=2, column=0, sticky="w", pady=(8, 0))
        tk.Entry(file_frame, textvariable=self.output_root_path_var, width=90).grid(
            row=2,
            column=1,
            sticky="ew",
            padx=(6, 6),
            pady=(8, 0),
        )
        tk.Button(file_frame, text="瀏覽...", command=self.select_output_root_folder).grid(row=2, column=2, pady=(8, 0))

        file_frame.columnconfigure(1, weight=1)

        hint_frame = tk.Frame(self.root_window, padx=10)
        hint_frame.pack(fill=tk.X)

        # 中文註解：用固定文字提醒複製規則，避免使用者選錯來源根目錄後找不到檔案。
        tk.Label(
            hint_frame,
            text="複製規則：site = Picture\\Site，pin = Picture\\Pin，doc = Document；輸出到 parse\\site、parse\\pin、parse\\doc",
            anchor="w",
        ).pack(fill=tk.X)

        action_frame = tk.Frame(self.root_window, padx=10)
        action_frame.pack(fill=tk.X)

        run_button = tk.Button(
            action_frame,
            text="開始複製",
            command=self.run_copy,
            bg="#2E7D32",
            fg="white",
            font=("Microsoft JhengHei UI", 11, "bold"),
            padx=14,
            pady=6,
        )
        run_button.pack(pady=(8, 8))

        log_frame = tk.Frame(self.root_window, padx=10, pady=6)
        log_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(log_frame, text="執行結果：", anchor="w").pack(fill=tk.X)
        self.log_text = scrolledtext.ScrolledText(log_frame, font=("Consolas", 10), height=24)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    # 中文註解：讓使用者選擇來源 JSON；選定後預設來源與輸出根目錄為 JSON 所在資料夾。
    def select_json_file(self):
        """彈出檔案對話框選取 JSON，並帶入合理的預設資料夾降低手動輸入錯誤。"""
        selected_path = filedialog.askopenfilename(
            title="選擇來源 JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if selected_path:
            selected_folder = os.path.dirname(selected_path)
            self.json_path_var.set(selected_path)
            if not self.source_root_path_var.get().strip():
                self.source_root_path_var.set(selected_folder)
            if not self.output_root_path_var.get().strip():
                self.output_root_path_var.set(selected_folder)

    # 中文註解：讓使用者選擇包含 Picture 與 Document 的來源根目錄。
    def select_source_root_folder(self):
        """選擇來源根目錄，程式會在其下尋找 Picture\\Site、Picture\\Pin、Document。"""
        selected_folder = filedialog.askdirectory(title="選擇來源根目錄")
        if selected_folder:
            self.source_root_path_var.set(selected_folder)

    # 中文註解：讓使用者選擇 parse 資料夾要建立在哪個輸出根目錄下。
    def select_output_root_folder(self):
        """選擇輸出根目錄，程式會在其下建立 parse\\site、parse\\pin、parse\\doc。"""
        selected_folder = filedialog.askdirectory(title="選擇輸出根目錄")
        if selected_folder:
            self.output_root_path_var.set(selected_folder)

    # 中文註解：將執行訊息寫入日誌區並更新畫面；輸入為訊息文字，無回傳值。
    def append_log(self, message):
        """集中處理 GUI 日誌，讓長時間複製時也能即時看到進度。"""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root_window.update_idletasks()

    # 中文註解：檢查 GUI 欄位與來源資料夾是否可用；輸出三個絕對路徑供複製流程使用。
    def validate_paths(self):
        """驗證 JSON、來源根目錄與輸出根目錄，避免複製流程執行到一半才發現基本路徑錯誤。"""
        json_path = self.json_path_var.get().strip()
        source_root_path = self.source_root_path_var.get().strip()
        output_root_path = self.output_root_path_var.get().strip()

        if not json_path:
            messagebox.showwarning("提示", "請先選擇來源 JSON")
            return None, None, None

        if not os.path.isfile(json_path):
            messagebox.showerror("錯誤", f"找不到來源 JSON：\n{json_path}")
            return None, None, None

        if not source_root_path:
            messagebox.showwarning("提示", "請先選擇來源根目錄")
            return None, None, None

        if not os.path.isdir(source_root_path):
            messagebox.showerror("錯誤", f"找不到來源根目錄：\n{source_root_path}")
            return None, None, None

        if not output_root_path:
            output_root_path = os.path.dirname(os.path.abspath(json_path))
            self.output_root_path_var.set(output_root_path)

        return os.path.abspath(json_path), os.path.abspath(source_root_path), os.path.abspath(output_root_path)

    # 中文註解：執行 JSON 載入與三類檔案複製；此方法負責 GUI 錯誤處理、確認提示與統計輸出。
    def run_copy(self):
        """依 site、pin、doc 三組規則複製檔案，並在日誌中列出每筆結果。"""
        self.log_text.delete("1.0", tk.END)
        json_path, source_root_path, output_root_path = self.validate_paths()

        if not json_path or not source_root_path or not output_root_path:
            return

        confirm_message = (
            "此操作會複製檔案，來源檔案會保留在原資料夾。\n\n"
            f"來源根目錄：\n{source_root_path}\n\n"
            f"輸出根目錄：\n{output_root_path}\n\n"
            "是否繼續？"
        )
        if not messagebox.askyesno("確認複製", confirm_message):
            return

        self.append_log(f"來源 JSON：{json_path}")
        self.append_log(f"來源根目錄：{source_root_path}")
        self.append_log(f"輸出根目錄：{output_root_path}")
        self.append_log("-" * 60)

        try:
            refs_data = load_refs_json(json_path)
        except json.JSONDecodeError as exc:
            messagebox.showerror("JSON 解析錯誤", str(exc))
            self.append_log(f"JSON 解析錯誤：{exc}")
            return
        except ValueError as exc:
            messagebox.showerror("JSON 格式錯誤", str(exc))
            self.append_log(f"JSON 格式錯誤：{exc}")
            return
        except Exception as exc:  # pylint: disable=broad-except
            messagebox.showerror("執行錯誤", str(exc))
            self.append_log(f"執行錯誤：{exc}")
            return

        total_copied_count = 0
        total_missing_count = 0
        total_skipped_existing_count = 0
        total_invalid_path_count = 0

        try:
            for refs_key in MOVE_RULES:
                self.append_log(f"[{refs_key}] 開始複製")
                summary = copy_ref_files(refs_key, refs_data.get(refs_key, []), source_root_path, output_root_path)

                total_copied_count += summary["copiedCount"]
                total_missing_count += summary["missingCount"]
                total_skipped_existing_count += summary["skippedExistingCount"]
                total_invalid_path_count += summary["invalidPathCount"]

                self.append_log(f"[{refs_key}] 清單筆數：{summary['totalCount']}")
                self.append_log(f"[{refs_key}] 成功複製：{summary['copiedCount']}")
                self.append_log(f"[{refs_key}] 找不到來源：{summary['missingCount']}")
                self.append_log(f"[{refs_key}] 目標已存在略過：{summary['skippedExistingCount']}")
                self.append_log(f"[{refs_key}] 無效路徑略過：{summary['invalidPathCount']}")

                if summary["messages"]:
                    self.append_log(f"[{refs_key}] 詳細紀錄：")
                    for detail_message in summary["messages"]:
                        self.append_log(f"- {detail_message}")

                self.append_log("-" * 60)
        except Exception as exc:  # pylint: disable=broad-except
            messagebox.showerror("複製錯誤", str(exc))
            self.append_log(f"複製錯誤：{exc}")
            return

        self.append_log("總計")
        self.append_log(f"成功複製：{total_copied_count}")
        self.append_log(f"找不到來源：{total_missing_count}")
        self.append_log(f"目標已存在略過：{total_skipped_existing_count}")
        self.append_log(f"無效路徑略過：{total_invalid_path_count}")
        self.append_log("完成")

        messagebox.showinfo("完成", f"複製完成，成功複製 {total_copied_count} 個檔案")


# 中文註解：程式入口；建立 Tkinter 根視窗並啟動 GUI 事件迴圈，讓此檔可直接用 python 執行。
def main():
    """啟動 JSON 檔案複製工具。"""
    root_window = tk.Tk()
    JsonRefsCopyApp(root_window)
    root_window.mainloop()


if __name__ == "__main__":
    main()


