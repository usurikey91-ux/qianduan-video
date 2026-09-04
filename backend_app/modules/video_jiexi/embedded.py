"""Lifecycle manager for the bundled video-jiexi Node service.

The workbench exposes one HTTP port.  The parser runs as a private loopback
child process on an ephemeral port and is never advertised to users.
"""

from __future__ import annotations

import atexit
import os
import subprocess
import threading
import time
from pathlib import Path


class EmbeddedVideoJiexi:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._url = ""
        self._reader: threading.Thread | None = None

    def ensure(self, download_dir: Path | None = None) -> str:
        with self._lock:
            if self._process and self._process.poll() is None and self._url:
                return self._url

            root = Path(__file__).resolve().parents[3]
            server = root / ".runtime" / "connectors" / "video-jiexi" / "server.js"
            if not server.exists():
                raise RuntimeError(f"找不到内置视频解析服务：{server}")
            node = os.environ.get("VIDEO_JIEXI_NODE") or "node"
            env = os.environ.copy()
            env.update({"HOST": "127.0.0.1", "PORT": "0"})
            if download_dir:
                env["DOWNLOAD_DIR"] = str(download_dir)
            self._process = subprocess.Popen(
                [node, str(server)],
                cwd=str(server.parent),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            ready = threading.Event()
            output: list[str] = []

            def read_output() -> None:
                assert self._process and self._process.stdout
                for line in self._process.stdout:
                    output.append(line.rstrip())
                    if line.startswith("Video Jiexi is running at http://"):
                        self._url = line.strip().rsplit("http://", 1)[-1]
                        self._url = f"http://{self._url}"
                        ready.set()

            self._reader = threading.Thread(target=read_output, daemon=True)
            self._reader.start()
            if not ready.wait(8):
                detail = " ".join(output[-3:])
                process = self._process
                self._process = None
                self._url = ""
                if process and process.poll() is None:
                    process.kill()
                raise RuntimeError(f"内置视频解析服务启动超时。{detail}")
            return self._url

    def stop(self) -> None:
        with self._lock:
            process = self._process
            self._process = None
            self._url = ""
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()


manager = EmbeddedVideoJiexi()
atexit.register(manager.stop)
