import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import sau_backend
from backend_app.modules.benchmark import repository as benchmark_repository
from backend_app.modules.idea_radar import repository as idea_radar_repository
from backend_app.modules.idea_radar.jobs import IdeaRadarJobRegistry


class IdeaRadarPipelineTests(unittest.TestCase):
    def test_delete_video_cascade_removes_derived_records_only(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            db_path = Path(directory) / "radar.db"
            benchmark_repository.ensure_tables(db_path)
            with benchmark_repository.connect(db_path) as conn:
                account_id = conn.execute(
                    "INSERT INTO douyin_benchmark_accounts (homepage_url, nickname, status) VALUES (?, ?, 'success')",
                    ("https://www.douyin.com/user/security-test", "测试账号"),
                ).lastrowid
                video_id = conn.execute(
                    "INSERT INTO douyin_benchmark_videos (account_id, video_url, title) VALUES (?, ?, ?)",
                    (account_id, "https://v.douyin.com/security-test", "待删除作品"),
                ).lastrowid
                conn.execute(
                    "INSERT INTO douyin_benchmark_video_transcripts (video_id) VALUES (?)",
                    (video_id,),
                )
                conn.execute(
                    "INSERT INTO douyin_benchmark_video_analysis (video_id) VALUES (?)",
                    (video_id,),
                )
                conn.commit()
            deleted = benchmark_repository.delete_video_cascade(db_path, video_id)
            self.assertEqual(video_id, deleted["id"])
            self.assertIsNone(benchmark_repository.get_video(db_path, video_id))
            self.assertEqual(1, len(benchmark_repository.list_accounts(db_path)))

    def test_job_registry_reports_active_state(self):
        registry = IdeaRadarJobRegistry()
        self.assertFalse(registry.is_active(9))
        self.assertTrue(registry.start(9))
        self.assertTrue(registry.is_active(9))
        registry.finish(9)
        self.assertFalse(registry.is_active(9))

    def test_manual_uploaders_are_scoped_per_video(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            db_path = Path(directory) / "radar.db"
            first_id = benchmark_repository.add_manual_video(
                db_path, "https://v.douyin.com/First/", lambda value: value
            )
            second_id = benchmark_repository.add_manual_video(
                db_path, "https://v.douyin.com/Second/", lambda value: value
            )
            benchmark_repository.update_manual_video_details(
                db_path, first_id, uploader="作者甲"
            )
            benchmark_repository.update_manual_video_details(
                db_path, second_id, uploader="作者乙"
            )

            self.assertEqual(
                "作者甲", benchmark_repository.get_video(db_path, first_id, True)["account_name"]
            )
            self.assertEqual(
                "作者乙", benchmark_repository.get_video(db_path, second_id, True)["account_name"]
            )

    def test_replacing_manual_url_clears_failed_derived_data(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            db_path = Path(directory) / "radar.db"
            video_id = benchmark_repository.add_manual_video(
                db_path, "legacy", lambda _: "https://3.89"
            )
            idea_radar_repository.update_transcript(
                db_path, video_id, status="failed", error_message="旧错误"
            )

            replaced = benchmark_repository.replace_manual_video_url(
                db_path,
                video_id,
                "完整文本 https://v.douyin.com/New123/ 复制打开抖音",
                sau_backend.normalize_manual_video_url,
            )

            self.assertTrue(replaced)
            self.assertEqual(
                "https://v.douyin.com/New123/",
                benchmark_repository.get_video(db_path, video_id)["video_url"],
            )
            self.assertIsNone(idea_radar_repository.get_transcript(db_path, video_id))

    def test_manual_share_text_extracts_the_real_url(self):
        value = "3.89 复制打开抖音，看看作品 https://v.douyin.com/AbC123/ 其他文字"
        self.assertEqual(
            "https://v.douyin.com/AbC123/",
            sau_backend.normalize_manual_video_url(value),
        )

    def test_manual_share_text_without_url_is_rejected(self):
        self.assertEqual("", sau_backend.normalize_manual_video_url("复制打开抖音看看作品"))

    def test_legacy_malformed_share_text_is_rejected(self):
        self.assertEqual(
            "",
            sau_backend.normalize_manual_video_url(
                "https://3.89 复制打开抖音，看看【土豆的作品】"
            ),
        )

    @patch.object(sau_backend.video_jiexi_client, "base_url", return_value="")
    @patch.object(sau_backend, "download_douyin_video")
    def test_media_download_fallback_uses_wrapper_contract(self, download_video, _base_url):
        download_video.return_value = Path("source.mp4")

        result = sau_backend.download_idea_radar_media(
            "https://v.douyin.com/AbC123/", Path("work"), progress_callback=lambda *_: None
        )

        self.assertEqual(Path("source.mp4"), result)
        download_video.assert_called_once()
        self.assertEqual(
            {"progress_callback": download_video.call_args.kwargs["progress_callback"]},
            download_video.call_args.kwargs,
        )

    def test_radar_hides_stale_monitor_mirrors(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            db_path = Path(directory) / "radar.db"
            base = {
                "account": {
                    "external_account_id": "account-1",
                    "platform": "douyin",
                    "display_name": "账号",
                },
                "title": "入选作品",
                "relative_multiple": 6,
                "status": "selected",
            }
            benchmark_repository.upsert_monitor_queue_video(
                db_path, {**base, "url": "https://example.com/active"}
            )
            benchmark_repository.upsert_monitor_queue_video(
                db_path, {**base, "url": "https://example.com/stale"}
            )

            videos = benchmark_repository.list_idea_radar_videos(
                db_path,
                sau_backend.parse_metric_number,
                active_monitor_urls={"https://example.com/active"},
            )

            self.assertEqual(
                ["https://example.com/active"],
                [video["video_url"] for video in videos],
            )

    def test_legacy_three_and_five_thresholds_migrate_to_single_five_x_gate(self):
        rules = sau_backend.normalize_benchmark_monitoring_rules({
            "reference_work_count": 20,
            "hot_multiple": 3,
            "very_hot_multiple": 5,
            "interval_hours": 4,
        })
        self.assertEqual(5.0, rules["hot_multiple"])
        self.assertEqual(5.5, rules["very_hot_multiple"])

    def test_custom_single_inclusion_threshold_keeps_legacy_connector_compatible(self):
        rules = sau_backend.normalize_benchmark_monitoring_rules({
            "reference_work_count": 15,
            "hot_multiple": 6.5,
            "interval_hours": 8,
        }, inherit_global=False)
        self.assertEqual(6.5, rules["hot_multiple"])
        self.assertEqual(7.0, rules["very_hot_multiple"])
        self.assertEqual(15, rules["reference_work_count"])

    def test_prompt_uses_full_transcript_and_requires_three_adaptations(self):
        prompt = sau_backend.build_transcript_radar_prompt(
            {
                "id": 1,
                "account_name": "示例账号",
                "title": "工具标题",
                "video_url": "https://example.com/video/1",
                "like_count": "1000",
            },
            "过去只有程序员能写自动化，现在普通运营也可以先完成一个流程。",
            "普通人的 AI 机会",
        )
        self.assertIn("过去只有程序员能写自动化", prompt)
        self.assertIn("轻度改编", prompt)
        self.assertIn("中度改编", prompt)
        self.assertIn("深度改编", prompt)
        self.assertIn("complete_script", prompt)

    def test_clean_transcript_removes_repeated_punctuation(self):
        cleaned = sau_backend.clean_transcript_text("第一句。。。。\n  第二句！！！")
        self.assertEqual("第一句。\n第二句！", cleaned)

    @patch.object(sau_backend, "update_idea_radar_transcript")
    @patch.object(sau_backend, "run_codex_structured")
    @patch.object(sau_backend, "transcribe_idea_radar_media")
    @patch.object(sau_backend, "download_idea_radar_media")
    @patch.object(sau_backend, "get_idea_radar_transcript")
    @patch.object(sau_backend, "load_idea_radar_video")
    def test_pipeline_transcribes_before_analysis(
        self,
        load_video,
        get_transcript,
        download_video,
        transcribe,
        run_codex,
        update_transcript,
    ):
        load_video.return_value = {
            "id": 7,
            "account_name": "对标账号",
            "title": "标题不是正文",
            "video_url": "https://example.com/video/7",
            "like_count": "2000",
        }
        get_transcript.return_value = None
        download_video.return_value = Path("source.mp4")
        transcribe.return_value = ({
            "text": "这是视频完整正文。这里说明了具体需求和交付方式。",
            "segments": [{"start": 0, "end": 3, "text": "这是视频完整正文"}],
            "engine": "faster-whisper",
            "language": "zh",
            "duration": 3,
        }, "base")
        run_codex.return_value = {
            "viral_theme": "网页自动化机会",
            "audience_anxieties": ["重复操作浪费时间"],
            "contrarian_viewpoint": "机会在具体流程，不在通用工具。",
            "evidence_types": ["视频正文事实"],
            "migration_angles": ["为小商家交付一个后台录入流程，并找一位客户试用"],
            "recommended_titles": ["网页开始自己干活后，小生意出现了"],
            "opening_script": "很多人只看见工具。",
            "formula": "变化 × 需求 × 交付 × 验证",
            "content_breakdown": {},
        }

        sau_backend.run_idea_radar_pipeline(7, "普通人的 AI 机会")

        self.assertTrue(transcribe.called)
        analysis_prompt = run_codex.call_args.args[0]
        self.assertIn("这是视频完整正文", analysis_prompt)
        final_update = update_transcript.call_args_list[-1].kwargs
        self.assertEqual("success", final_update["status"])
        self.assertEqual("transcript", final_update["analysis_basis"])


if __name__ == "__main__":
    unittest.main()
