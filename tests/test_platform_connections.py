import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend_app.modules.own_content_review import platform_connections
from backend_app.modules.own_content_review import repository


class PlatformConnectionTests(unittest.TestCase):
    def setUp(self):
        platform_connections._jobs.clear()

    def tearDown(self):
        platform_connections._jobs.clear()

    def test_stored_data_does_not_claim_live_login(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "review.sqlite"
            account_id = repository.upsert_account(db_path, "我的抖音账号")
            repository.save_account_snapshot(db_path, account_id, {
                "captured_at": "2026-09-03T09:00:00+00:00",
                "period": "7d",
            })
            with patch.object(platform_connections, "_douyin_probe", return_value={
                "available": True,
                "state": "unknown",
                "loginStatus": "unknown",
            }):
                result = platform_connections.connection_status("douyin", db_path)

            self.assertEqual("login_check_required", result["state"])
            self.assertEqual("我的抖音账号", result["account"]["displayName"])
            self.assertTrue(result["account"]["dataAvailable"])

    def test_live_xiaohongshu_identity_takes_priority(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "review.sqlite"
            with patch.object(platform_connections, "_xiaohongshu_probe", return_value={
                "available": True,
                "state": "connected",
                "loginStatus": "logged_in",
                "account": {"displayName": "真实昵称", "followers": 18},
            }):
                result = platform_connections.connection_status("xiaohongshu", db_path)

            self.assertEqual("connected", result["state"])
            self.assertEqual("真实昵称", result["account"]["displayName"])

    def test_douyin_login_requires_explicit_risk_acknowledgement(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "风险说明"):
                platform_connections.start_login(
                    "douyin", Path(directory) / "review.sqlite",
                    acknowledged_risk=False,
                )

    def test_running_job_is_returned_without_browser_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            platform_connections._set_job(
                "douyin",
                jobId="job-1",
                phase="waiting_for_scan",
                message="请扫码",
            )
            with patch.object(platform_connections, "_douyin_probe") as probe:
                result = platform_connections.connection_status(
                    "douyin", Path(directory) / "review.sqlite"
                )

            probe.assert_not_called()
            self.assertEqual("waiting_for_scan", result["state"])
            self.assertEqual("请扫码", result["job"]["message"])


if __name__ == "__main__":
    unittest.main()

