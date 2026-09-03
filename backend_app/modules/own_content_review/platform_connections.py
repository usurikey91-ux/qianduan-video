"""Local platform login orchestration for the creator review workspace.

The workbench never receives passwords, verification codes, or cookies.  It
only starts each connector's visible, official-site login flow and records a
small in-memory progress summary for the local UI.
"""

from __future__ import annotations

import json
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import connectors
from . import repository as douyin_repository
from . import xiaohongshu_repository


SUPPORTED_PLATFORMS = {"douyin", "xiaohongshu"}
ACTIVE_PHASES = {"starting", "waiting_for_scan", "syncing"}
_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _public_job(job: dict | None) -> dict | None:
    if not job:
        return None
    return {key: value for key, value in job.items() if key not in {"thread"}}


def _set_job(platform: str, **changes) -> dict:
    with _lock:
        current = _jobs.setdefault(platform, {"platform": platform})
        current.update(changes)
        current["updatedAt"] = _now()
        return dict(current)


def _get_job(platform: str) -> dict | None:
    with _lock:
        return dict(_jobs.get(platform) or {}) or None


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
    return {}


def _run(command: list[str], *, cwd: Path | None = None, timeout: int = 30):
    completed = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    output = (completed.stdout or "").strip()
    if completed.returncode != 0:
        detail = (completed.stderr or output or "命令执行失败").strip()
        raise RuntimeError(detail[-2000:])
    return _extract_json(output)


def _stored_account(platform: str, db_path: Path) -> dict | None:
    if platform == "douyin":
        snapshot = douyin_repository.get_latest_account_snapshot(db_path)
        if not snapshot:
            return None
        identity = snapshot.get("account_identity") or {}
        return {
            "displayName": identity.get("display_name") or snapshot.get("account_name") or "抖音创作者账号",
            "stableId": identity.get("stable_id") or identity.get("account_id"),
            "lastSyncedAt": snapshot.get("captured_at"),
            "dataAvailable": True,
        }
    snapshot = xiaohongshu_repository.get_latest_account_snapshot(db_path)
    if not snapshot:
        return None
    display_name = snapshot.get("account_name") or "小红书创作者账号"
    for item in snapshot.get("profile") or []:
        if item.get("label") == "账号名称" and item.get("value"):
            display_name = str(item["value"])
            break
    return {
        "displayName": display_name,
        "stableId": None,
        "lastSyncedAt": snapshot.get("captured_at"),
        "dataAvailable": True,
    }


def _douyin_probe() -> dict:
    executable, project = connectors._resolve_douyin_cli()
    payload = _run([executable, "status"], cwd=project, timeout=20)
    compliance = payload.get("platform_compliance") or {}
    login_status = str(payload.get("login_status") or "unknown")
    return {
        "available": True,
        "state": "connected" if login_status == "logged_in" else login_status,
        "loginStatus": login_status,
        "accountBinding": payload.get("account_binding") or {},
        "profileLocked": bool((payload.get("profile_lock") or {}).get("locked")),
        "riskAcknowledged": bool(compliance.get("acknowledged")),
        "riskNotice": compliance.get("notice"),
        "termsUrl": compliance.get("terms_url"),
    }


def _xiaohongshu_probe() -> dict:
    executable = connectors._resolve_opencli()
    payload = _run([
        executable, "xiaohongshu", "whoami", "-f", "json",
        "--window", "background", "--site-session", "persistent",
    ], timeout=45)
    logged_in = bool(payload.get("logged_in"))
    return {
        "available": True,
        "state": "connected" if logged_in else "login_required",
        "loginStatus": "logged_in" if logged_in else "login_required",
        "account": ({
            "displayName": payload.get("username") or "小红书创作者账号",
            "followers": payload.get("followers"),
            "stableId": payload.get("user_id") or payload.get("id"),
        } if logged_in else None),
    }


def connection_status(platform: str, db_path: Path, *, probe: bool = True) -> dict:
    if platform not in SUPPORTED_PLATFORMS:
        raise ValueError("暂不支持该平台")
    stored = _stored_account(platform, db_path)
    job = _get_job(platform)
    if job and job.get("phase") in ACTIVE_PHASES:
        return {
            "platform": platform,
            "available": True,
            "state": job["phase"],
            "job": _public_job(job),
            "account": job.get("account") or stored,
            "storedAccount": stored,
            "localOnly": True,
        }
    if not probe:
        return {
            "platform": platform,
            "available": True,
            "state": (job or {}).get("phase") or ("local_data_available" if stored else "unknown"),
            "job": _public_job(job),
            "account": (job or {}).get("account") or stored,
            "storedAccount": stored,
            "localOnly": True,
        }
    try:
        live = _douyin_probe() if platform == "douyin" else _xiaohongshu_probe()
    except Exception as exc:
        live = {
            "available": False,
            "state": "connector_unavailable",
            "loginStatus": "unknown",
            "error": str(exc),
        }
    account = live.get("account") or (job or {}).get("account") or stored
    if live.get("state") in {"unknown", "login_required"} and stored:
        live["state"] = "login_check_required"
    return {
        "platform": platform,
        **live,
        "job": _public_job(job),
        "account": account,
        "storedAccount": stored,
        "localOnly": True,
    }


