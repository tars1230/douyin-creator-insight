import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import runtime_env  # noqa: E402
from asr import transcribe_video_cloud, transcribe_video_local, transcribe_videos  # noqa: E402
from browser_collector import default_profile_dir  # noqa: E402
from schemas import Transcript, TranscriptStatus, Video  # noqa: E402


class RuntimeEnvTests(unittest.TestCase):
    def setUp(self):
        self._saved_env = {
            key: os.environ.get(key)
            for key in runtime_env.RUNTIME_ENV_KEYS
        }
        for key in runtime_env.RUNTIME_ENV_KEYS:
            os.environ.pop(key, None)
        self._saved_runtime_files = runtime_env.RUNTIME_ENV_FILES
        runtime_env.reset_runtime_env_cache()

    def tearDown(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        runtime_env.RUNTIME_ENV_FILES = self._saved_runtime_files
        runtime_env.reset_runtime_env_cache()

    def test_loader_fills_missing_keys_without_overwriting_existing_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "DASHSCOPE_API_KEY=from-file\nDOUYIN_BROWSER_PROFILE=/tmp/profile-from-file\n",
                encoding="utf-8",
            )
            os.environ["DASHSCOPE_API_KEY"] = "from-process"
            os.environ.pop("DOUYIN_BROWSER_PROFILE", None)

            loaded = runtime_env.ensure_runtime_env(candidate_files=[env_file])

            self.assertEqual(os.environ["DASHSCOPE_API_KEY"], "from-process")
            self.assertEqual(os.environ["DOUYIN_BROWSER_PROFILE"], "/tmp/profile-from-file")
            self.assertEqual(loaded, [env_file])

    def test_empty_values_are_ignored_not_used_to_disable_existing_env(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text("DASHSCOPE_API_KEY=\n", encoding="utf-8")
            os.environ["DASHSCOPE_API_KEY"] = "from-process"

            loaded = runtime_env.ensure_runtime_env(candidate_files=[env_file])

            self.assertEqual(os.environ["DASHSCOPE_API_KEY"], "from-process")
            self.assertEqual(loaded, [])

    def test_unquoted_inline_comments_are_removed_but_quoted_hashes_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                'DASHSCOPE_API_KEY=fixture-key # comment\nSILICONFLOW_API_KEY="value # literal"\n',
                encoding="utf-8",
            )

            runtime_env.ensure_runtime_env(candidate_files=[env_file])

            self.assertEqual(os.environ["DASHSCOPE_API_KEY"], "fixture-key")
            self.assertEqual(os.environ["SILICONFLOW_API_KEY"], "value # literal")

    def test_transcribe_videos_picks_up_cloud_key_from_runtime_env_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text("DASHSCOPE_API_KEY=fixture-key\n", encoding="utf-8")
            old_files = runtime_env.RUNTIME_ENV_FILES
            runtime_env.RUNTIME_ENV_FILES = (env_file,)
            os.environ.pop("DASHSCOPE_API_KEY", None)
            try:
                def cloud(video):
                    self.assertEqual(os.environ.get("DASHSCOPE_API_KEY"), "fixture-key")
                    return Transcript(video.aweme_id, TranscriptStatus.SUCCESS, "ok", actor_used="cloud-fixture")

                def local(video):
                    raise AssertionError("local fallback should not run when cloud succeeds")

                transcripts, source = transcribe_videos(
                    [Video(aweme_id="fixture", video_url="https://media.example.test/1.mp4")],
                    cloud_transcriber=cloud,
                    local_transcriber=local,
                )
            finally:
                runtime_env.RUNTIME_ENV_FILES = old_files
            self.assertEqual(transcripts[0].status, TranscriptStatus.SUCCESS)
            self.assertIn("cloud-fixture", source)

    def test_direct_cloud_transcriber_loads_runtime_env_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text("DASHSCOPE_API_KEY=fixture-key\n", encoding="utf-8")
            old_files = runtime_env.RUNTIME_ENV_FILES
            runtime_env.RUNTIME_ENV_FILES = (env_file,)
            os.environ.pop("DASHSCOPE_API_KEY", None)
            try:
                transcript = transcribe_video_cloud(Video(aweme_id="fixture"))
            finally:
                runtime_env.RUNTIME_ENV_FILES = old_files
            self.assertEqual(os.environ.get("DASHSCOPE_API_KEY"), "fixture-key")
            self.assertEqual(transcript.status, TranscriptStatus.FAILED)
            self.assertIn("no public media URL", transcript.err_msg or "")

    def test_direct_local_transcriber_loads_runtime_env_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text("DOUYIN_WHISPER_MODEL=tiny\n", encoding="utf-8")
            old_files = runtime_env.RUNTIME_ENV_FILES
            runtime_env.RUNTIME_ENV_FILES = (env_file,)
            os.environ.pop("DOUYIN_WHISPER_MODEL", None)
            try:
                transcript = transcribe_video_local(Video(aweme_id="fixture"))
            finally:
                runtime_env.RUNTIME_ENV_FILES = old_files
            self.assertEqual(os.environ.get("DOUYIN_WHISPER_MODEL"), "tiny")
            self.assertEqual(transcript.status, TranscriptStatus.FAILED)
            self.assertIn("no public media URL", transcript.err_msg or "")

    def test_default_profile_dir_reads_browser_profile_from_runtime_env_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            profile_dir = Path(temp_dir) / "browser-profile"
            env_file.write_text(f"DOUYIN_BROWSER_PROFILE={profile_dir}\n", encoding="utf-8")
            old_files = runtime_env.RUNTIME_ENV_FILES
            runtime_env.RUNTIME_ENV_FILES = (env_file,)
            os.environ.pop("DOUYIN_BROWSER_PROFILE", None)
            try:
                resolved = default_profile_dir()
            finally:
                runtime_env.RUNTIME_ENV_FILES = old_files
            self.assertEqual(resolved, profile_dir)


if __name__ == "__main__":
    unittest.main()
