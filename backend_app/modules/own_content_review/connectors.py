"""Local read-only connector adapters for creator work review.

The adapters invoke already-installed local tools only. They never receive or
return cookies/API keys; authentication remains in each tool's own profile.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import repository as douyin_repository
from . import xiaohongshu_repository


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_douyin_cli() -> tuple[str, Path]:
    configured = os.environ.get("DOUYIN_MCP_CLI_PATH", "").strip()
    project = os.environ.get("DOUYIN_MCP_PROJECT_DIR", "").strip()
    candidates = []
    if configured:
        candidates.append(Path(configured))
    if project:
        root = Path(project)
    else:
        root = _project_root().parent / "mcp-tools" / "douyin-mcp"
    candidates.extend([root / ".venv" / "Scripts" / "douyin-mcp.exe", root / ".venv311" / "Scripts" / "douyin-mcp.exe"])
    for candidate in candidates:
        if candidate.exists():
            return str(candidate), root
    executable = shutil.which("douyin-mcp") or shutil.which("douyin-mcp.exe")
    if executable:
        return executable, root
    raise RuntimeError("未找到 douyin-mcp。请设置 DOUYIN_MCP_PROJECT_DIR 或 DOUYIN_MCP_CLI_PATH。")


def _resolve_opencli() -> str:
    configured = os.environ.get("OPENCLI_PATH", "").strip()
    if configured and Path(configured).exists():
        return configured
    executable = shutil.which("opencli") or shutil.which("opencli.cmd")
    if executable:
        return executable
    raise RuntimeError("未找到 opencli。请安装 OpenCLI 或设置 OPENCLI_PATH。")


def connector_availability() -> dict:
    status = {}
    try:
        executable, _ = _resolve_douyin_cli()
        status["douyin"] = {"available": True, "executable": executable}
    except Exception as exc:
        status["douyin"] = {"available": False, "error": str(exc)}
    try:
        executable = _resolve_opencli()
        status["xiaohongshu"] = {"available": True, "executable": executable}
    except Exception as exc:
        status["xiaohongshu"] = {"available": False, "error": str(exc)}
    return status


def _run(command: list[str], cwd: Path | None = None, timeout: int = 180) -> str:
    completed = subprocess.run(
        command, cwd=str(cwd) if cwd else None, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )
    output = (completed.stdout or "").strip()
    if completed.returncode != 0:
        detail = (completed.stderr or output or "命令执行失败").strip()
        raise RuntimeError(detail[-2000:])
    return output


def _extract_json(text: str):
    decoder = json.JSONDecoder()
    for index, char in enumerate(text or ""):
        if char not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
            return value
        except json.JSONDecodeError:
            continue
    raise RuntimeError("连接器没有返回可解析的 JSON")


def _source_key(item: dict) -> str:
    url = str(item.get("video_url") or "").strip()
    if url:
        return f"url:{url}"
    digest = hashlib.sha1(
        f"{item.get('title', '')}|{item.get('published_at', '')}".encode("utf-8")
    ).hexdigest()
    return f"title_time:{digest}"


def _format_douyin_time(value) -> str | None:
    if value in (None, "", 0):
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return str(value)


def _normalize_douyin_rows(rows: list[dict]) -> list[dict]:
    merged = []
    for key, group in __import__("itertools").groupby(sorted(rows, key=lambda row: str(row.get("video_id") or row.get("title") or "")), key=lambda row: str(row.get("video_id") or row.get("title") or "")):
        group_rows = list(group)
        item = next((row for row in group_rows if row.get("source") == "browser_detail"), group_rows[0])
        merged.append({
            "title": item.get("title") or "未命名作品",
            "video_url": item.get("video_url") or "",
            "published_at": _format_douyin_time(item.get("publish_time")),
            "play_count": item.get("play_count"),
            "like_count": item.get("like_count"),
            "collect_count": item.get("collect_count"),
            "comment_count": item.get("comment_count"),
            "share_count": item.get("share_count"),
            "completion_rate": item.get("completion_rate"),
            "five_sec_completion_rate": item.get("five_second_completion_rate"),
            "avg_play_duration": item.get("average_watch_duration_seconds"),
            "follower_delta": item.get("follower_gain"),
            "notes": "; ".join(filter(None, [f"video_id={item.get('video_id')}" if item.get('video_id') else None, f"source={item.get('source')}" if item.get('source') else None])),
        })
    return merged


def sync_douyin(db_path: Path, account_name: str = "抖音创作者中心", recent_limit: int = 20) -> dict:
    cli, project = _resolve_douyin_cli()
    _run([cli, "sync", "--mode", "background_first"], cwd=project, timeout=240)
    _run([cli, "details", "--recent-limit", str(recent_limit), "--mode", "background_first"], cwd=project, timeout=300)
    with tempfile.NamedTemporaryFile(prefix="douyin-export-", suffix=".json", delete=False) as handle:
        export_path = Path(handle.name)
    try:
        _run([cli, "export", "--format", "json", "--period", "all", "--output", str(export_path)], cwd=project, timeout=120)
        payload = json.loads(export_path.read_text(encoding="utf-8"))
        rows = _normalize_douyin_rows(list(payload.get("rows") or []))
        result = douyin_repository.save_import(db_path, rows, account_name, _source_key)
        result.update({"connector": "douyin-mcp", "synced_rows": len(rows), "raw_rows": len(payload.get("rows") or [])})
        return result
    finally:
        export_path.unlink(missing_ok=True)


def sync_xiaohongshu(db_path: Path, account_name: str = "我的小红书账号", limit: int = 20) -> dict:
    cli = _resolve_opencli()
    output = _run([cli, "xiaohongshu", "creator-notes", "--limit", str(limit), "-f", "json", "--site-session", "persistent"], timeout=180)
    payload = _extract_json(output)
    rows = [{
        "title": item.get("title") or "未命名笔记",
        "video_url": item.get("url") or "",
        "published_at": item.get("date"),
        "play_count": item.get("views"),
        "like_count": item.get("likes"),
        "collect_count": item.get("collects"),
        "comment_count": item.get("comments"),
        "share_count": None,
        "notes": f"note_id={item.get('id')}" if item.get("id") else "",
    } for item in list(payload or [])]
    result = xiaohongshu_repository.save_import(db_path, rows, account_name, _source_key)
    result.update({"connector": "opencli-xiaohongshu", "synced_rows": len(rows)})
    return result
