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


def _run_optional(command: list[str], cwd: Path | None = None, timeout: int = 180):
    try:
        return _extract_json(_run(command, cwd=cwd, timeout=timeout)), None
    except Exception as exc:
        return [], str(exc)


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


_DOUYIN_FIXED_RAW_LABELS = {
    "exposure_count", "play_count", "five_second_completion_rate",
    "completion_rate", "average_watch_duration_seconds", "like_count",
    "collect_count", "comment_count", "share_count", "follower_gain",
    "2s跳出率", "2秒跳出率", "封面点击率",
}


def _parse_json_object(value) -> dict:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _official_metric_section(label: str) -> str:
    text = str(label or "")
    if any(word in text for word in ("推荐", "流量", "来源", "搜索", "主页", "关注页", "同城")):
        return "流量来源"
    if any(word in text for word in ("粉丝", "非粉丝", "涨粉", "吸粉", "脱粉", "性别", "年龄", "地域", "观众")):
        return "观众与粉丝"
    return "内容表现"


def _raw_rate(raw_metrics: dict, *labels: str):
    for label in labels:
        value = raw_metrics.get(label)
        if value in (None, ""):
            continue
        text = str(value).strip().replace(",", "")
        try:
            return float(text[:-1]) / 100 if text.endswith("%") else float(text)
        except ValueError:
            continue
    return None


def _normalize_official_metrics(raw_metrics) -> list[dict]:
    sections: dict[str, list[dict]] = {}
    for raw_label, raw_value in _parse_json_object(raw_metrics).items():
        label = str(raw_label or "").strip()
        if not label or label in _DOUYIN_FIXED_RAW_LABELS or raw_value in (None, ""):
            continue
        value = str(raw_value).strip()
        section = _official_metric_section(label)
        sections.setdefault(section, []).append({"label": label, "value": value})
    order = ("流量来源", "观众与粉丝", "内容表现")
    return [
        {"label": section, "items": sections[section]}
        for section in order if sections.get(section)
    ]


def _normalize_douyin_rows(rows: list[dict]) -> list[dict]:
    merged = []
    for key, group in __import__("itertools").groupby(sorted(rows, key=lambda row: str(row.get("video_id") or row.get("title") or "")), key=lambda row: str(row.get("video_id") or row.get("title") or "")):
        group_rows = list(group)
        item = next((row for row in group_rows if row.get("source") == "browser_detail"), group_rows[0])
        raw_metrics = _parse_json_object(item.get("raw_metric_json"))
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
            "two_sec_bounce_rate": _raw_rate(raw_metrics, "2s跳出率", "2秒跳出率"),
            "cover_click_rate": _raw_rate(raw_metrics, "封面点击率"),
            "avg_play_duration": item.get("average_watch_duration_seconds"),
            "follower_delta": item.get("follower_gain"),
            "official_metric_sections": _normalize_official_metrics(raw_metrics),
            "metric_quality": item.get("quality"),
            "notes": "; ".join(filter(None, [f"video_id={item.get('video_id')}" if item.get('video_id') else None, f"source={item.get('source')}" if item.get('source') else None])),
        })
    return merged


def sync_douyin(db_path: Path, account_name: str = "抖音创作者中心", recent_limit: int = 20) -> dict:
    cli, project = _resolve_douyin_cli()
    list_sync = _extract_json(_run([cli, "sync", "--mode", "background_first"], cwd=project, timeout=240))
    detail_batches = []
    cursor = 0
    while True:
        detail = _extract_json(_run([
            cli, "details", "--recent-limit", str(recent_limit),
            "--cursor", str(cursor), "--mode", "background_first",
        ], cwd=project, timeout=300))
        detail_batches.append(detail)
        next_cursor = detail.get("next_cursor") if isinstance(detail, dict) else None
        if next_cursor is None:
            break
        cursor = int(next_cursor)
    overview = _extract_json(_run(
        [cli, "overview", "--mode", "background_first"], cwd=project, timeout=180
    ))
    binding_identity = (
        list_sync.get("account_identity") if isinstance(list_sync, dict) else None
    ) or {}
    overview_identity = (
        overview.get("account_identity") if isinstance(overview, dict) else None
    ) or {}
    account_identity = {**overview_identity, **binding_identity}
    if isinstance(overview, dict):
        overview["account_identity"] = account_identity
    with tempfile.NamedTemporaryFile(prefix="douyin-export-", suffix=".json", delete=False) as handle:
        export_path = Path(handle.name)
    try:
        _run([cli, "export", "--format", "json", "--period", "all", "--output", str(export_path)], cwd=project, timeout=120)
        payload = json.loads(export_path.read_text(encoding="utf-8"))
        rows = _normalize_douyin_rows(list(payload.get("rows") or []))
        result = douyin_repository.save_import(db_path, rows, account_name, _source_key)
        snapshot_id = douyin_repository.save_account_snapshot(
            db_path, result["account_id"], overview
        )
        failures = [
            failure
            for batch in detail_batches if isinstance(batch, dict)
            for failure in list(batch.get("failures") or [])
        ]
        warnings = []
        if failures:
            warnings.append(f"{len(failures)} 条作品暂未生成或未返回完整后台指标")
        result.update({
            "connector": "douyin-mcp",
            "synced_rows": len(rows),
            "raw_rows": len(payload.get("rows") or []),
            "account_snapshot_id": snapshot_id,
            "list_sync_status": list_sync.get("status") if isinstance(list_sync, dict) else None,
            "account_identity": account_identity,
            "detail_batch_count": len(detail_batches),
            "detail_failures": failures,
            "warnings": warnings,
        })
        return result
    finally:
        export_path.unlink(missing_ok=True)


