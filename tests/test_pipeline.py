import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from browser_collector import normalize_browser_item, profile_url_from_resolved_url  # noqa: E402
from resolver import extract_douyin_url, parse_input_type  # noqa: E402
from run_pipeline import build_parser, load_callable, run_pipeline  # noqa: E402


class PipelineTests(unittest.TestCase):
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
            "video": {"duration": 45_000, "cover": {"url_list": ["https://example.test/cover"]}},
            "statistics": {"digg_count": 10, "comment_count": 2, "share_count": 3, "collect_count": 4, "play_count": 100},
            "author": {"sec_uid": sec_uid, "nickname": "fixture"},
            "text_extra": [{"hashtag_name": "workflow"}],
        })
        self.assertEqual(normalized["id"], "1234567890123456789")
        self.assertEqual(normalized["statistics"]["collectCount"], 4)
        self.assertEqual(normalized["hashtags"], ["workflow"])
        self.assertIsNone(normalize_browser_item({"aweme_id": "invalid"}))

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

    def test_adapter_loader_rejects_invalid_spec(self):
        with self.assertRaises(ValueError):
            load_callable("missing_separator")


if __name__ == "__main__":
    unittest.main()