def all_connection_statuses(db_path: Path, *, probe: bool = True) -> dict:
    return {
        platform: connection_status(platform, db_path, probe=probe)
        for platform in ("douyin", "xiaohongshu")
    }


def start_login(
    platform: str,
    db_path: Path,
    *,
    acknowledged_risk: bool = False,
    auto_sync: bool = True,
    sync_limit: int = 20,
) -> dict:
    if platform not in SUPPORTED_PLATFORMS:
        raise ValueError("暂不支持该平台")
    current = _get_job(platform)
    if current and current.get("phase") in ACTIVE_PHASES:
        raise RuntimeError("该平台正在登录或同步，请勿重复启动")
    if platform == "douyin" and not acknowledged_risk:
        raise ValueError("请先阅读并确认抖音平台访问风险说明")

    job_id = uuid.uuid4().hex
    job = _set_job(
        platform,
        jobId=job_id,
        phase="starting",
        message="正在打开平台官方登录页面",
        startedAt=_now(),
        error=None,
        account=None,
    )

    def worker():
        try:
            if platform == "douyin":
                executable, project = connectors._resolve_douyin_cli()
                _run(
                    [executable, "acknowledge-platform-risk", "--yes"],
                    cwd=project,
                    timeout=20,
                )
                _set_job(
                    platform,
                    phase="waiting_for_scan",
                    message="请在打开的抖音官方窗口中扫码并完成安全验证",
                )
                login_payload = _run([
                    executable, "login", "--timeout", "300", "--poll-interval", "2",
                ], cwd=project, timeout=330)
                login_status = str(login_payload.get("login_status") or login_payload.get("status") or "")
                if login_status not in {"logged_in", "completed"} and not login_payload.get("ok"):
                    raise RuntimeError(login_payload.get("message") or "抖音登录未完成")
                account = {"displayName": "抖音创作者账号", "dataAvailable": False}
            else:
                executable = connectors._resolve_opencli()
                _set_job(
                    platform,
                    phase="waiting_for_scan",
                    message="请在打开的小红书官方窗口中扫码并完成安全验证",
                )
                login_payload = _run([
                    executable, "xiaohongshu", "login", "--timeout", "300",
                    "-f", "json", "--window", "foreground",
                    "--site-session", "persistent", "--keep-tab", "true",
                ], timeout=330)
                if not login_payload.get("logged_in"):
                    raise RuntimeError(login_payload.get("message") or "小红书登录未完成")
                account = {
                    "displayName": login_payload.get("username") or "小红书创作者账号",
                    "followers": login_payload.get("followers"),
                    "stableId": login_payload.get("user_id") or login_payload.get("id"),
                    "dataAvailable": False,
                }
            _set_job(platform, phase="syncing" if auto_sync else "connected", account=account,
                     message="登录成功，正在首次同步" if auto_sync else "登录成功")
            if auto_sync:
                if platform == "douyin":
                    result = connectors.sync_douyin(
                        db_path, account.get("displayName") or "抖音创作者中心",
                        recent_limit=sync_limit,
                    )
                    identity = result.get("account_identity") or {}
                    if identity.get("display_name"):
                        account["displayName"] = identity["display_name"]
                else:
                    connectors.sync_xiaohongshu(
                        db_path, account.get("displayName") or "我的小红书账号",
                        limit=sync_limit,
                    )
                account["dataAvailable"] = True
            _set_job(platform, phase="connected", account=account, message="账号已连接")
        except subprocess.TimeoutExpired:
            _set_job(platform, phase="expired", message="二维码或登录等待已超时，请重新发起登录",
                     error="login_timeout")
        except Exception as exc:
            _set_job(platform, phase="failed", message="登录或首次同步未完成", error=str(exc))

    thread = threading.Thread(target=worker, daemon=True, name=f"{platform}-login-{job_id[:8]}")
    with _lock:
        _jobs[platform]["thread"] = thread
    thread.start()
    return _public_job(job)

