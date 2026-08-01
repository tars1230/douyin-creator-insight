"""Non-mutating checks for safe coexistence with the favorites skill."""
from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


def _favorites_roots() -> list[Path]:
    home = Path.home()
    return [
        home / ".shared" / "skills" / "douyin-favorites-to-knowledge",
        home / ".openclaw" / "workspace" / "skills" / "douyin-favorites-to-knowledge",
        home / ".shared" / "skills" / "douyin-knowledge-base-pipeline",
    ]


def probe_installation(profile: Path | None = None, output_dir: Path | None = None) -> dict[str, Any]:
    """Return integration facts without writing config, login, or credentials."""
    from browser_collector import default_profile_dir
    from runtime_env import ensure_runtime_env
    from setup_config import detect_existing_setup

    ensure_runtime_env()
    detected = detect_existing_setup()
    selected_profile = (profile or default_profile_dir()).expanduser()
    favorites = [root for root in _favorites_roots() if root.exists()]
    output = (output_dir or Path("./output")).expanduser()
    creator_output = output / "creator-insight"
    profile_busy = any((selected_profile / name).exists() for name in ("SingletonLock", "SingletonSocket"))
    conflicts: list[str] = []
    if output.exists() and output.resolve() in {root.resolve() for root in favorites}:
        conflicts.append("output_dir overlaps the favorites skill directory")
    if selected_profile.exists() and not selected_profile.is_dir():
        conflicts.append("shared browser profile path is not a directory")
    if profile_busy:
        conflicts.append("shared browser profile is already in use")
    return {
        "creator_insight": "installed",
        "favorites_skill": "installed" if favorites else "not_installed (optional)",
        "favorites_transcript_mode": detected.get("favorites_transcript_mode"),
        "cloud_asr_configured": detected["cloud_asr_configured"],
        "setup_configured": detected["creator_configured"],
        "shared_profile": "available" if selected_profile.is_dir() else "not_initialized (login required)",
        "profile_reuse": bool(selected_profile.is_dir()),
        "profile_source": detected["profile_source"],
        "shared_profile_busy": profile_busy,
        "isolated_output": True,
        "recommended_output_layout": "<output-root>/creator-insight/",
        "schedule_conflict": "none (Creator Insight has no scheduler)",
        "conflicts": conflicts,
        "ready": not conflicts,
    }


@contextmanager
def profile_lock(profile: Path) -> Iterator[None]:
    """Serialize persistent-profile use between local Douyin workflows."""
    lock_root = Path.home() / ".cache" / "douyin-creator-insight"
    lock_root.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(str(profile.expanduser().resolve()).encode()).hexdigest()[:16]
    lock_path = lock_root / f"profile-{digest}.lock"
    handle = lock_path.open("a+")
    fcntl_module = None
    try:
        try:
            import fcntl
            fcntl_module = fcntl
            fcntl_module.flock(handle.fileno(), fcntl_module.LOCK_EX | fcntl_module.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("shared Douyin browser profile is busy; wait for the other workflow to finish") from exc
        except ImportError:
            # Chromium's SingletonLock/SingletonSocket remains the cross-platform guard.
            pass
        yield
    finally:
        if fcntl_module is not None:
            fcntl_module.flock(handle.fileno(), fcntl_module.LOCK_UN)
        handle.close()


def main() -> int:
    print(json.dumps(probe_installation(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
