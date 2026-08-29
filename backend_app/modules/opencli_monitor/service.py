"""HTTP boundary for Sunbird's auxiliary OpenCLI Admin service."""

import json
import os
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urlparse
from urllib.request import Request, urlopen


DEFAULT_OPENCLI_ADMIN_URL = ""


class OpenCLIAdminError(RuntimeError):
    """The auxiliary monitor cannot serve the requested operation."""


def get_base_url(settings: dict[str, Any] | None = None) -> str:
    settings = settings or {}
    value = (
        os.environ.get("OPENCLI_ADMIN_BASE_URL")
        or os.environ.get("VITE_OPENCLI_ADMIN_BASE_URL")
        or settings.get("opencliAdminBaseUrl")
        or DEFAULT_OPENCLI_ADMIN_URL
    )
    return str(value).rstrip("/")


def get_api_token(settings: dict[str, Any] | None = None) -> str:
    settings = settings or {}
    return str(
        os.environ.get("OPENCLI_ADMIN_API_TOKEN")
        or settings.get("opencliAdminApiToken")
        or ""
    ).strip()


def parse_douyin_sec_uid(value: str) -> tuple[str, str]:
    text = (value or "").strip()
    if not text:
        raise ValueError("请粘贴抖音主页链接或 sec_uid")
    # 兼容抖音分享卡片复制出来的整段提示语，从文本中提取其中的链接。
    embedded_url = re.search(r"https?://[^\s<>\]\[\"']+", text)
    if embedded_url:
        text = embedded_url.group(0).rstrip(".,!?，。！？")
    if "://" not in text and "/" not in text:
        return text, f"https://www.douyin.com/user/{text}"
    if "://" not in text:
        text = f"https://{text}"
    parsed = urlparse(text)
    if not parsed.hostname or not parsed.hostname.lower().endswith("douyin.com"):
        raise ValueError("请输入 douyin.com 的主页链接")

    # 抖音分享卡片常用 v.douyin.com 短链，打开后会跳转到
    # /share/user?...&sec_uid=...。先跟随一次跳转，再从最终 URL 提取稳定 ID。
    query_sec_uid = parse_qs(parsed.query).get("sec_uid", [""])[0].strip()
    match = re.search(r"/user/([^/?#]+)", parsed.path)
    if not match and not query_sec_uid and parsed.hostname.lower().startswith("v."):
        try:
            request = Request(
                text,
                headers={"User-Agent": "Mozilla/5.0 (Sunbird benchmark monitor)"},
            )
            with urlopen(request, timeout=10) as response:
                redirected = response.geturl()
            redirected_parsed = urlparse(redirected)
            query_sec_uid = parse_qs(redirected_parsed.query).get("sec_uid", [""])[0].strip()
            match = re.search(r"/user/([^/?#]+)", redirected_parsed.path)
        except Exception as exc:
            raise ValueError("无法从抖音分享链接识别稳定账号 ID") from exc

    sec_uid = query_sec_uid or (match.group(1).strip() if match else "")
    if not sec_uid:
        raise ValueError("主页链接中缺少稳定账号 ID（sec_uid）")
    return sec_uid, f"https://www.douyin.com/user/{sec_uid}"


def parse_account_reference(platform: str, value: str) -> tuple[str, str | None]:
    """Normalize a user-supplied account reference without coupling the UI to one site.

    Douyin keeps its strict ``sec_uid`` validation for backwards compatibility. Other
    platforms accept either a profile URL or a stable account identifier; the actual
    platform adapter in OpenCLI Admin remains responsible for validating the reference.
    """
    normalized_platform = str(platform or "").strip().lower()
    if normalized_platform == "douyin":
        external_id, profile_url = parse_douyin_sec_uid(value)
        return external_id, profile_url

    text = str(value or "").strip()
    if not text:
        raise ValueError("请输入对标账号主页链接或稳定账号 ID")
    if "://" not in text:
        return text, None
    parsed = urlparse(text)
    if not parsed.hostname:
        raise ValueError("账号主页链接无效")
    path_parts = [part for part in parsed.path.split("/") if part]
    external_id = path_parts[-1] if path_parts else parsed.hostname
    if not external_id:
        raise ValueError("主页链接中缺少稳定账号 ID")
    return external_id, text


def _read_error(exc: HTTPError) -> str:
    try:
        payload = json.loads(exc.read().decode("utf-8", errors="replace"))
        return str(payload.get("detail") or payload.get("error") or payload)
    except Exception:
        return str(exc)


def _request(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
    settings: dict[str, Any] | None = None,
    timeout: int = 30,
) -> Any:
    base = get_base_url(settings)
    if not base:
        raise OpenCLIAdminError("未配置 OpenCLI Admin 地址，请设置 OPENCLI_ADMIN_BASE_URL")
    url = f"{base}{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload else None
    headers = {"Content-Type": "application/json"} if body else {}
    token = get_api_token(settings)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(
        url,
        data=body,
        method=method,
        headers=headers,
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - local URL is user-configured
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise OpenCLIAdminError(_read_error(exc)) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise OpenCLIAdminError(f"OpenCLI Admin 无法连接：{exc}") from exc
    except json.JSONDecodeError as exc:
        raise OpenCLIAdminError("OpenCLI Admin 返回了无法解析的数据") from exc

    if not result.get("success"):
        raise OpenCLIAdminError(str(result.get("error") or "OpenCLI Admin 请求失败"))
    return result.get("data")


def bind_account(
    platform: str,
    account_reference: str,
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    platform = str(platform or "").strip().lower()
    if not platform:
        raise ValueError("请选择采集平台")
    external_account_id, profile_url = parse_account_reference(platform, account_reference)
    payload = {
        "platform": platform,
        "external_account_id": external_account_id,
    }
    if profile_url:
        payload["profile_url"] = profile_url
    result = _request(
        "POST",
        "/integrations/sunbird/accounts",
        payload=payload,
        settings=settings,
    )
    return result if isinstance(result, dict) else {}


def bind_douyin_account(homepage_url: str, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compatibility wrapper for existing Douyin callers."""
    return bind_account("douyin", homepage_url, settings)


def list_accounts(
    platform: str | None = None,
    settings: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"limit": 100}
    if platform:
        query["platform"] = str(platform).strip().lower()
    result = _request(
        "GET",
        "/integrations/sunbird/accounts",
        query=query,
        settings=settings,
    )
    return result if isinstance(result, list) else []


def list_platforms(settings: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    result = _request(
        "GET",
        "/integrations/sunbird/platforms",
        settings=settings,
    )
    return result if isinstance(result, list) else []


def list_douyin_accounts(settings: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Compatibility wrapper for existing Douyin callers."""
    return list_accounts("douyin", settings)


def check_account(account_id: str, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    result = _request(
        "POST",
        f"/integrations/sunbird/accounts/{quote(str(account_id), safe='')}/check",
        settings=settings,
    )
    return result if isinstance(result, dict) else {}


def list_analysis_queue(
    settings: dict[str, Any] | None = None,
    platform: str | None = None,
) -> list[dict[str, Any]]:
    works: list[dict[str, Any]] = []
    for status in ("hot", "very_hot"):
        query = {"status": status, "limit": 100}
        if platform:
            query["platform"] = str(platform).strip().lower()
        result = _request(
            "GET",
            "/integrations/sunbird/works",
            query=query,
            settings=settings,
        )
        if isinstance(result, list):
            works.extend(item for item in result if isinstance(item, dict))
    return sorted(
        works,
        key=lambda item: (
            not bool(item.get("priority")),
            -float(item.get("relative_multiple") or 0),
        ),
    )
