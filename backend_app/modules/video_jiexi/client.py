import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_BASE_URL = ""


class VideoJiexiError(RuntimeError):
    pass


def base_url(settings=None):
    settings = settings or {}
    return (os.environ.get("VIDEO_JIEXI_BASE_URL") or settings.get("videoJiexiBaseUrl") or DEFAULT_BASE_URL).rstrip("/")


def download_root(settings=None):
    settings = settings or {}
    configured = os.environ.get("VIDEO_JIEXI_DOWNLOAD_DIR") or settings.get("videoJiexiDownloadDir")
    return Path(configured).expanduser() if configured else None


def api_token(settings=None):
    settings = settings or {}
    return os.environ.get("VIDEO_JIEXI_API_TOKEN") or settings.get("videoJiexiApiToken") or ""


def _request(path, method="GET", payload=None, timeout=15, settings=None):
    service_url = base_url(settings)
    if not service_url:
        raise VideoJiexiError("未配置 video-jiexi 服务地址，请设置 VIDEO_JIEXI_BASE_URL")
    body = None
    headers = {"Accept": "application/json"}
    token = api_token(settings)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{service_url}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise VideoJiexiError(f"video-jiexi HTTP {exc.code}: {detail[:500]}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise VideoJiexiError(f"无法连接 video-jiexi（{service_url}）：{exc}") from exc


def health(settings=None):
    return _request("/api/health", timeout=5, settings=settings)


def inspect(url, cookie_browser="", settings=None):
    payload = {"url": url}
    if cookie_browser:
        payload["cookieBrowser"] = cookie_browser
    return _request("/api/inspect", method="POST", payload=payload, timeout=60, settings=settings)


def start_download(inspection_id, format_id=None, kind="video", settings=None):
    payload = {"inspectionId": inspection_id, "kind": kind}
    if format_id:
        payload["formatId"] = format_id
    return _request("/api/downloads", method="POST", payload=payload, timeout=30, settings=settings)


def get_task(task_id, settings=None):
    return _request(f"/api/downloads/{task_id}", timeout=15, settings=settings)


def download_file(task_id, settings=None):
    service_url = base_url(settings)
    if not service_url:
        raise VideoJiexiError("未配置 video-jiexi 服务地址，请设置 VIDEO_JIEXI_BASE_URL")
    headers = {"Accept": "*/*"}
    token = api_token(settings)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(f"{service_url}/api/downloads/{task_id}/file", headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            filename = response.headers.get_filename() or "video.mp4"
            return filename, response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise VideoJiexiError(f"video-jiexi 文件接口 HTTP {exc.code}: {detail[:500]}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise VideoJiexiError(f"无法从 video-jiexi 获取文件：{exc}") from exc


def wait_for_task(task_id, timeout=900, interval=2, settings=None):
    deadline = time.time() + timeout
    while time.time() < deadline:
        task = get_task(task_id, settings=settings)
        if task.get("state") in {"completed", "error", "cancelled"}:
            return task
        time.sleep(interval)
    raise VideoJiexiError("video-jiexi 下载任务等待超时")


def task_file_path(task, settings=None):
    filename = str(task.get("filename") or "").strip()
    if not filename:
        raise VideoJiexiError("video-jiexi 任务未返回文件名")
    kind = str(task.get("kind") or "video")
    folder = {"video": "视频", "audio": "音乐", "cover": "图文", "gallery": "图文", "collection": "图文"}.get(kind, "视频")
    root = download_root(settings)
    if root is None:
        raise VideoJiexiError("未配置共享下载目录；请让 video-jiexi 提供文件接口，或显式设置 VIDEO_JIEXI_DOWNLOAD_DIR")
    root = root.resolve()
    candidate = (root / folder / filename).resolve()
    if root != candidate and root not in candidate.parents:
        raise VideoJiexiError("video-jiexi 返回了不安全的文件路径")
    if not candidate.exists():
        raise VideoJiexiError(f"video-jiexi 文件不存在：{candidate}")
    return candidate
