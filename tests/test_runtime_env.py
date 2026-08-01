import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import runtime_env  # noqa: E402
import setup_config  # noqa: E402
from asr import transcribe_video_cloud, transcribe_video_local, transcribe_videos  # noqa: E402
from browser_collector import default_profile_dir  # noqa: E402
from schemas import Transcript, TranscriptStatus, Video  # noqa: E402
from setup_config import detect_existing_setup, load_setup_config, save_setup_config  # noqa: E402


class RuntimeEnvTests(unittest.TestCase):
    def setUp(self):
        self._saved_env = {
            key: os.environ.get(key)
            for key in runtime_env.RUNTIME_ENV_KEYS
        }
        for key in runtime_env.RUNTIME_ENV_KEYS:
            os.environ.pop(key, None)
        self._saved_runtime_files = runtime_env.RUNTIME_ENV_FILES
        self._saved_creator_config = os.environ.get("DOUYIN_CREATOR_CONFIG")
        runtime_env.reset_runtime_env_cache()

    def tearDown(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        runtime_env.RUNTIME_ENV_FILES = self._saved_runtime_files
        if self._saved_creator_config is None:
            os.environ.pop("DOUYIN_CREATOR_CONFIG", None)
        else:
            os.environ["DOUYIN_CREATOR_CONFIG"] = self._saved_creator_config
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

    def test_default_profile_dir_accepts_favorites_profile_env_alias(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            profile_dir = Path(temp_dir) / "favorites-profile"
            env_file.write_text(f"DOUYIN_FAVORITES_PROFILE_DIR={profile_dir}\n", encoding="utf-8")
            old_files = runtime_env.RUNTIME_ENV_FILES
            runtime_env.RUNTIME_ENV_FILES = (env_file,)
            os.environ.pop("DOUYIN_BROWSER_PROFILE", None)
            os.environ.pop("DOUYIN_FAVORITES_PROFILE_DIR", None)
            try:
                resolved = default_profile_dir()
            finally:
                runtime_env.RUNTIME_ENV_FILES = old_files
            self.assertEqual(resolved, profile_dir)

    def test_detect_existing_setup_reuses_favorites_mode_without_exposing_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "favorites.json"
            config.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "knowledge_dir": "/tmp/knowledge",
                        "ledger_path": "/tmp/ledger.sqlite3",
                        "mode": "full",
                        "transcription": {"enabled": True, "provider": "bailian", "model": "qwen3-asr-flash"},
                    }
                ),
                encoding="utf-8",
            )
            original = setup_config._favorites_config_candidates
            setup_config._favorites_config_candidates = lambda: (config,)
            try:
                detected = detect_existing_setup()
            finally:
                setup_config._favorites_config_candidates = original
            self.assertTrue(detected["favorites_skill_installed"])
            self.assertEqual(detected["favorites_transcript_mode"], "cloud")
            self.assertNotIn("knowledge_dir", detected)

    def test_detect_existing_setup_recognizes_shared_favorites_install_without_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_root = Path(temp_dir) / "douyin-favorites-to-knowledge"
            skill_root.mkdir()
            original_configs = setup_config._favorites_config_candidates
            original_roots = setup_config._favorites_skill_root_candidates
            setup_config._favorites_config_candidates = lambda: ()
            setup_config._favorites_skill_root_candidates = lambda: (skill_root,)
            try:
                detected = detect_existing_setup()
            finally:
                setup_config._favorites_config_candidates = original_configs
                setup_config._favorites_skill_root_candidates = original_roots
            self.assertTrue(detected["favorites_skill_installed"])
            self.assertIsNone(detected["favorites_transcript_mode"])

    def test_setup_config_never_stores_api_key(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "creator.json"
            save_setup_config("cloud", path=path)
            payload = load_setup_config(path)
            self.assertEqual(payload["transcript_mode"], "cloud")
            self.assertNotIn("DASHSCOPE_API_KEY", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