def sync_xiaohongshu(db_path: Path, account_name: str = "我的小红书账号", limit: int = 20) -> dict:
    cli = _resolve_opencli()
    output = _run([
        cli, "xiaohongshu", "creator-notes-summary", "--limit", str(limit),
        "--timeout", "300", "-f", "json", "--window", "background",
        "--site-session", "persistent",
    ], timeout=360)
    payload = _extract_json(output)
    rows = [_normalize_xiaohongshu_summary(item) for item in list(payload or [])]
    profile, profile_error = _run_optional([
        cli, "xiaohongshu", "creator-profile", "-f", "json", "--window", "background",
        "--site-session", "persistent",
    ], timeout=120)
    stats, stats_error = _run_optional([
        cli, "xiaohongshu", "creator-stats", "--period", "thirty", "-f", "json",
        "--window", "background", "--site-session", "persistent",
    ], timeout=180)
    normalized_profile = _normalize_xiaohongshu_profile(profile)
    resolved_name = next(
        (str(item.get("value")).strip() for item in normalized_profile
         if item.get("label") == "账号名称" and str(item.get("value") or "").strip()),
        None,
    )
    effective_account_name = resolved_name or account_name
    result = xiaohongshu_repository.save_import(db_path, rows, effective_account_name, _source_key)
    snapshot_id = xiaohongshu_repository.save_account_snapshot(
        db_path, result["account_id"], normalized_profile,
        _normalize_xiaohongshu_stats(stats), period="thirty",
    )
    warnings = [message for message in (profile_error, stats_error) if message]
    result.update({
        "connector": "opencli-xiaohongshu-creator-center",
        "synced_rows": len(rows), "account_snapshot_id": snapshot_id,
        "warnings": warnings,
    })
    return result


def _value_or_none(value):
    if value in (None, "", "-", "--"):
        return None
    text = str(value).strip().replace(",", "")
    try:
        return int(float(text))
    except ValueError:
        return value


def _normalize_xiaohongshu_summary(item: dict) -> dict:
    sections = []
    traffic_items = []
    audience_items = []
    quality_items = []
    if item.get("top_source"):
        traffic_items.append({
            "label": str(item.get("top_source")),
            "value": str(item.get("top_source_pct") or "-"),
        })
    if item.get("top_interest"):
        audience_items.append({
            "label": f"兴趣：{item.get('top_interest')}",
            "value": str(item.get("top_interest_pct") or "-"),
        })
    if item.get("rise_fans") not in (None, "", "-"):
        audience_items.append({"label": "涨粉数", "value": str(item.get("rise_fans"))})
    if item.get("avg_view_time") not in (None, "", "-"):
        quality_items.append({"label": "平均观看时长", "value": str(item.get("avg_view_time"))})
    for label, items in (("观看来源", traffic_items), ("观众画像", audience_items), ("观看质量", quality_items)):
        if items:
            sections.append({"label": label, "items": items})
    return {
        "title": item.get("title") or "未命名笔记",
        "video_url": item.get("url") or "",
        "published_at": item.get("published_at") or item.get("date"),
        "play_count": _value_or_none(item.get("views")),
        "like_count": _value_or_none(item.get("likes")),
        "collect_count": _value_or_none(item.get("collects")),
        "comment_count": _value_or_none(item.get("comments")),
        "share_count": _value_or_none(item.get("shares")),
        "follower_delta": _value_or_none(item.get("rise_fans")),
        "official_metric_sections": sections,
        "metric_quality": "partial" if sections else "basic",
        "notes": f"note_id={item.get('id')}" if item.get("id") else "",
    }


def _normalize_xiaohongshu_profile(rows) -> list[dict]:
    labels = {
        "Name": "账号名称", "Followers": "粉丝数", "Following": "关注数",
        "Likes & Collects": "获赞与收藏", "Creator Level": "创作者等级",
        "Level Progress": "等级进度", "Bio": "简介",
    }
    return [
        {"label": labels.get(str(item.get("field")), str(item.get("field"))), "value": item.get("value")}
        for item in list(rows or []) if item.get("field") and item.get("value") not in (None, "")
    ]


def _normalize_xiaohongshu_stats(rows) -> list[dict]:
    result = []
    for item in list(rows or []):
        metric = str(item.get("metric") or "").strip()
        label = metric.split("(", 1)[0].strip() or metric
        trend = str(item.get("trend") or "").strip()
        values = []
        if trend and trend != "-":
            for part in trend.split("→"):
                try:
                    values.append(float(part.strip()))
                except ValueError:
                    pass
        result.append({"label": label, "total": item.get("total"), "trend": values})
    return result
