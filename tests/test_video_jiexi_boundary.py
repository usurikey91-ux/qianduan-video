import io
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend_app.modules.video_jiexi import client
from backend_app.modules.video_jiexi.embedded import EmbeddedVideoJiexi


class VideoJiexiBoundaryTests(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_default_uses_embedded_not_4200(self):
        with patch.object(client.embedded_manager, "ensure", return_value="http://127.0.0.1:54321") as ensure:
            self.assertEqual(client.base_url({}), "http://127.0.0.1:54321")
            ensure.assert_called_once_with(None)

    @patch.dict(os.environ, {}, clear=True)
    def test_explicit_external_service_remains_supported(self):
        with patch.object(client.embedded_manager, "ensure") as ensure:
            self.assertEqual(client.base_url({"videoJiexiBaseUrl": "http://localhost:4200/"}), "http://localhost:4200")
            ensure.assert_not_called()

    @patch.dict(os.environ, {"DOWNLOAD_DIR": "unrelated-project"}, clear=True)
    def test_embedded_downloads_ignore_unrelated_environment(self):
        process = MagicMock()
        process.stdout = io.StringIO("Video Jiexi is running at http://127.0.0.1:54321\n")
        process.poll.return_value = None
        manager = EmbeddedVideoJiexi()
        with patch("subprocess.Popen", return_value=process) as launch:
            self.assertEqual(manager.ensure(), "http://127.0.0.1:54321")
            env = launch.call_args.kwargs["env"]
            expected = Path(__file__).resolve().parents[1] / ".runtime" / "connectors" / "video-jiexi" / "downloads"
            self.assertEqual(Path(env["DOWNLOAD_DIR"]), expected)
            self.assertEqual((env["HOST"], env["PORT"]), ("127.0.0.1", "0"))
            manager.stop()


if __name__ == "__main__":
    unittest.main()
