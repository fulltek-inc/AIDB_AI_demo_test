# SSP JSON 本機檢視工具

此工具會在 Windows 本機啟動 HTTP Server，避免直接用 `file://` 開啟 HTML 時被瀏覽器限制 `fetch()`。

## 目錄結構

```text
localTool/
├─ index.html
├─ start.bat
├─ server.py
├─ README.md
└─ data/
   ├─ example_data.json
   ├─ example_compe_plugs.json
   └─ index.json
```

## 如何啟動

1. 將 JSON、圖片、XML 等資料放到 `data` 資料夾。
2. 雙擊 `start.bat`。
3. 工具會自動啟動本機 HTTP Server，並開啟瀏覽器。
4. 預設網址從 `http://localhost:8000/` 開始；若 8000 被占用，會自動改用下一個可用 port。

## 如何放入 JSON

- 主資料 JSON 建議使用既有流程產出的 `*_data.json`。
- 名稱對應 JSON 可放 `*_compe_plugs.json`。
- 文件索引 JSON 可放 `index.json`。
- XML 圖片對應 JSON 可放 `*_xml_document_use.json`。
- 檔名可以包含中文、空白或特殊字元。
- 圖片與文件請維持原本相對路徑，例如：

```text
data/
├─ car_data.json
├─ car_compe_plugs.json
├─ index.json
├─ Picture/
│  ├─ Site/
│  ├─ Pin/
│  └─ XmlUse/
├─ Document/
└─ Output/
   ├─ Document/
   └─ Picture/
```

## Python 檢查方式

在命令提示字元執行：

```bat
python --version
```

如果沒有結果，再試：

```bat
py --version
```

兩者都不可用時，請安裝 Python 3，並勾選 `Add python.exe to PATH`。

## 常見錯誤排除

- `data 資料夾不存在`
  - 請在 `localTool` 底下建立 `data` 資料夾。

- `資料夾內沒有 JSON`
  - 請確認 JSON 是否放在 `localTool/data` 或其子資料夾內。

- `JSON 格式錯誤`
  - 單一 JSON 解析失敗時，頁面會顯示該檔案錯誤，其他 JSON 仍會繼續載入。

- `找不到 Python`
  - 請安裝 Python 3，或確認 `python --version` / `py --version` 是否可用。

- 瀏覽器沒有自動開啟
  - 請查看命令提示字元顯示的網址，手動貼到瀏覽器開啟。
