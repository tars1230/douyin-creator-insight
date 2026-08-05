"""First-run configuration and coexistence helpers for Creator Insight.

Only non-secret preferences are stored. API keys remain in the process
environment, a host secret manager, or an already configured env file.
"""
from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Any

from runtime_env import ensure_runtime_env


BAILIAN_API_KEY_GUIDE_URL = "https://help.aliyun.com/zh/model-studio/get-api-key"
BAILIAN_CONSOLE_URL = "https://bailian.console.aliyun.com/cn-beijing/?tab=api"
SILICONFLOW_CONSOLE_URL = "https://cloud.siliconflow.cn/account/ak"
SILICONFLOW_DOCS_URL = "https://docs.siliconflow.cn/cn/api-reference/audio/create-audio-transcriptions"
CONFIG_ENV = "DOUYIN_CREATOR_CONFIG"
MODES = frozenset({"cloud", "local", "index"})
SECRET_LIKE_KEYS = (
    "api_key",
    "apikey",
    "token",
    "cookie",
    "password",
    "secret",
    "access_token",
    "refresh_token",
)


def default_config_path() -> Path:
    override = os.environ.get(CONFIG_ENV)
    if override:
        return Path(override).expanduser().resolve()
    system = platform.system()
    if system == "Darwin":
        root = Path.home() / "Library" / "Application Support"
    elif system == "Windows":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "douyin-creator-insight" / "config.json"


def _favorites_config_candidates() -> tuple[Path, ...]:
    home = Path.home()
    system = platform.system()
    if system == "Darwin":
        root = home / "Library" / "Application Support"
    elif system == "Windows":
        root = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    return (
        root / "douyin-favorites-to-knowledge" / "config.json",
        home / ".openclaw" / "workspace" / "skills" / "douyin-favorites-to-knowledge" / "config.json",
        home / ".shared" / "skills" / "douyin-favorites-to-knowledge" / "config.json",
        home / ".shared" / "skills" / "douyin-knowledge-base-pipeline" / "config.json",
    )


def _favorites_skill_root_candidates() -> tuple[Path, ...]:
    home = Path.home()
    return (
        home / ".shared" / "skills" / "douyin-favorites-to-knowledge",
        home / ".openclaw" / "workspace" / "skills" / "douyin-favorites-to-knowledge",
        home / ".shared" / "skills" / "douyin-knowledge-base-pipeline",
    )


def _favorites_profile_candidates() -> tuple[Path, ...]:
    home = Path.home()
    system = platform.system()
    if system == "Darwin":
        root = home / "Library" / "Application Support"
    elif system == "Windows":
        root = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
    else:
        root = Path(os.environ.get("XDG_STATE_HOME", home / ".local" / "state"))
    return (
        root / "douyin-favorites-to-knowledge" / "browser-profile",
        home / ".openclaw" / "workspace" / "skills" / "douyin-favorites-to-knowledge" / "browser-profile",
        home / ".shared" / "skills" / "douyin-favorites-to-knowledge" / "browser-profile",
        home / ".openclaw" / "workspace" / ".douyin-pw-profile",
    )


def _normalize_favorites_mode(raw: Any) -> str | None:
    if not isinstance(raw, dict):
        return None
    transcription = raw.get("transcription")
    if not isinstance(transcription, dict):
        return None
    provider = transcription.get("provider")
    if provider in {"bailian", "cloud"}:
        return "cloud"
    if provider in {"local", "local_whisper"}:
        return "local"
    if provider == "none":
        return "index"
    return None


def detect_existing_setup() -> dict[str, Any]:
    """Return non-secret facts needed for first-run setup."""
    ensure_runtime_env()
    favorites_config = next((path for path in _favorites_config_candidates() if path.is_file()), None)
    favorites_mode = None
    if favorites_config:
        try:
            raw = json.loads(favorites_config.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
        favorites_mode = _normalize_favorites_mode(raw)

    configured_profile = os.environ.get("DOUYIN_BROWSER_PROFILE") or os.environ.get("DOUYIN_FAVORITES_PROFILE_DIR")
    profile = Path(configured_profile).expanduser() if configured_profile else None
    if profile is None:
        profile = next((candidate for candidate in _favorites_profile_candidates() if candidate.is_dir()), None)
    creator_config = default_config_path()
    favorites_skill_installed = bool(favorites_config) or any(path.exists() for path in _favorites_skill_root_candidates())
    return {
        "creator_configured": creator_config.is_file(),
        "favorites_skill_installed": favorites_skill_installed,
        "favorites_transcript_mode": favorites_mode,
        "shared_profile_available": bool(profile and profile.is_dir()),
        "profile_source": (
            "environment"
            if configured_profile
            else ("favorites_skill" if profile else "neutral_creator_profile")
        ),
        "cloud_asr_configured": bool(os.environ.get("SILICONFLOW_API_KEY") or os.environ.get("DASHSCOPE_API_KEY")),
        "siliconflow_configured": bool(os.environ.get("SILICONFLOW_API_KEY")),
        "dashscope_configured": bool(os.environ.get("DASHSCOPE_API_KEY")),
        "config_path": creator_config,
        "browser_profile": profile,
    }


def load_setup_config(path: Path | None = None) -> dict[str, Any]:
    config_path = (path or default_config_path()).expanduser().resolve()
    if not config_path.is_file():
        return {}
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read Creator Insight setup: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("Creator Insight setup must be a JSON object")
    allowed = {
        "schema_version",
        "transcript_mode",
        "allow_local_fallback",
        "browser_profile",
        "output_dir",
    }
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"unknown setup fields: {sorted(unknown)}")
    for key in raw:
        if any(secret_part in key.lower() for secret_part in SECRET_LIKE_KEYS):
            raise ValueError(f"secret-like setup field is not allowed: {key}")
    if raw.get("schema_version") != 1:
        raise ValueError("Creator Insight setup schema_version must be 1")
    mode = raw.get("transcript_mode", "cloud")
    if mode not in MODES:
        raise ValueError(f"unsupported transcript_mode: {mode!r}")
    return dict(raw)


def save_setup_config(
    mode: str,
    *,
    path: Path | None = None,
    browser_profile: Path | None = None,
    output_dir: Path | None = None,
) -> Path:
    if mode not in MODES:
        raise ValueError("setup mode must be cloud, local, or index")
    config_path = (path or default_config_path()).expanduser().resolve()
    payload: dict[str, Any] = {
        "schema_version": 1,
        "transcript_mode": mode,
        "allow_local_fallback": mode == "cloud",
    }
    if browser_profile:
        payload["browser_profile"] = str(browser_profile.expanduser().resolve())
    if output_dir:
        payload["output_dir"] = str(output_dir.expanduser().resolve())
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = config_path.with_suffix(config_path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(config_path)
    return config_path


def mode_label(mode: str) -> str:
    return {
        "cloud": "云端 ASR（抖音推荐 SiliconFlow 上传；百炼 URL 仅适合可公网直链媒体）",
        "local": "本地 Whisper（会临时下载并在结束后清理视频）",
        "index": "只做信息索引（不转录、不下载视频）",
    }[mode]
