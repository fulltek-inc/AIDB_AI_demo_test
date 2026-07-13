#!/usr/bin/env python3
"""SSP XML 解析工具（GUI 版）。"""

import json
import os
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext


# 中文註解：清理以逗號分隔的字串並轉成陣列

def split_csv_text(raw_text):
    # 中文註解：避免 None 造成 split 失敗
    text_value = raw_text or ""
    return [item.strip() for item in text_value.split(",") if item.strip()]


# 中文註解：依 FileID 檢查圖片位於 Site 或 Pin

def find_picture_location(base_dir, file_id):
    # 中文註解：組合 Site / Pin 圖片完整路徑
    site_file_path = os.path.join(base_dir, "Picture", "Site", f"{file_id}.png")
    pin_file_path = os.path.join(base_dir, "Picture", "Pin", f"{file_id}.png")

    if os.path.exists(site_file_path):
        return "site"
    if os.path.exists(pin_file_path):
        return "pin"
    return None


# 中文註解：解析 XML 並輸出目標 JSON 結構

def parse_ssp_xml(xml_path):
    # 中文註解：載入 XML 根節點
    xml_tree = ET.parse(xml_path)
    xml_root = xml_tree.getroot()

    # 中文註解：以 XML 所在目錄作為圖片資料夾的基準位置
    base_dir = os.path.dirname(os.path.abspath(xml_path))

    # 中文註解：收集 ProjectList 結果
    project_list = []
    for project_node in xml_root.findall(".//ProjectList/ProjectData"):
        include_raw = project_node.findtext("includeObjectName", "")
        include_items = split_csv_text(include_raw)

        project_item = {
            "SSPNb": project_node.findtext("SSPNb", ""),
            "FactCls": project_node.findtext("FactCls", ""),
            "Name_CN": project_node.findtext("Name_CN", ""),
            "FactFileName": project_node.findtext("FactFileName", ""),
            "ParentName": project_node.findtext("ParentName", ""),
            "Specify_AutoInt": project_node.findtext("Specify_AutoInt", ""),
            "Specify_Nb": project_node.findtext("Specify_Nb", ""),
            "Specify_Tw": project_node.findtext("Specify_Tw", ""),
            "includeObjectName": include_items,
        }
        project_list.append(project_item)

    # 中文註解：依圖片來源位置分流到 site / pin
    picture_list_site = []
    picture_list_pin = []
    missing_picture_count = 0

    for picture_node in xml_root.findall(".//PictureList/PictureData_CLS"):
        file_id = picture_node.findtext("FileID", "")
        name_cn_items = split_csv_text(picture_node.findtext("Name_CN", ""))

        picture_item = {
            "FileID": file_id,
            "Name_CN": name_cn_items,
            "PictureType": picture_node.findtext("PictureType", ""),
            "ParentName": picture_node.findtext("ParentName", ""),
            "INFOOBJECTID": picture_node.findtext("INFOOBJECTID", ""),
        }

        picture_location = find_picture_location(base_dir, file_id)
        if picture_location == "site":
            picture_list_site.append(picture_item)
        elif picture_location == "pin":
            picture_list_pin.append(picture_item)
        else:
            picture_item["_note"] = "file not found in Picture/Site or Picture/Pin"
            picture_list_site.append(picture_item)
            missing_picture_count += 1

    result_json = {
        "ProjectList": project_list,
        "PictureList_site": picture_list_site,
        "PictureList_pin": picture_list_pin,
    }

    return result_json, missing_picture_count


# 中文註解：GUI 主程式，提供選檔與執行按鈕

class SspXmlParserApp:
    # 中文註解：初始化視窗與元件
    def __init__(self, root_window):
        self.root_window = root_window
        self.root_window.title("SSP XML 解析工具")
        self.root_window.geometry("780x560")

        self.xml_path_var = tk.StringVar()

        top_frame = tk.Frame(self.root_window, padx=10, pady=10)
        top_frame.pack(fill=tk.X)

        tk.Label(top_frame, text="XML 檔案：").pack(side=tk.LEFT)

        path_entry = tk.Entry(top_frame, textvariable=self.xml_path_var, width=80)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 6))

        browse_button = tk.Button(top_frame, text="瀏覽...", command=self.select_xml_file)
        browse_button.pack(side=tk.LEFT)

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

        self.log_text = scrolledtext.ScrolledText(log_frame, font=("Consolas", 10), height=22)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    # 中文註解：彈出檔案對話框讓使用者選擇 XML 檔
    def select_xml_file(self):
        selected_path = filedialog.askopenfilename(
            title="選擇 XML 檔案",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
        )
        if selected_path:
            self.xml_path_var.set(selected_path)

    # 中文註解：將訊息附加到日誌區
    def append_log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    # 中文註解：執行解析並輸出 JSON
    def run_parse(self):
        self.log_text.delete("1.0", tk.END)
        xml_file_path = self.xml_path_var.get().strip()

        if not xml_file_path:
            messagebox.showwarning("提示", "請先選擇 XML 檔案")
            return

        if not os.path.isfile(xml_file_path):
            messagebox.showerror("錯誤", f"找不到檔案：\n{xml_file_path}")
            return

        self.append_log(f"開始解析：{xml_file_path}")
        self.append_log("-" * 60)

        try:
            result_json, missing_picture_count = parse_ssp_xml(xml_file_path)
        except ET.ParseError as exc:
            messagebox.showerror("XML 解析錯誤", str(exc))
            return
        except Exception as exc:  # pylint: disable=broad-except
            messagebox.showerror("執行錯誤", str(exc))
            return

        # 中文註解：主資料 JSON 統一加上 _data 後綴，方便與其他輔助 JSON 檔案區分。
        output_json_path = os.path.splitext(xml_file_path)[0] + "_data.json"
        with open(output_json_path, "w", encoding="utf-8") as output_file:
            json.dump(result_json, output_file, ensure_ascii=False, indent=2)

        self.append_log(f"ProjectList 筆數：{len(result_json['ProjectList'])}")
        self.append_log(f"PictureList_site 筆數：{len(result_json['PictureList_site'])}")
        self.append_log(f"PictureList_pin 筆數：{len(result_json['PictureList_pin'])}")

        if missing_picture_count > 0:
            self.append_log(f"未找到對應圖片的筆數：{missing_picture_count}")

        self.append_log("-" * 60)
        self.append_log(f"輸出 JSON：{output_json_path}")
        self.append_log("完成")

        messagebox.showinfo("完成", f"解析完成，已輸出：\n{output_json_path}")


# 中文註解：程式入口，啟動 GUI

def main():
    root_window = tk.Tk()
    SspXmlParserApp(root_window)
    root_window.mainloop()


if __name__ == "__main__":
    main()

