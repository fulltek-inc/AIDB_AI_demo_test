#!/usr/bin/env python3
"""依 parse_ssp_xml_gui.py 輸出的 JSON 批次解析 Document XML 的元件與插頭清單。"""

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext


# 中文註解：統一清理 XML / JSON 讀出的文字，避免 None、換行或前後空白影響判斷。
def clean_text(raw_text):
    """將輸入文字轉為去除前後空白的字串；輸入可為 None，輸出固定為字串。"""
    return (raw_text or "").strip()


# 中文註解：從 parse_ssp_xml_gui.py 的 JSON 內取出所有需要解析的 FactFileName。
def load_fact_file_names(input_json_path):
    """讀取輸入 JSON，回傳 ProjectList 中不重複且非空白的 FactFileName 清單。"""
    with open(input_json_path, "r", encoding="utf-8") as input_file:
        input_data = json.load(input_file)

    project_list = input_data.get("ProjectList", [])
    fact_file_names = []
    seen_fact_file_names = set()

    for project_item in project_list:
        # 中文註解：FactFileName 是 Document 資料夾下 XML 的檔名主體，例如 178074。
        fact_file_name = clean_text(project_item.get("FactFileName"))
        if not fact_file_name or fact_file_name in seen_fact_file_names:
            continue

        seen_fact_file_names.add(fact_file_name)
        fact_file_names.append(fact_file_name)

    return fact_file_names


# 中文註解：解析單一 Document XML，將 CompeData 轉為 {Number: {name, plugList}} 的局部結果。
def parse_document_xml(xml_path):
    """解析單一 XML 的 CompeList，回傳元件編號對應的名稱與插頭名稱清單。"""
    xml_tree = ET.parse(xml_path)
    xml_root = xml_tree.getroot()
    component_map = {}

    for compe_node in xml_root.findall(".//CompeList/CompeData"):
        # 中文註解：Number 是輸出 JSON 的 key；若空白就無法建立穩定索引，因此略過。
        component_number = clean_text(compe_node.findtext("Number"))
        component_name = clean_text(compe_node.findtext("Name"))

        # 中文註解：需求指定 CompeData 的 Name 空白時不抓取，所以直接跳過該筆。
        if not component_number or not component_name:
            continue

        component_item = component_map.setdefault(
            component_number,
            {
                "name": component_name,
                "plugList": [],
            },
        )

        # 中文註解：同一 Number 可能重複出現；保留第一個非空名稱，插頭清單則持續合併。
        if not clean_text(component_item.get("name")):
            component_item["name"] = component_name

        for plug_node in compe_node.findall("./PlugList/PlugData"):
            # 中文註解：需求指定 PlugData 的 Name 空白時不抓取，並避免同元件重複加入相同插頭。
            plug_name = clean_text(plug_node.findtext("Name"))
            if plug_name and plug_name not in component_item["plugList"]:
                component_item["plugList"].append(plug_name)

    return component_map


# 中文註解：把單一 XML 的解析結果合併到總結果，並以來源檔名區隔不同 XML 的同名元件。
def merge_component_maps(target_map, source_file_name, source_map):
    """將來源元件資料依檔名合併到目標字典；輸入為來源檔名與元件資料，輸出會更新 target_map。"""
    for component_number, source_item in source_map.items():
        # 中文註解：第一層用 Number，第二層用不含副檔名的 FactFileName，避免不同 XML 的同 Number 混在一起。
        file_map = target_map.setdefault(component_number, {})
        target_item = file_map.setdefault(source_file_name, {"name": source_item["name"], "plugList": []})

        # 中文註解：同一來源檔案內若 Number 重複，名稱以第一個遇到的非空值為主。
        if not clean_text(target_item.get("name")):
            target_item["name"] = source_item["name"]

        for plug_name in source_item.get("plugList", []):
            if plug_name and plug_name not in target_item["plugList"]:
                target_item["plugList"].append(plug_name)


# 中文註解：將同一 Number 底下內容相同的來源檔案合併，減少重複資料並保留 sourceFiles 追溯來源。
def group_same_component_sources(component_source_map):
    """整理元件來源資料；輸入為 {Number: {FactFileName: item}}，輸出為 {Number: [group_item]}。"""
    grouped_result = {}

    for component_number, source_map in component_source_map.items():
        grouped_items = []
        grouped_index = {}

        for source_file_name, component_item in source_map.items():
            component_name = component_item.get("name", "")
            plug_list = component_item.get("plugList", [])
            # 中文註解：plugList 以排序後的 tuple 作為比對 key，讓順序不同但內容相同的清單仍可合併。
            group_key = (component_name, tuple(sorted(plug_list)))

            if group_key not in grouped_index:
                grouped_index[group_key] = len(grouped_items)
                grouped_items.append(
                    {
                        "name": component_name,
                        "plugList": list(plug_list),
                        "sourceFiles": [],
                    }
                )

            grouped_items[grouped_index[group_key]]["sourceFiles"].append(source_file_name)

        grouped_result[component_number] = grouped_items

    return grouped_result

