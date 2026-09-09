import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


_CUDA_DLL_HANDLES = []


def extract_bilibili_bvid(value):
    """Extract a Bilibili BV id from a URL or pasted share text."""
    match = re.search(r"(?<![A-Za-z0-9])(BV[0-9A-Za-z]{10})(?![A-Za-z0-9])", str(value or ""))
    return match.group(1) if match else ""


def is_bilibili_video_url(value):
    text = str(value or "").lower()
    return bool(extract_bilibili_bvid(value)) or "bilibili.com/video/" in text or "b23.tv/" in text


def assemble_transcript_text(segments):
    """Join timed ASR/caption segments with readable Chinese punctuation."""
    items = [item for item in (segments or []) if str(item.get("text") or "").strip()]
    if not items:
        return ""
    punctuation = "。！？!?；;:：,，、"
    parts = []
    for index, item in enumerate(items):
        text = re.sub(r"\s+", "", str(item.get("text") or "").strip())
        if not text:
            continue
        parts.append(text)
        if index >= len(items) - 1:
            continue
        if text[-1] in punctuation:
            continue
        current_end = float(item.get("end") or 0)
        next_start = float(items[index + 1].get("start") or current_end)
        gap = max(0, next_start - current_end)
        next_text = re.sub(r"\s+", "", str(items[index + 1].get("text") or "").strip())
        sentence_starters = (
            "给大家", "大家", "这个", "那个", "如果", "但是", "不过", "而且", "所以",
            "比如", "然后", "首先", "最后", "其实", "当然", "现在", "我们", "你可以",
        )
        semantic_break = bool(next_text.startswith(sentence_starters)) and (
            text[-1] in "啊呀呢吧啦了" or len(text) >= 18
        )
        parts.append("。" if gap >= 1.0 or semantic_break else "，")
    result = "".join(parts).strip()
    if result and result[-1] not in punctuation:
        result += "。"
    return result


def _resolve_opencli():
    configured = os.environ.get("OPENCLI_PATH", "").strip()
    if configured and Path(configured).exists():
        return configured
    return shutil.which("opencli") or shutil.which("opencli.cmd")


def _extract_json_payload(text):
    decoder = json.JSONDecoder()
    for index, char in enumerate(text or ""):
        if char not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
            return value
        except json.JSONDecodeError:
            continue
    return None


def fetch_bilibili_official_subtitle(video_url, progress_callback=None, log=None):
    """Read the official timed captions through the logged-in OpenCLI browser session."""
    if not is_bilibili_video_url(video_url):
        return None
    bvid = extract_bilibili_bvid(video_url)
    cli = _resolve_opencli()
    if not bvid or not cli:
        return None
    if progress_callback:
        progress_callback(8, "正在读取 B 站官方字幕")
    command = [cli, "bilibili", "subtitle", bvid, "--window", "background",
               "--site-session", "persistent", "-f", "json"]
    try:
        completed = subprocess.run(command, capture_output=True, text=False, timeout=180)
    except Exception as exc:
        if log:
            log(f"bilibili official subtitle unavailable: {exc}")
        return None
    stdout = completed.stdout or b""
    stderr = completed.stderr or b""
    try:
        stdout_text = stdout.decode("utf-8")
    except UnicodeDecodeError:
        stdout_text = stdout.decode("gb18030", errors="replace")
    try:
        stderr_text = stderr.decode("utf-8")
    except UnicodeDecodeError:
        stderr_text = stderr.decode("gb18030", errors="replace")
    payload = _extract_json_payload(stdout_text)
    if completed.returncode != 0 or not isinstance(payload, list):
        if log:
            log(f"bilibili official subtitle unavailable: {(stderr_text or stdout_text)[-500:]}")
        return None
    segments = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        text = str(item.get("content") or item.get("text") or "").strip()
        if not text:
            continue
        def seconds(value):
            match = re.search(r"[0-9]+(?:\.[0-9]+)?", str(value or "0"))
            return round(float(match.group(0)), 3) if match else 0.0
        segments.append({"start": seconds(item.get("from") or item.get("start")),
                         "end": seconds(item.get("to") or item.get("end")),
                         "text": text})
    if not segments:
        return None
    duration = max((segment["end"] for segment in segments), default=0)
    if progress_callback:
        progress_callback(100, f"B 站官方字幕读取完成（{len(segments)} 段）")
    return {"engine": "bilibili-official-subtitle", "language": "zh",
            "duration": duration, "text": assemble_transcript_text(segments),
            "segments": segments}, "bilibili-official-subtitle"


