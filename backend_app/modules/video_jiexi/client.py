import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_BASE_URL = "http://127.0.0.1:4200"
DEFAULT_DOWNLOAD_DIR = r"D:\ai-coding\视频解析下载目录"


class VideoJiexiError(RuntimeError):
    pass


def base_url():
    return (os.environ.get("VIDEO_JIEXI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def download_root():
    return Path(os.environ.get("VIDEO_JIEXI_DOWNLOAD_DIR") or DEFAULT_DOWNLOAD_DIR)


def _request(path, method="GET", payload=None, timeout=15):
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{base_url()}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise VideoJiexiError(f"video-jiexi HTTP {exc.code}: {detail[:500]}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise VideoJiexiError(f"无法连接 video-jiexi（{base_url()}）：{exc}") from exc


def health():
    return _request("/api/health", timeout=5)


def inspect(url, cookie_browser=""):
    payload = {"url": url}
    if cookie_browser:
        payload["cookieBrowser"] = cookie_browser
    return _request("/api/inspect", method="POST", payload=payload, timeout=60)


def start_download(inspection_id, format_id=None, kind="video"):
    payload = {"inspectionId": inspection_id, "kind": kind}
    if format_id:
        payload["formatId"] = format_id
    return _request("/api/downloads", method="POST", payload=payload, timeout=30)


def get_task(task_id):
    return _request(f"/api/downloads/{task_id}", timeout=15)


def wait_for_task(task_id, timeout=900, interval=2):
    deadline = time.time() + timeout
    while time.time() < deadline:
        task = get_task(task_id)
        if task.get("state") in {"completed", "error", "cancelled"}:
            return task
        time.sleep(interval)
    raise VideoJiexiError("video-jiexi 下载任务等待超时")


def task_file_path(task):
    filename = str(task.get("filename") or "").strip()
    if not filename:
        raise VideoJiexiError("video-jiexi 任务未返回文件名")
    kind = str(task.get("kind") or "video")
    folder = {"video": "视频", "audio": "音乐", "cover": "图文", "gallery": "图文", "collection": "图文"}.get(kind, "视频")
    root = download_root().resolve()
    candidate = (root / folder / filename).resolve()
    if root != candidate and root not in candidate.parents:
        raise VideoJiexiError("video-jiexi 返回了不安全的文件路径")
    if not candidate.exists():
        raise VideoJiexiError(f"video-jiexi 文件不存在：{candidate}")
    return candidate

