import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from browser_collector import normalize_browser_item, profile_url_from_resolved_url, _merge_author_metadata, _profile_author  # noqa: E402
from asr import transcribe_video_local, transcribe_videos  # noqa: E402
from integration import probe_installation  # noqa: E402
from resolver import extract_douyin_url, parse_input_type  # noqa: E402
from run_pipeline import build_parser, load_callable, run_pipeline  # noqa: E402
from schemas import Transcript, TranscriptStatus, Video, VideoStats  # noqa: E402
from selector import select_transcript_candidates  # noqa: E402
from transcript import _parse_transcript_result  # noqa: E402


class PipelineTests(unittest.TestCase):
    @staticmethod
    def make_videos(count):
        return [
            Video(
                aweme_id=str(index),
                title=f"fixture {index}",
                create_time=1_700_000_000 + index,
                stats=VideoStats(
                    digg_count=index,
                    collect_count=count - index,
                    comment_count=index,
                    share_count=index,
                ),
                video_url=f"https://media.example.test/{index}.mp4",
            )
            for index in range(count)
        ]

    def test_adaptive_transcript_selection_uses_full_transcription_for_small_accounts(self):
        selected, plan = select_transcript_candidates(self.make_videos(30))
        self.assertEqual(len(selected), 30)
        self.assertEqual(plan["mode"], "all")

    def test_adaptive_transcript_selection_uses_top_likes_for_up_to_100_videos(self):
        selected, plan = select_transcript_candidates(self.make_videos(100))
        self.assertEqual(len(selected), 50)
        self.assertEqual(plan["target_count"], 50)
        self.assertEqual({video.aweme_id for video in selected}, {str(index) for index in range(50, 100)})

    def test_adaptive_transcript_selection_scales_and_deduplicates_large_accounts(self):
        for count, expected in ((101, 60), (300, 60), (301, 80), (800, 80), (801, 100)):
            with self.subTest(count=count):
                selected, plan = select_transcript_candidates(self.make_videos(count))
                self.assertEqual(len(selected), expected)
                self.assertEqual(len({video.aweme_id for video in selected}), expected)
                self.assertEqual(plan["mode"], "adaptive")

    def test_transcript_errors_are_not_classified_as_text(self):
        parsed = _parse_transcript_result(
            [{"id": "123", "text": "[mcporter] douyin-mcp appears offline: timed out"}],
            "fixture",
        )
        self.assertEqual(parsed[0].status.value, "failed")

    def test_cloud_is_default_and_local_only_runs_after_cloud_failure(self):
        videos = self.make_videos(2)
        cloud_calls = []
        local_calls = []

        def cloud(video):
            cloud_calls.append(video.aweme_id)
            if video.aweme_id == "0":
                return Transcript(video.aweme_id, TranscriptStatus.SUCCESS, "cloud transcript", actor_used="cloud-test")
            return Transcript(video.aweme_id, TranscriptStatus.FAILED, actor_used="cloud-test", err_msg="upstream failed")

        def local(video):
            local_calls.append(video.aweme_id)
            return Transcript(video.aweme_id, TranscriptStatus.SUCCESS, "local transcript", actor_used="local-test")

        transcripts, source = transcribe_videos(videos, cloud_transcriber=cloud, local_transcriber=local)
        self.assertEqual([item.status.value for item in transcripts], ["success", "success"])
        self.assertEqual(cloud_calls, ["0", "1"])
        self.assertEqual(local_calls, ["1"])
        self.assertIn("cloud-test", source)
        self.assertIn("local-test", source)

    def test_index_mode_never_invokes_asr_or_downloads(self):
        def should_not_run(_video):
            raise AssertionError("ASR provider must not run in index mode")

        transcripts, source = transcribe_videos(
            self.make_videos(2),
            mode="index",
            cloud_transcriber=should_not_run,
            local_transcriber=should_not_run,
        )
        self.assertEqual(source.split(" ")[0], "index_only")
        self.assertEqual([item.status.value for item in transcripts], ["skipped", "skipped"])
    def test_cli_requires_explicit_mode(self):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "run_pipeline.py"),
                "--creator",
                "https://www.douyin.com/user/MS4wFixture",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--dry-run", result.stderr)
        self.assertIn("--adapter", result.stderr)

    def test_browser_mode_accepts_profile_and_rejects_nickname_at_parser_level(self):
        parser = build_parser()
        args = parser.parse_args(["--creator", "MS4wFixture", "--browser"])
        self.assertTrue(args.browser)
        self.assertEqual(args.max_videos, 1000)
        self.assertIsNone(args.transcript_count)

    def test_share_message_url_is_extracted(self):
        message = "8- 长按复制此条消息，打开抖音搜索 https://v.douyin.com/6rA126v3USM/ 3@4.com"
        self.assertEqual(extract_douyin_url(message), "https://v.douyin.com/6rA126v3USM/")
        self.assertEqual(parse_input_type(message), "url")

    def test_browser_helpers_normalize_public_item(self):
        profile_url, sec_uid = profile_url_from_resolved_url(
            "https://www.douyin.com/user/MS4wFixture?from=share"
        )
        self.assertEqual(profile_url, "https://www.douyin.com/user/MS4wFixture")
        self.assertEqual(sec_uid, "MS4wFixture")
        normalized = normalize_browser_item({
            "aweme_id": "1234567890123456789",
            "desc": "fixture topic #workflow",
            "create_time": 1_700_000_000,
            "video": {
                "duration": 45_000,
                "cover": {"url_list": ["https://example.test/cover"]},
                "play_addr": {"url_list": ["https://media.example.test/123.mp4"]},
            },
            "statistics": {"digg_count": 10, "comment_count": 2, "share_count": 3, "collect_count": 4, "play_count": 100},
            "author": {"sec_uid": sec_uid, "nickname": "fixture"},
            "text_extra": [{"hashtag_name": "workflow"}],
        })
        self.assertEqual(normalized["id"], "1234567890123456789")
        self.assertEqual(normalized["statistics"]["collectCount"], 4)
        self.assertEqual(normalized["hashtags"], ["workflow"])
        self.assertEqual(normalized["videoUrl"], "https://media.example.test/123.mp4")
        self.assertIsNone(normalize_browser_item({"aweme_id": "invalid"}))

    def test_local_fallback_cleans_its_temporary_directory_after_failure(self):
        before = set(Path(tempfile.gettempdir()).glob("douyin-creator-asr-*"))
        transcript = transcribe_video_local(Video(aweme_id="fixture", video_url="http://127.0.0.1:1/media.mp4"))
        after = set(Path(tempfile.gettempdir()).glob("douyin-creator-asr-*"))
        self.assertEqual(transcript.status, TranscriptStatus.FAILED)
        self.assertEqual(before, after)

    def test_integration_probe_treats_favorites_as_optional(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = probe_installation(profile=Path(temp_dir) / "missing", output_dir=Path(temp_dir))
        self.assertIn(result["favorites_skill"], {"installed", "not_installed (optional)"})
        self.assertEqual(result["schedule_conflict"], "none (Creator Insight has no scheduler)")
        self.assertEqual(result["conflicts"], [])

    def test_profile_metadata_extracts_declared_count(self):
        author = _profile_author({"user_info": {"user": {"sec_uid": "MS4wFixture", "aweme_count": 9}}}, "MS4wFixture")
        self.assertEqual(author["aweme_count"], 9)

    def test_profile_metadata_prefers_matching_user_over_container(self):
        author = _profile_author(
            {
                "user": {"aweme_count": 1},
                "user_info": {
                    "user": {"sec_uid": "MS4wFixture", "aweme_count": 9, "nickname": "fixture"},
                    "extra": "container field",
                },
            },
            "MS4wFixture",
        )
        self.assertEqual(author["aweme_count"], 9)
        self.assertEqual(author["nickname"], "fixture")

    def test_profile_metadata_wins_author_merge(self):
        merged = _merge_author_metadata(
            {"aweme_count": 9, "follower_count": 100, "nickname": "profile name"},
            {"aweme_count": 1, "follower_count": 20, "nickname": "post name", "signature": "from post"},
        )
        self.assertEqual(merged["aweme_count"], 9)
        self.assertEqual(merged["follower_count"], 100)
        self.assertEqual(merged["nickname"], "profile name")
        self.assertEqual(merged["signature"], "from post")

    def test_report_json_contains_collection_manifest(self):
        def fixture_adapter(*, actor, input, wait_secs):
            del input, wait_secs
            if "profile" in actor:
                return [{"id": str(1000 + i), "text": f"fixture {i}", "duration": 30} for i in range(10)]
            return [{"id": "1000", "text": "valid transcript text", "duration": 30}]

        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_pipeline(
                creator_query="https://www.douyin.com/user/MS4wFixture",
                max_videos=10,
                transcript_count=1,
                output_dir=temp_dir,
                apify_caller=fixture_adapter,
                cloud_transcriber=lambda video: Transcript(
                    video.aweme_id,
                    TranscriptStatus.FAILED,
                    actor_used="cloud-fixture",
                    err_msg="fixture cloud failure",
                ),
                local_transcriber=lambda video: Transcript(
                    video.aweme_id,
                    TranscriptStatus.FAILED,
                    actor_used="local-fixture",
                    err_msg="fixture local failure",
                ),
            )
            payload = json.loads(Path(result["output_paths"]["json"]).read_text())
            self.assertEqual(result["status"], "degraded")
            self.assertFalse(result["transcript_quality"]["passed"])
            self.assertFalse(payload["transcript_quality"]["passed"])
            self.assertEqual(payload["collection"]["state"], "unknown")
            self.assertEqual(payload["collection"]["reconciliation"], "unavailable")

    def test_cli_dry_run_is_explicit_and_non_mutating(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "run_pipeline.py"),
                    "--creator",
                    "https://www.douyin.com/user/MS4wFixture",
                    "--dry-run",
                    "--output-dir",
                    temp_dir,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"status": "dry_run"', result.stdout)
            self.assertEqual(list(Path(temp_dir).iterdir()), [])

    def test_fixture_e2e_generates_all_formats(self):
        def fixture_adapter(*, actor, input, wait_secs):
            del input, wait_secs
            if "profile" in actor:
                return [
                    {
                        "id": str(1000 + index),
                        "text": f"fixture topic {index} #workflow",
                        "duration": 45_000,
                        "videoUrl": f"https://media.example.test/{index}.mp4",
                        "statistics": {
                            "diggCount": 100 + index,
                            "commentCount": 20 + index,
                            "shareCount": 10 + index,
                            "collectCount": 30 + index,
                            "playCount": 1000 + index,
                        },
                    }
                    for index in range(10)
                ]
            return [
                {
                    "id": str(1009 - index),
                    "text": "This fixture transcript is long enough to pass validation.",
                    "duration": 45,
                }
                for index in range(5)
            ]

        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_pipeline(
                creator_query="https://www.douyin.com/user/MS4wFixture",
                max_videos=10,
                transcript_count=5,
                output_dir=temp_dir,
                apify_caller=fixture_adapter,
                cloud_transcriber=lambda video: Transcript(
                    aweme_id=video.aweme_id,
                    status=TranscriptStatus.SUCCESS,
                    text="This fixture cloud transcript is long enough to pass validation.",
                    actor_used="cloud-fixture",
                ),
            )
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["video_count"], 10)
            self.assertEqual(result["transcript_count"], 5)
            self.assertEqual(result["transcript_candidate_count"], 5)
            self.assertEqual(set(result["output_paths"]), {"html", "json", "md"})
            for path in result["output_paths"].values():
                self.assertTrue(Path(path).is_file())
            payload = json.loads(Path(result["output_paths"]["json"]).read_text())
            self.assertEqual(len(payload["videos"]), 10)
            self.assertIn("cloud-fixture", payload["transcript_source"])
            self.assertTrue(payload["transcript_quality"]["passed"])

    def test_adapter_loader_rejects_invalid_spec(self):
        with self.assertRaises(ValueError):
            load_callable("missing_separator")


if __name__ == "__main__":
    unittest.main()