def download_bilibili_video(video_url, work_dir, progress_callback=None, log=None):
    """Download a public Bilibili MP4 via the official playurl API, bypassing yt-dlp."""
    bvid = extract_bilibili_bvid(video_url)
    if not bvid:
        raise ValueError("不是有效的 B 站视频链接")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36",
               "Referer": "https://www.bilibili.com/"}
    def request_json(url):
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("code") != 0:
            raise RuntimeError(payload.get("message") or f"B 站接口错误 {payload.get('code')}")
        return payload.get("data") or {}
    try:
        view = request_json(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}")
        pages = view.get("pages") or []
        cid = (pages[0].get("cid") if pages else None) or view.get("cid")
        if not cid:
            raise RuntimeError("B 站视频没有可用分 P")
        play = request_json(f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=64&fnval=0&fnver=0&fourk=1")
        urls = [item.get("url") for item in (play.get("durl") or []) if item.get("url")]
        if not urls:
            raise RuntimeError("B 站播放接口没有返回可下载地址")
        target = Path(work_dir) / "source.mp4"
        if progress_callback:
            progress_callback(10, "已获取 B 站公开播放地址，正在下载媒体")
        request = urllib.request.Request(urls[0], headers=headers)
        with urllib.request.urlopen(request, timeout=180) as response, target.open("wb") as output:
            total = int(response.headers.get("Content-Length") or 0)
            downloaded = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    percent = downloaded * 100 / total if total else 50
                    progress_callback(min(99, percent), f"B 站媒体下载 {percent:.1f}%")
        if progress_callback:
            progress_callback(100, "B 站媒体下载完成")
        return target
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        if log:
            log(f"bilibili API download failed: {exc}")
        raise RuntimeError(f"B 站专用媒体下载失败：{exc}") from exc


def configure_local_cuda_runtime():
    """Reuse the CUDA runtime already installed with the local WhisperX project."""
    if os.name != "nt" or _CUDA_DLL_HANDLES:
        return
    configured_root = os.environ.get("WHISPERX_RUNTIME_ROOT")
    runtime_root = (
        Path(configured_root)
        if configured_root
        else Path(__file__).resolve().parents[4] / "视频一键制作" / ".venv-whisperx"
    )
    candidates = (
        runtime_root / "Lib" / "site-packages" / "torch" / "lib",
        runtime_root / "Lib" / "site-packages" / "ctranslate2",
    )
    existing_path = os.environ.get("PATH", "")
    available = [str(directory) for directory in candidates if directory.is_dir()]
    if available:
        os.environ["PATH"] = os.pathsep.join([*available, existing_path])
    for directory in candidates:
        if directory.is_dir():
            _CUDA_DLL_HANDLES.append(os.add_dll_directory(str(directory)))


def write_netscape_cookie_file(storage_state_path, output_path):
    data = json.loads(Path(storage_state_path).read_text(encoding="utf-8"))
    lines = ["# Netscape HTTP Cookie File"]
    for cookie in data.get("cookies") or []:
        domain = cookie.get("domain") or ".douyin.com"
        include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
        path = cookie.get("path") or "/"
        secure = "TRUE" if cookie.get("secure") else "FALSE"
        expires = int(cookie.get("expires") or 0)
        lines.append("\t".join([
            domain, include_subdomains, path, secure, str(max(expires, 0)),
            cookie.get("name") or "", cookie.get("value") or "",
        ]))
    Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def download_with_ytdlp(video_url, output_dir, cookie_file, progress_callback=None, log=None):
    from yt_dlp import YoutubeDL

    output_template = str(Path(output_dir) / "source.%(ext)s")
    ffmpeg_dir = os.environ.get("SAU_FFMPEG_DIR")

    def progress_hook(status):
        if not progress_callback:
            return
        if status.get("status") == "finished":
            progress_callback(100, "视频下载完成")
            return
        if status.get("status") != "downloading":
            return
        total = status.get("total_bytes") or status.get("total_bytes_estimate") or 0
        downloaded = status.get("downloaded_bytes") or 0
        percent = min(99.0, downloaded * 100 / total) if total else 5.0
        details = [f"下载 {percent:.1f}%"]
        speed = str(status.get("_speed_str") or "").strip()
        eta = str(status.get("_eta_str") or "").strip()
        if speed and speed != "N/A":
            details.append(speed)
        if eta and eta != "N/A":
            details.append(f"剩余 {eta}")
        progress_callback(percent, " · ".join(details))

    options = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 20,
        "retries": 2,
        "fragment_retries": 2,
        "merge_output_format": "mp4",
        "outtmpl": output_template,
        "progress_hooks": [progress_hook],
    }
    if ffmpeg_dir and Path(ffmpeg_dir).exists():
        options["ffmpeg_location"] = ffmpeg_dir
    if cookie_file:
        options["cookiefile"] = str(cookie_file)
    if log:
        log(f"yt-dlp in-process ffmpeg dir: {ffmpeg_dir or '<none>'}")
    with YoutubeDL(options) as downloader:
        downloader.extract_info(video_url, download=True)
    candidates = sorted(
        (path for path in Path(output_dir).glob("source.*") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise RuntimeError("yt-dlp 下载完成但没有找到视频文件")
    return candidates[0]


async def download_with_playwright(video_url, output_path, storage_state_path=None, progress_callback=None):
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        kwargs = {
            "viewport": {"width": 1280, "height": 900},
            "locale": "zh-CN",
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
            ),
        }
        if storage_state_path and Path(storage_state_path).exists():
            kwargs["storage_state"] = str(storage_state_path)
        context = await browser.new_context(**kwargs)
        page = await context.new_page()
        media_urls = []

        def capture_response(response):
            content_type = (response.headers.get("content-type") or "").lower()
            if "video/" in content_type or ".mp4" in response.url:
                media_urls.append(response.url)

        page.on("response", capture_response)
        if progress_callback:
            progress_callback(15, "备用下载：正在打开作品页")
        await page.goto(video_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(7000)
        current_src = await page.evaluate(
            "() => document.querySelector('video')?.currentSrc || document.querySelector('video')?.src || ''"
        )
        media_url = current_src or (media_urls[-1] if media_urls else "")
        if not media_url:
            await context.close()
            await browser.close()
            raise RuntimeError("作品页没有发现可下载的视频媒体地址")
        if progress_callback:
            progress_callback(45, "备用下载：已找到视频地址")
        response = await context.request.get(media_url, headers={"Referer": video_url}, timeout=120000)
        if not response.ok:
            await context.close()
            await browser.close()
            raise RuntimeError(f"媒体下载失败: HTTP {response.status}")
        Path(output_path).write_bytes(await response.body())
        if progress_callback:
            progress_callback(100, "备用方式下载完成")
        await context.close()
        await browser.close()
    return Path(output_path)


def download_douyin_video(video_url, work_dir, *, base_dir, latest_cookie_file, progress_callback=None, log=None):
    cookie_name = latest_cookie_file()
    storage_state = Path(base_dir) / "cookiesFile" / cookie_name if cookie_name else None
    netscape_cookie = Path(work_dir) / "cookies.txt"
    if storage_state and storage_state.exists():
        write_netscape_cookie_file(storage_state, netscape_cookie)
    try:
        if progress_callback:
            progress_callback(2, "正在使用 yt-dlp 获取视频")
        return download_with_ytdlp(
            video_url, work_dir, netscape_cookie if netscape_cookie.exists() else None,
            progress_callback=progress_callback, log=log,
        )
    except Exception as primary_error:
        fallback_path = Path(work_dir) / "source-playwright.mp4"
        try:
            if progress_callback:
                progress_callback(5, "主下载方式失败，正在切换备用方式")
            return asyncio.run(download_with_playwright(
                video_url, fallback_path, storage_state, progress_callback=progress_callback,
            ))
        except Exception as fallback_error:
            raise RuntimeError(
                f"yt-dlp: {primary_error}; Playwright: {fallback_error}"
            ) from fallback_error


def transcribe_media(media_path, progress_callback=None, log=None):
    # medium 已随“视频一键制作”环境下载到本机 Hugging Face 缓存，
    # 对中文短视频的口语、同音词和背景噪声比 base 更稳；仍可通过环境变量覆盖。
    model = os.environ.get("IDEA_RADAR_WHISPER_MODEL", "medium")
    language = "zh"
    # 本机 RTX 4050 可正常加载 medium；使用 GPU + float16 才能兼顾准确率和速度。
    device = os.environ.get("IDEA_RADAR_WHISPER_DEVICE", "cuda")
    compute_type = os.environ.get("IDEA_RADAR_WHISPER_COMPUTE_TYPE", "float16")
    media_path = Path(media_path)
    if not media_path.exists():
        raise FileNotFoundError(media_path)

    configure_local_cuda_runtime()
    try:
        from faster_whisper import WhisperModel
    except ModuleNotFoundError as exc:
        raise RuntimeError("Missing faster-whisper dependency for local transcription") from exc

    if progress_callback:
        progress_callback(0, "正在启动本地语音识别")
        progress_callback(2, f"正在加载 Whisper {model} 模型")
    if log:
        log(f"loading faster-whisper model={model} device={device} compute_type={compute_type}")
    whisper_model = WhisperModel(model, device=device, compute_type=compute_type)
    if progress_callback:
        progress_callback(5, "模型加载完成，正在读取音视频")

    segments, info = whisper_model.transcribe(
        str(media_path),
        language=language,
        vad_filter=True,
        beam_size=5,
    )
    items = []
    text_parts = []
    duration = float(getattr(info, "duration", 0) or 0)
    last_reported = -1
    for segment in segments:
        text = (segment.text or "").strip()
        if not text:
            continue
        text_parts.append(text)
        items.append({
            "start": round(float(segment.start or 0), 3),
            "end": round(float(segment.end or 0), 3),
            "text": text,
        })
        position = float(segment.end or 0)
        percent = min(99, (position / duration * 100)) if duration else 0
        if progress_callback and int(percent) > last_reported:
            last_reported = int(percent)
            progress_callback(percent, f"已识别到 {int(position)} 秒", {
                "position": round(position, 3),
                "duration": round(duration, 3),
            })

    if progress_callback:
        progress_callback(100, "视频文案识别完成")
    return {
        "engine": "faster-whisper",
        "language": getattr(info, "language", language),
        "duration": round(duration, 3),
        "text": assemble_transcript_text(items) or "".join(text_parts).strip(),
        "segments": items,
    }, model


def clean_transcript_text(text):
    value = re.sub(r"[ \t]+", " ", str(text or ""))
    value = re.sub(r"\s*\n\s*", "\n", value)
    value = re.sub(r"([。！？!?，,])\1+", r"\1", value)
    try:
        from opencc import OpenCC
        value = OpenCC("t2s").convert(value)
    except ImportError:
        pass
    return value.strip()