# 中文註解：主處理流程，依輸入 JSON 找 Document XML、解析 CompeData，並寫出結果 JSON。
def extract_compe_plugs(input_json_path, output_json_path=None):
    """處理 parse_ssp_xml_gui.py 輸出的 JSON，回傳輸出路徑與統計資訊。"""
    absolute_input_path = os.path.abspath(input_json_path)
    base_dir = os.path.dirname(absolute_input_path)
    document_dir = os.path.join(base_dir, "Document")

    if not os.path.isfile(absolute_input_path):
        raise FileNotFoundError(f"找不到輸入 JSON：{absolute_input_path}")

    if not os.path.isdir(document_dir):
        raise FileNotFoundError(f"找不到 Document 資料夾：{document_dir}")

    fact_file_names = load_fact_file_names(absolute_input_path)
    result_map = {}
    missing_xml_files = []
    parse_error_files = []
    parsed_xml_count = 0

    for fact_file_name in fact_file_names:
        xml_path = os.path.join(document_dir, f"{fact_file_name}.xml")

        if not os.path.isfile(xml_path):
            missing_xml_files.append(xml_path)
            continue

        try:
            document_component_map = parse_document_xml(xml_path)
        except ET.ParseError as exc:
            # 中文註解：單一 XML 解析失敗時先記錄，讓其他 XML 仍可繼續處理。
            parse_error_files.append({"path": xml_path, "error": str(exc)})
            continue

        merge_component_maps(result_map, fact_file_name, document_component_map)
        parsed_xml_count += 1

    if output_json_path is None:
        input_name = os.path.splitext(os.path.basename(absolute_input_path))[0]
        output_json_path = os.path.join(base_dir, f"{input_name}_compe_plugs.json")

    grouped_result_map = group_same_component_sources(result_map)

    absolute_output_path = os.path.abspath(output_json_path)
    with open(absolute_output_path, "w", encoding="utf-8") as output_file:
        json.dump(grouped_result_map, output_file, ensure_ascii=False, indent=2)

    summary = {
        "factFileNameCount": len(fact_file_names),
        "parsedXmlCount": parsed_xml_count,
        "componentCount": len(result_map),
        "componentSourceCount": sum(len(source_map) for source_map in result_map.values()),
        "componentGroupCount": sum(len(group_items) for group_items in grouped_result_map.values()),
        "missingXmlFiles": missing_xml_files,
        "parseErrorFiles": parse_error_files,
    }

    return absolute_output_path, summary


