"""Load local runtime config for Douyin Creator Insight.

Hermes and other launcher paths do not always forward shell environment
variables into the skill process. This helper reads a narrow whitelist of
keys from standard local env files so cloud ASR and the shared browser profile
still work when they were already configured once.
"""
from __future__ import annotations

import os
from ast import literal_eval
from pathlib import Path
from typing import Iterable, Iterator


RUNTIME_ENV_KEYS = {
    "DASHSCOPE_API_KEY",
    "DASHSCOPE_ASR_MODEL",
    "DOUYIN_CLOUD_ASR_URL",
    "DOUYIN_BROWSER_PROFILE",
    "DOUYIN_WHISPER_MODEL",
    "SILICONFLOW_API_KEY",
    "SILICONFLOW_ASR_URL",
    "SILICONFLOW_ASR_MODEL",
}
RUNTIME_ENV_FILES: tuple[Path, ...] | None = None
_LOADED_ENV_FILE_SIGNATURES: set[tuple[str, ...]] = set()


def _default_env_files() -> tuple[Path, ...]:
    skill_root = Path(__file__).resolve().parents[1]
    home = Path.home()
    hermes_home = Path(os.environ.get("HERMES_HOME", home / ".hermes")).expanduser()
    candidates = (
        Path.cwd() / ".env",
        Path.cwd() / ".env.local",
        skill_root / ".env",
        skill_root / ".env.local",
        hermes_home / ".env",
        home / ".hermes" / ".env",
        home / ".config" / "douyin-creator-insight.env",
        home / ".config" / "douyin-creator-insight" / ".env",
    )
    seen: set[str] = set()
    ordered: list[Path] = []
    for candidate in candidates:
        normalized = str(candidate.expanduser())
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(candidate.expanduser())
    return tuple(ordered)


def ensure_runtime_env(candidate_files: Iterable[Path] | None = None) -> list[Path]:
    """Load missing runtime keys from local env files.

    Existing process environment values always win. The return value lists the
    files that contributed at least one loaded key. Empty assignments such as
    ``KEY=`` are ignored; unset or override keys in the parent process when a
    workflow needs to disable a provider.
    """
    loaded_sources: list[Path] = []
    files = tuple(candidate_files) if candidate_files is not None else (RUNTIME_ENV_FILES or _default_env_files())
    signature = None
    if candidate_files is None:
        signature = tuple(str(path.expanduser()) for path in files)
        if signature in _LOADED_ENV_FILE_SIGNATURES:
            return loaded_sources
    for path in files:
        if not path.is_file():
            continue
        loaded_any = False
        for key, value in _iter_env_pairs(path):
            if key not in RUNTIME_ENV_KEYS:
                continue
            if os.environ.get(key):
                continue
            if value == "":
                continue
            os.environ[key] = value
            loaded_any = True
        if loaded_any:
            loaded_sources.append(path)
    if signature is not None:
        _LOADED_ENV_FILE_SIGNATURES.add(signature)
    return loaded_sources


def reset_runtime_env_cache() -> None:
    """Clear the per-process env-file load cache for tests."""
    _LOADED_ENV_FILE_SIGNATURES.clear()


def _iter_env_pairs(path: Path) -> Iterator[tuple[str, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw_line in text.splitlines():
        pair = _parse_env_line(raw_line)
        if pair is not None:
            yield pair


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[7:].lstrip()
    if "=" not in stripped:
        return None
    key, raw_value = stripped.split("=", 1)
    key = key.strip()
    if not key:
        return None
    value = raw_value.strip()
    if not value:
        return key, ""
    if value[0] in {"'", '"'} and value[-1] == value[0]:
        try:
            parsed = literal_eval(value)
        except (SyntaxError, ValueError):
            return key, value[1:-1]
        return key, str(parsed)
    return key, _strip_unquoted_comment(value)


def _strip_unquoted_comment(value: str) -> str:
    for index, character in enumerate(value):
        if character == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()
    return value
