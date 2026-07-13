from __future__ import annotations

import json
import mimetypes
import os
import socket
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


# 中文註解：工具根目錄固定為 server.py 所在資料夾；輸入是目前檔案位置，輸出為後續所有相對路徑的基準。
ROOT_DIR = Path(__file__).resolve().parent

# 中文註解：資料來源資料夾固定為 localTool/data；前端與 API 都只讀這裡，避免硬編碼使用者電腦路徑。
DATA_DIR = ROOT_DIR / "data"

# 中文註解：預設從 8000 開始尋找可用 port；若被占用，會往後找其他 port。
DEFAULT_PORT = 8000
MAX_PORT_ATTEMPTS = 50


# 中文註解：把 Windows 路徑轉成瀏覽器與 JSON 都容易處理的斜線相對路徑；輸入為檔案 Path，輸出為 data 內相對路徑。
def to_data_relative_path(file_path: Path) -> str:
    return file_path.relative_to(DATA_DIR).as_posix()


# 中文註解：列出 data 內所有檔案；輸出包含所有檔案與 JSON 子清單，讓前端能索引圖片/XML 並逐一載入 JSON。
def build_files_payload() -> dict:
    if not DATA_DIR.exists():
        return {
            "ok": False,
            "error": "data 資料夾不存在，請在 localTool 底下建立 data 資料夾並放入 JSON。",
            "dataExists": False,
            "files": [],
            "jsonFiles": [],
        }

    if not DATA_DIR.is_dir():
        return {
            "ok": False,
            "error": "data 路徑存在但不是資料夾，請確認 localTool/data。",
            "dataExists": False,
            "files": [],
            "jsonFiles": [],
        }

    files = []
    for file_path in sorted(DATA_DIR.rglob("*"), key=lambda path: path.as_posix().lower()):
        if not file_path.is_file():
            continue

        relative_path = to_data_relative_path(file_path)
        files.append(
            {
                "name": file_path.name,
                "relativePath": relative_path,
                "url": f"/data/{urllib.parse.quote(relative_path, safe='/')}",
                "size": file_path.stat().st_size,
            }
        )

    json_files = [file_info for file_info in files if file_info["name"].lower().endswith(".json")]
    return {
        "ok": True,
        "dataExists": True,
        "files": files,
        "jsonFiles": json_files,
        "jsonCount": len(json_files),
    }


# 中文註解：尋找可使用的本機 port；輸入起始 port，輸出第一個成功綁定的 port，避免 8000 被占用時直接失敗。
def find_available_port(start_port: int) -> int:
    for offset in range(MAX_PORT_ATTEMPTS):
        port = start_port + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port

    raise OSError(f"找不到可用 port，已嘗試 {start_port} 到 {start_port + MAX_PORT_ATTEMPTS - 1}。")


# 中文註解：確認要求的檔案仍在指定根目錄內；輸入根目錄與 URL 路徑，輸出安全解析後的 Path。
def resolve_safe_path(base_dir: Path, url_path: str) -> Path | None:
    decoded_path = urllib.parse.unquote(url_path).replace("\\", "/").lstrip("/")
    candidate_path = (base_dir / decoded_path).resolve()
    try:
        candidate_path.relative_to(base_dir.resolve())
    except ValueError:
        return None
    return candidate_path


class LocalToolRequestHandler(BaseHTTPRequestHandler):
    # 中文註解：回傳 JSON API；輸入為 Python 物件與狀態碼，輸出為 UTF-8 JSON HTTP 回應。
    def send_json(self, payload: dict, status_code: int = 200) -> None:
        response_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    # 中文註解：回傳純文字錯誤；輸入為狀態碼與中文內容，輸出為 UTF-8 body，避免 send_error 的 latin-1 狀態列限制。
    def send_plain_error(self, status_code: int, reason: str, message: str) -> None:
        response_body = message.encode("utf-8")
        self.send_response(status_code, reason)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    # 中文註解：回傳沒有內容的成功狀態；輸入為狀態碼，輸出為空 body，供 favicon 這類非必要請求使用。
    def send_empty_response(self, status_code: int = 204) -> None:
        self.send_response(status_code)
        self.send_header("Content-Length", "0")
        self.end_headers()

    # 中文註解：回傳靜態檔案；輸入為檔案路徑，輸出為瀏覽器可讀的檔案內容。
    def send_file(self, file_path: Path) -> None:
        if not file_path.exists() or not file_path.is_file():
            self.send_plain_error(404, "Not Found", "找不到檔案")
            return

        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        file_bytes = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(file_bytes)))
        self.end_headers()
        self.wfile.write(file_bytes)

    # 中文註解：處理 GET 要求；依路徑分流到 /api/files、/data 靜態檔或 index.html。
    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        request_path = parsed_url.path

        if request_path == "/api/files":
            payload = build_files_payload()
            self.send_json(payload, 200 if payload.get("ok") else 404)
            return

        if request_path == "/favicon.ico":
            self.send_empty_response()
            return

        if request_path.startswith("/data/"):
            data_path = resolve_safe_path(DATA_DIR, request_path.removeprefix("/data/"))
            if data_path is None:
                self.send_plain_error(403, "Forbidden", "不允許讀取 data 外部路徑")
                return
            self.send_file(data_path)
            return

        if request_path in ("", "/"):
            self.send_file(ROOT_DIR / "index.html")
            return

        static_path = resolve_safe_path(ROOT_DIR, request_path)
        if static_path is None:
            self.send_plain_error(403, "Forbidden", "不允許讀取工具目錄外部路徑")
            return
        self.send_file(static_path)

    # 中文註解：覆寫預設 log，讓終端輸出保留請求紀錄但避免亂碼格式過多。
    def log_message(self, format_text: str, *args: object) -> None:
        sys.stderr.write("[localTool] " + format_text % args + "\n")


# 中文註解：啟動 HTTP Server 並自動開啟瀏覽器；輸入為可用 port，輸出為持續執行的本機服務。
def run_server(port: int) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", port), LocalToolRequestHandler)
    url = f"http://localhost:{port}/"
    print(f"localTool 已啟動：{url}")
    print(f"資料夾：{DATA_DIR}")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    server.serve_forever()


if __name__ == "__main__":
    os.chdir(ROOT_DIR)
    try:
        selected_port = find_available_port(DEFAULT_PORT)
        run_server(selected_port)
    except OSError as error:
        print(f"啟動失敗：{error}")
        input("按 Enter 結束...")
        raise