# 中文註解：GUI 主程式，提供使用者選擇 JSON、執行解析與查看統計日誌。
class CompePlugExtractorApp:
    """元件插頭解析工具的 GUI 應用程式。"""

    # 中文註解：初始化視窗與所有互動元件；輸入為 tkinter 根視窗，無回傳值。
    def __init__(self, root_window):
        self.root_window = root_window
        self.root_window.title("Document 元件插頭解析工具")
        self.root_window.geometry("860x580")

        self.input_json_path_var = tk.StringVar()
        self.output_json_path_var = tk.StringVar()

        path_frame = tk.Frame(self.root_window, padx=10, pady=10)
        path_frame.pack(fill=tk.X)

        tk.Label(path_frame, text="輸入 JSON：").grid(row=0, column=0, sticky="w")
        input_entry = tk.Entry(path_frame, textvariable=self.input_json_path_var, width=90)
        input_entry.grid(row=0, column=1, sticky="ew", padx=(6, 6))
        tk.Button(path_frame, text="瀏覽...", command=self.select_input_json).grid(row=0, column=2)

        tk.Label(path_frame, text="輸出 JSON：").grid(row=1, column=0, sticky="w", pady=(8, 0))
        output_entry = tk.Entry(path_frame, textvariable=self.output_json_path_var, width=90)
        output_entry.grid(row=1, column=1, sticky="ew", padx=(6, 6), pady=(8, 0))
        tk.Button(path_frame, text="另存...", command=self.select_output_json).grid(row=1, column=2, pady=(8, 0))

        path_frame.columnconfigure(1, weight=1)

        action_frame = tk.Frame(self.root_window, padx=10)
        action_frame.pack(fill=tk.X)

        run_button = tk.Button(
            action_frame,
            text="開始解析",
            command=self.run_extract,
            bg="#1565C0",
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

    # 中文註解：讓使用者選擇 parse_ssp_xml_gui.py 產出的 JSON，並自動帶入預設輸出路徑。
    def select_input_json(self):
        """開啟檔案選擇器，更新輸入 JSON 路徑。"""
        selected_path = filedialog.askopenfilename(
            title="選擇 parse_ssp_xml_gui.py 輸出的 JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not selected_path:
            return

        self.input_json_path_var.set(selected_path)
        input_name = os.path.splitext(os.path.basename(selected_path))[0]
        default_output_path = os.path.join(os.path.dirname(selected_path), f"{input_name}_compe_plugs.json")
        self.output_json_path_var.set(default_output_path)

    # 中文註解：讓使用者指定輸出 JSON 路徑；若留空則會使用程式預設命名。
    def select_output_json(self):
        """開啟另存對話框，更新輸出 JSON 路徑。"""
        selected_path = filedialog.asksaveasfilename(
            title="選擇輸出 JSON 位置",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if selected_path:
            self.output_json_path_var.set(selected_path)

    # 中文註解：將訊息附加到畫面日誌，讓使用者知道目前處理狀態。
    def append_log(self, message):
        """新增一行日誌文字到 GUI 顯示區。"""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    # 中文註解：GUI 按鈕事件，負責驗證輸入、呼叫解析流程並呈現統計結果。
    def run_extract(self):
        """執行元件插頭解析流程。"""
        self.log_text.delete("1.0", tk.END)
        input_json_path = self.input_json_path_var.get().strip()
        output_json_path = self.output_json_path_var.get().strip() or None

        if not input_json_path:
            messagebox.showwarning("提示", "請先選擇輸入 JSON 檔案")
            return

        self.append_log(f"開始處理：{input_json_path}")
        self.append_log("-" * 70)

        try:
            saved_output_path, summary = extract_compe_plugs(input_json_path, output_json_path)
        except Exception as exc:  # pylint: disable=broad-except
            messagebox.showerror("執行錯誤", str(exc))
            self.append_log(f"錯誤：{exc}")
            return

        self.append_log(f"FactFileName 筆數：{summary['factFileNameCount']}")
        self.append_log(f"成功解析 XML 筆數：{summary['parsedXmlCount']}")
        self.append_log(f"輸出元件 Number 筆數：{summary['componentCount']}")
        self.append_log(f"元件來源分組筆數：{summary['componentSourceCount']}")
        self.append_log(f"合併後內容分組筆數：{summary['componentGroupCount']}")
        self.append_log(f"缺少 XML 筆數：{len(summary['missingXmlFiles'])}")
        self.append_log(f"XML 解析錯誤筆數：{len(summary['parseErrorFiles'])}")

        if summary["missingXmlFiles"]:
            self.append_log("")
            self.append_log("缺少的 XML：")
            for missing_path in summary["missingXmlFiles"][:20]:
                self.append_log(f"- {missing_path}")
            if len(summary["missingXmlFiles"]) > 20:
                self.append_log(f"...另有 {len(summary['missingXmlFiles']) - 20} 筆")

        if summary["parseErrorFiles"]:
            self.append_log("")
            self.append_log("解析錯誤的 XML：")
            for error_item in summary["parseErrorFiles"][:20]:
                self.append_log(f"- {error_item['path']}：{error_item['error']}")
            if len(summary["parseErrorFiles"]) > 20:
                self.append_log(f"...另有 {len(summary['parseErrorFiles']) - 20} 筆")

        self.append_log("-" * 70)
        self.append_log(f"輸出 JSON：{saved_output_path}")
        self.append_log("完成")

        messagebox.showinfo("完成", f"解析完成，已輸出：\n{saved_output_path}")


# 中文註解：建立命令列參數，讓程式可用 GUI 或 CLI 兩種方式獨立執行。
def parse_args(argv):
    """解析命令列參數；輸入為 argv 清單，輸出為 argparse 命名空間。"""
    argument_parser = argparse.ArgumentParser(
        description="依 parse_ssp_xml_gui.py 輸出的 JSON 解析 Document XML 的 CompeData 與 PlugData。"
    )
    argument_parser.add_argument("input_json", nargs="?", help="parse_ssp_xml_gui.py 輸出的 JSON 檔案路徑")
    argument_parser.add_argument("-o", "--output", help="輸出 JSON 檔案路徑，未指定時會自動命名")
    return argument_parser.parse_args(argv)


# 中文註解：程式入口；有命令列輸入時直接執行，沒有輸入時啟動 GUI。
def main(argv=None):
    """主程式入口；依參數決定執行 CLI 或 GUI 模式。"""
    args = parse_args(sys.argv[1:] if argv is None else argv)

    if args.input_json:
        output_path, summary = extract_compe_plugs(args.input_json, args.output)
        print(f"輸出 JSON：{output_path}")
        print(f"FactFileName 筆數：{summary['factFileNameCount']}")
        print(f"成功解析 XML 筆數：{summary['parsedXmlCount']}")
        print(f"輸出元件 Number 筆數：{summary['componentCount']}")
        print(f"元件來源分組筆數：{summary['componentSourceCount']}")
        print(f"合併後內容分組筆數：{summary['componentGroupCount']}")
        print(f"缺少 XML 筆數：{len(summary['missingXmlFiles'])}")
        print(f"XML 解析錯誤筆數：{len(summary['parseErrorFiles'])}")
        return

    root_window = tk.Tk()
    CompePlugExtractorApp(root_window)
    root_window.mainloop()


if __name__ == "__main__":
    main()




