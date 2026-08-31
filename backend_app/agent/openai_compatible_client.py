import json
import urllib.error
import urllib.parse
import urllib.request


SUPPORTED_AI_PROTOCOLS = {"openai-compatible", "anthropic", "gemini"}


def get_universal_ai_settings(settings=None):
    settings = settings or {}
    value = settings.get("universalAI") if isinstance(settings.get("universalAI"), dict) else None
    if value is None:
        value = settings.get("openaiCompatible") if isinstance(settings.get("openaiCompatible"), dict) else {}
    protocol = str(value.get("protocol") or "openai-compatible").strip().lower()
    if protocol not in SUPPORTED_AI_PROTOCOLS:
        protocol = "openai-compatible"
    return {
        "providerName": str(value.get("providerName") or "自定义 AI").strip() or "自定义 AI",
        "protocol": protocol,
        "baseUrl": str(value.get("baseUrl") or "").strip().rstrip("/"),
        "apiKey": str(value.get("apiKey") or "").strip(),
        "timeout": max(10, min(int(value.get("timeout") or 300), 1800)),
    }


def public_universal_ai_settings(settings=None):
    value = get_universal_ai_settings(settings)
    return {
        "providerName": value["providerName"],
        "protocol": value["protocol"],
        "baseUrl": value["baseUrl"],
        "apiKeyConfigured": bool(value["apiKey"]),
        "timeout": value["timeout"],
    }


def _endpoint(base_url, path):
    base_url = str(base_url or "").strip().rstrip("/")
    if not base_url:
        raise RuntimeError("尚未配置 AI 接口地址")
    suffix = "/" + path.lstrip("/")
    if base_url.endswith(suffix):
        return base_url
    return base_url + suffix


def _json_request(url, *, config, method="GET", payload=None, timeout=None, headers=None):
    # Some OpenAI-compatible relays put Cloudflare in front of the API and reject
    # urllib's default `Python-urllib/*` signature before the request reaches auth.
    request_headers = {
        "Accept": "application/json",
        "User-Agent": "ContentWorkbench/1.0 (Universal AI Client)",
    }
    request_headers.update(headers or {})
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout or config["timeout"]) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[-1200:]
        if exc.code == 401:
            raise RuntimeError("AI 服务鉴权失败，请检查 API Key") from exc
        if exc.code == 403:
            if "cloudflare" in detail.lower() or "browser_signature" in detail.lower():
                raise RuntimeError("AI 服务被中转站的 Cloudflare 访问策略拦截，请检查中转站安全规则") from exc
            raise RuntimeError(f"AI 服务拒绝访问（HTTP 403）：{detail}") from exc
        raise RuntimeError(f"AI 服务请求失败（HTTP {exc.code}）：{detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"无法连接 AI 服务：{exc.reason}") from exc


def openai_compatible_request(path, *, settings, method="GET", payload=None, timeout=None):
    config = get_universal_ai_settings(settings)
    headers = {}
    if config["apiKey"]:
        headers["Authorization"] = f"Bearer {config['apiKey']}"
    return _json_request(
        _endpoint(config["baseUrl"], path), config=config, method=method,
        payload=payload, timeout=timeout, headers=headers,
    )


def universal_ai_completion(messages, *, settings, model_config, timeout=None):
    config = get_universal_ai_settings(settings)
    protocol = config["protocol"]
    model = str(model_config.get("model") or "").strip()
    if protocol == "openai-compatible":
        payload = {"model": model, "stream": False, "messages": messages}
        if model_config.get("reasoningEffort"):
            payload["reasoning_effort"] = model_config["reasoningEffort"]
        if model_config.get("serviceTier"):
            payload["service_tier"] = model_config["serviceTier"]
        response = openai_compatible_request(
            "/chat/completions", method="POST", payload=payload,
            settings=settings, timeout=timeout or config["timeout"],
        )
        choices = response.get("choices") if isinstance(response, dict) else None
        return choices[0].get("message", {}).get("content") if choices else ""

    if protocol == "anthropic":
        system_parts = [item.get("content", "") for item in messages if item.get("role") == "system"]
        chat_messages = [
            item for item in messages if item.get("role") in {"user", "assistant"}
        ]
        payload = {
            "model": model,
            "max_tokens": 8192,
            "messages": chat_messages,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        response = _json_request(
            _endpoint(config["baseUrl"], "/messages"), config=config, method="POST",
            payload=payload, timeout=timeout or config["timeout"],
            headers={"x-api-key": config["apiKey"], "anthropic-version": "2023-06-01"},
        )
        content = response.get("content") if isinstance(response, dict) else []
        return "".join(
            str(item.get("text") or "") for item in (content or [])
            if isinstance(item, dict) and item.get("type") == "text"
        )

    if protocol == "gemini":
        system_parts = [item.get("content", "") for item in messages if item.get("role") == "system"]
        contents = []
        for item in messages:
            if item.get("role") not in {"user", "assistant"}:
                continue
            contents.append({
                "role": "model" if item.get("role") == "assistant" else "user",
                "parts": [{"text": str(item.get("content") or "")}],
            })
        payload = {"contents": contents, "generationConfig": {"responseMimeType": "application/json"}}
        if system_parts:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
        encoded_model = urllib.parse.quote(model, safe="-._")
        response = _json_request(
            _endpoint(config["baseUrl"], f"/models/{encoded_model}:generateContent"),
            config=config, method="POST", payload=payload,
            timeout=timeout or config["timeout"], headers={"x-goog-api-key": config["apiKey"]},
        )
        candidates = response.get("candidates") if isinstance(response, dict) else None
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        return "".join(str(item.get("text") or "") for item in parts if isinstance(item, dict))

    raise RuntimeError(f"暂不支持 AI 协议：{protocol}")


# Backward-compatible names for existing imports and local settings.
get_openai_compatible_settings = get_universal_ai_settings
public_openai_compatible_settings = public_universal_ai_settings
