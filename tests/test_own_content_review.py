import json
import gc
import tempfile
import unittest
from pathlib import Path

from backend_app.modules.own_content_review import connectors, repository, xiaohongshu_repository


class OwnContentReviewTests(unittest.TestCase):
    def test_douyin_private_metrics_are_grouped_without_invention(self):
        rows = connectors._normalize_douyin_rows([
            {
                "video_id": "item-1",
                "title": "测试作品",
                "source": "browser_detail",
                "raw_metric_json": json.dumps({
                    "粉丝播放占比": "0.15%",
                    "非粉丝播放占比（按平台粉丝占比反算）": "99.85%",
                    "作品带来的主页访问": "102",
                    "涨粉率": "0.04%",
                }, ensure_ascii=False),
            }
        ])

        sections = {section["label"]: section["items"] for section in rows[0]["official_metric_sections"]}
        self.assertEqual(
            ["粉丝播放占比", "非粉丝播放占比（按平台粉丝占比反算）", "涨粉率"],
            [item["label"] for item in sections["观众与粉丝"]],
        )
        self.assertEqual("作品带来的主页访问", sections["流量来源"][0]["label"])

    def test_douyin_account_snapshot_round_trips(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "review.sqlite"
            account_id = repository.upsert_account(db_path, "抖音创作者中心")
            repository.save_account_snapshot(db_path, account_id, {
                "period": "7d",
                "captured_at": "2026-09-03T09:00:00+00:00",
                "traffic_sources": [{"label": "作品搜索", "value": "4939"}],
                "fan_metrics": [{"label": "总粉丝量", "value": 37}],
                "audience_profile": [],
                "audience_profile_available": False,
                "audience_profile_note": "抖音当前未向该账号开放用户画像数据。",
            })

            snapshot = repository.get_latest_account_snapshot(db_path)
            self.assertEqual("抖音创作者中心", snapshot["account_name"])
            self.assertEqual("作品搜索", snapshot["traffic_sources"][0]["label"])
            self.assertEqual(37, snapshot["fan_metrics"][0]["value"])
            self.assertFalse(snapshot["audience_profile_available"])
            del snapshot
            gc.collect()

    def test_xiaohongshu_videos_default_to_latest_synced_account(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "review.sqlite"
            older = xiaohongshu_repository.upsert_account(db_path, "旧账号")
            newer = xiaohongshu_repository.upsert_account(db_path, "当前账号")
            xiaohongshu_repository.save_import(
                db_path, [{"title": "旧作品", "video_url": "https://xhs/old"}],
                "旧账号", lambda item: item["video_url"],
            )
            xiaohongshu_repository.save_import(
                db_path, [{"title": "新作品", "video_url": "https://xhs/new"}],
                "当前账号", lambda item: item["video_url"],
            )
            xiaohongshu_repository.save_account_snapshot(db_path, older, [], [])
            xiaohongshu_repository.save_account_snapshot(db_path, newer, [], [])
            videos = xiaohongshu_repository.list_videos(db_path)
            self.assertEqual(["当前账号"], [item["account_name"] for item in videos])
            self.assertEqual(["新作品"], [item["title"] for item in videos])

    def test_xiaohongshu_videos_without_current_snapshot_are_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "review.sqlite"
            xiaohongshu_repository.save_import(
                db_path, [{"title": "历史作品", "video_url": "https://xhs/history"}],
                "历史账号", lambda item: item["video_url"],
            )
            self.assertEqual([], xiaohongshu_repository.list_videos(db_path))

    def test_xiaohongshu_sync_prefers_profile_nickname(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "review.sqlite"
            original_run = connectors._run
            original_optional = connectors._run_optional
            try:
                connectors._run = lambda command, cwd=None, timeout=180: '[{"id":"n1","title":"作品","url":"https://xhs/n1"}]'
                connectors._run_optional = lambda command, cwd=None, timeout=180: (
                    ([{"field": "Name", "value": "真实昵称"}], None)
                    if "creator-profile" in command else ([], None)
                )
                result = connectors.sync_xiaohongshu(db_path, "UI默认名称", limit=20)
                self.assertEqual("真实昵称", xiaohongshu_repository.get_latest_account_snapshot(db_path)["account_name"])
                self.assertEqual("真实昵称", xiaohongshu_repository.list_videos(db_path)[0]["account_name"])
                self.assertEqual(result["account_id"], xiaohongshu_repository.get_latest_account_snapshot(db_path)["account_id"])
            finally:
                connectors._run = original_run
                connectors._run_optional = original_optional


if __name__ == "__main__":
    unittest.main()
