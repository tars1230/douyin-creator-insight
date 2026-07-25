import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from run_pipeline import load_callable, run_pipeline  # noqa: E402


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
