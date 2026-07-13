# 測試必要前置轉檔 Python 工具

此資料夾放的是 `ssp_json_tabs.html` 測試前需要用到的轉檔、輔助整理與檢視工具。

## 建議執行方式

一般測試前建議直接執行整合工具：

```powershell
python run_ssp_json_prepare_gui.py
```

此工具只需要選擇：

- `SSP 主 XML`
- `輸出資料夾`

執行後會自動產生 `ssp_json_tabs.html` 需要的主要 JSON 與輔助 JSON。

## 整合工具輸出檔案

`run_ssp_json_prepare_gui.py` 會輸出下列檔案到指定輸出資料夾：

- `<主XML檔名>_data.json`：主資料 JSON，內容來自 `parse_ssp_xml_gui.py` 的解析結果。
- `<主XML檔名>_xml_document_use.json`：XMLDocumentUse 圖片對照資料。
- `<主XML檔名>_document_index.json`：`explorer.html` 可用的文件索引資料。
- `<主XML檔名>_compe_plugs.json`：元件與插頭對照資料。

## 工具用途與執行指令

### run_ssp_json_prepare_gui.py

用途：整合必要前置轉檔流程，一次產生主 JSON、XMLDocumentUse、Document Index、Compe Plugs 四份 JSON。

執行指令：

```powershell
python run_ssp_json_prepare_gui.py
```

### parse_ssp_xml_gui.py

用途：解析 SSP 主 XML，產生 `ssp_json_tabs.html` 主要載入的 `<主XML檔名>_data.json`。

執行指令：

```powershell
python parse_ssp_xml_gui.py
```

### parse_xml_document_use_gui.py

用途：從 SSP 主 XML 的 `PictureList` 解析 `PictureType = XMLDocumentUse` 的圖片對照資料，產生 `_xml_document_use.json`。

執行指令：

```powershell
python parse_xml_document_use_gui.py
```

### build_explorer_index_gui.py

用途：從 SSP 主 XML 的 `XmlDocumentList` 建立文件索引 JSON，供 `explorer.html` 使用，產生 `_document_index.json`。

執行指令：

```powershell
python build_explorer_index_gui.py
```

### extract_compe_plugs_gui.py

用途：依主 JSON 的 `ProjectList.FactFileName` 讀取同層 `Document` 資料夾中的 XML，整理元件與插頭對照資料，產生 `_compe_plugs.json`。

執行指令：

```powershell
python extract_compe_plugs_gui.py
```

### parse_document_refs_gui.py

用途：解析 SSP 主 XML 的文件引用資料，輸出以 `Name_CN` 為 key 的文件參照 JSON。

執行指令：

```powershell
python parse_document_refs_gui.py
```

### move_json_refs_gui.py

用途：依 JSON 清單複製 `Picture/Site`、`Picture/Pin`、`Document` 內指定檔案到輸出資料夾的 `parse` 子目錄。

執行指令：

```powershell
python move_json_refs_gui.py
```

### ssp_json_viewer.py

用途：用 GUI 檢視 `parse_ssp_xml_gui.py` 產出的 SSP JSON，並輔助查看專案資訊、Document 文件與 Site / Pin 圖片。

執行指令：

```powershell
python ssp_json_viewer.py
```

## 注意事項

- 建議優先使用 `run_ssp_json_prepare_gui.py`，可減少手動執行多支工具的步驟。
- `run_ssp_json_prepare_gui.py` 會讀取 SSP 主 XML 同層的 `Document` 資料夾來產生 `_compe_plugs.json`。
- `run_ssp_json_prepare_gui.py` 不會執行 `build_explorer_index_gui.py` 中的文件 XML 複製功能，只會產生 `_document_index.json`。
- 若單獨執行各工具，請確認輸入檔與同層資料夾結構仍符合原始 SSP 資料夾規則。
