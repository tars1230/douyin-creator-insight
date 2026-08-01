"""ASR providers for Creator Insight.

Cloud ASR receives a public media URL and never downloads the media locally.
Local Whisper is a fallback only; it uses a temporary directory that is removed
whether transcription succeeds or fails.
"""
from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from schemas import Transcript, TranscriptStatus, Video
from runtime_env import ensure_runtime_env


CloudTranscriber = Callable[[Video], Transcript]
LocalTranscriber = Callable[[Video], Transcript]
_WHISPER_MODEL: Any = None


def transcribe_videos(
    videos: Iterable[Video],
    *,
    mode: str = "cloud",
    allow_local_fallback: bool = True,
    cloud_transcriber: CloudTranscriber | None = None,
    local_transcriber: LocalTranscriber | None = None,
) -> tuple[list[Transcript], str]:
    """Transcribe selected videos using ``cloud``, ``local``, or ``index``.

    ``cloud`` is the default. A cloud failure falls back to local Whisper only
    when allowed. ``index`` deliberately never invokes an ASR provider.
    """
    ensure_runtime_env()
    if mode not in {"cloud", "local", "index"}:
        raise ValueError("transcript mode must be cloud, local, or index")

    selected = list(videos)
    if mode == "index":
        return [
            Transcript(
                aweme_id=video.aweme_id,
                status=TranscriptStatus.SKIPPED,
                actor_used="index_only",
                err_msg="index_only: ASR was not requested",
            )
            for video in selected
        ], "index_only (标题、描述、互动数据和链接；未调用 ASR)"

    cloud = cloud_transcriber or transcribe_video_cloud
    local = local_transcriber or transcribe_video_local
    results: list[Transcript] = []
    providers: set[str] = set()

    for video in selected:
        if mode == "local":
            transcript = _safe_transcribe(local, video, "local-whisper")
            results.append(transcript)
            providers.add(transcript.actor_used or "local-whisper")
            continue

        transcript = _safe_transcribe(cloud, video, "dashscope-cloud")
        if transcript.status == TranscriptStatus.SUCCESS:
            results.append(transcript)
            providers.add(transcript.actor_used or "dashscope-cloud")
            continue

        if allow_local_fallback and not _is_missing_configuration(transcript):
            fallback = _safe_transcribe(local, video, "local-whisper")
            if fallback.status == TranscriptStatus.SUCCESS:
                fallback.err_msg = _join_errors(transcript.err_msg, "cloud failed; local fallback used")
                results.append(fallback)
                providers.add(fallback.actor_used or "local-whisper")
                continue
            fallback.err_msg = _join_errors(transcript.err_msg, fallback.err_msg)
            results.append(fallback)
            providers.add(fallback.actor_used or "local-whisper")
        elif _is_missing_configuration(transcript):
            transcript.err_msg = _join_errors(
                transcript.err_msg,
                "local fallback not attempted because cloud credentials are missing; choose local explicitly",
            )
            results.append(transcript)
            providers.add(transcript.actor_used or "dashscope-cloud")
        else:
            results.append(transcript)
            providers.add(transcript.actor_used or "dashscope-cloud")

    source = ", ".join(sorted(providers)) or "not_configured"
    if mode == "cloud" and allow_local_fallback:
        source += " (cloud default; local fallback on failure)"
    return results, source


def transcribe_video_cloud(video: Video) -> Transcript:
    """Use the cloud ASR lane without invoking local Whisper.

    It first attempts DashScope URL recognition without local media. If the
    upstream rejects a large Douyin video, it uses an optional cloud-upload
    provider with temporary media and removes it before returning.
    """
    ensure_runtime_env()
    direct = _transcribe_dashscope_url(video)
    if direct.status == TranscriptStatus.SUCCESS:
        return direct
    uploaded = _transcribe_siliconflow_upload(video)
    if uploaded.status == TranscriptStatus.SUCCESS:
        uploaded.err_msg = _join_errors(direct.err_msg, "DashScope URL ASR fell back to cloud upload")
        return uploaded
    uploaded.err_msg = _join_errors(direct.err_msg, uploaded.err_msg)
    return uploaded


def _transcribe_dashscope_url(video: Video) -> Transcript:
    """Use DashScope-compatible ASR with a public URL and no local media."""
    media_url = video.audio_url or video.video_url
    if not media_url:
        return _failed(video, "dashscope-cloud", "no public media URL available for cloud ASR")
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        return _failed(video, "dashscope-cloud", "DASHSCOPE_API_KEY is not configured")

    endpoint = os.environ.get(
        "DOUYIN_CLOUD_ASR_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    )
    model = os.environ.get("DASHSCOPE_ASR_MODEL", "qwen3-asr-flash")
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [{
                "type": "input_audio",
                "input_audio": {"data": media_url, "format": _media_format(media_url)},
            }],
        }],
    }
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        return _failed(video, "dashscope-cloud", f"cloud ASR HTTP {exc.code}: {detail}")
    except (URLError, TimeoutError, OSError) as exc:
        return _failed(video, "dashscope-cloud", f"cloud ASR request failed: {exc}")
    except json.JSONDecodeError as exc:
        return _failed(video, "dashscope-cloud", f"cloud ASR returned invalid JSON: {exc}")

    text = _extract_cloud_text(response_payload)
    if len(text.strip()) < 2:
        return _failed(video, "dashscope-cloud", "cloud ASR returned an empty transcript")
    return Transcript(
        aweme_id=video.aweme_id,
        status=TranscriptStatus.SUCCESS,
        text=text.strip(),
        duration_seconds=video.duration_seconds,
        actor_used="dashscope-cloud",
    )


def _transcribe_siliconflow_upload(video: Video) -> Transcript:
    """Use cloud upload ASR when direct URL recognition cannot accept the video.

    Downloaded source/audio exist only under ``TemporaryDirectory``. This is
    still cloud ASR: local Whisper is neither loaded nor invoked.
    """
    media_url = video.audio_url or video.video_url
    api_key = os.environ.get("SILICONFLOW_API_KEY")
    if not api_key:
        return _failed(video, "siliconflow-cloud", "SILICONFLOW_API_KEY is not configured")
    if not media_url:
        return _failed(video, "siliconflow-cloud", "no public media URL available for cloud upload ASR")
    endpoint = os.environ.get("SILICONFLOW_ASR_URL", "https://api.siliconflow.cn/v1/audio/transcriptions")
    model = os.environ.get("SILICONFLOW_ASR_MODEL", "FunAudioLLM/SenseVoiceSmall")
    try:
        with tempfile.TemporaryDirectory(prefix="douyin-creator-cloud-") as temporary:
            temp_dir = Path(temporary)
            source_path = temp_dir / f"source.{_media_format(media_url)}"
            audio_path = temp_dir / "audio.mp3"
            _download_media(media_url, source_path)
            _extract_cloud_audio(source_path, audio_path)
            response_payload = _post_multipart(
                endpoint,
                api_key,
                audio_path,
                {"model": model, "language": "zh"},
            )
    except Exception as exc:
        return _failed(video, "siliconflow-cloud", f"cloud upload ASR failed: {exc}")
    text = _extract_cloud_text(response_payload)
    if len(text.strip()) < 2:
        return _failed(video, "siliconflow-cloud", "cloud upload ASR returned an empty transcript")
    return Transcript(
        aweme_id=video.aweme_id,
        status=TranscriptStatus.SUCCESS,
        text=text.strip(),
        duration_seconds=video.duration_seconds,
        actor_used="siliconflow-cloud",
    )


def transcribe_video_local(video: Video) -> Transcript:
    """Download only for local Whisper and always remove temporary media."""
    ensure_runtime_env()
    media_url = video.audio_url or video.video_url
    if not media_url:
        return _failed(video, "local-whisper", "no public media URL available for local fallback")

    try:
        with tempfile.TemporaryDirectory(prefix="douyin-creator-asr-") as temporary:
            temp_dir = Path(temporary)
            source_path = temp_dir / f"source.{_media_format(media_url)}"
            audio_path = temp_dir / "audio.wav"
            _download_media(media_url, source_path)
            _extract_audio(source_path, audio_path)
            text, segments = _whisper_transcribe(audio_path)
    except Exception as exc:
        return _failed(video, "local-whisper", f"local Whisper fallback failed: {exc}")

    if len(text.strip()) < 2:
        return Transcript(
            aweme_id=video.aweme_id,
            status=TranscriptStatus.EMPTY,
            actor_used="local-whisper",
            err_msg="local Whisper returned empty transcript",
        )
    return Transcript(
        aweme_id=video.aweme_id,
        status=TranscriptStatus.SUCCESS,
        text=text.strip(),
        duration_seconds=video.duration_seconds,
        segments=segments,
        actor_used="local-whisper",
    )


def _safe_transcribe(transcriber: Callable[[Video], Transcript], video: Video, provider: str) -> Transcript:
    try:
        result = transcriber(video)
    except Exception as exc:
        return _failed(video, provider, str(exc))
    if not isinstance(result, Transcript):
        return _failed(video, provider, "provider returned an invalid result")
    return result


def _is_missing_configuration(transcript: Transcript) -> bool:
    """Do not turn a missing cloud key into an implicit media download."""
    message = (transcript.err_msg or "").lower()
    return any(
        marker in message
        for marker in (
            "api_key is not configured",
            "api key is not configured",
            "credentials are missing",
        )
    )


def _download_media(url: str, destination: Path) -> None:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=120) as response, destination.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)


def _extract_audio(source: Path, audio: Path) -> None:
    completed = subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000", str(audio)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr[-500:] or "ffmpeg failed")


def _extract_cloud_audio(source: Path, audio: Path) -> None:
    completed = subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k", str(audio)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr[-500:] or "ffmpeg cloud audio extraction failed")


def _post_multipart(endpoint: str, api_key: str, audio_path: Path, fields: dict[str, str]) -> Any:
    boundary = f"----douyinCreator{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            str(value).encode(),
            b"\r\n",
        ])
    mime = mimetypes.guess_type(audio_path.name)[0] or "audio/mpeg"
    chunks.extend([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{audio_path.name}"\r\n'.encode(),
        f"Content-Type: {mime}\r\n\r\n".encode(),
        audio_path.read_bytes(),
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])
    request = Request(
        endpoint,
        data=b"".join(chunks),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def _whisper_transcribe(audio_path: Path) -> tuple[str, list[dict[str, Any]]]:
    global _WHISPER_MODEL
    try:
        import whisper
    except ImportError as exc:
        raise RuntimeError("openai-whisper is not installed") from exc
    if _WHISPER_MODEL is None:
        _WHISPER_MODEL = whisper.load_model(os.environ.get("DOUYIN_WHISPER_MODEL", "base"))
    result = _WHISPER_MODEL.transcribe(str(audio_path), language="zh", fp16=False)
    segments = [
        {"start": segment.get("start"), "end": segment.get("end"), "text": segment.get("text", "").strip()}
        for segment in result.get("segments", [])
    ]
    return str(result.get("text") or ""), segments


def _extract_cloud_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    choices = payload.get("choices") or []
    if choices and isinstance(choices[0], dict):
        content = (choices[0].get("message") or {}).get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(
                str(part.get("text") or "") for part in content if isinstance(part, dict)
            )
    output = payload.get("output") or {}
    return str(output.get("text") or payload.get("text") or "")


def _media_format(url: str) -> str:
    suffix = url.split("?", 1)[0].rsplit(".", 1)[-1].lower()
    return suffix if suffix in {"aac", "m4a", "mp3", "mp4", "ogg", "opus", "wav", "webm"} else "mp4"


def _failed(video: Video, provider: str, error: str) -> Transcript:
    return Transcript(
        aweme_id=video.aweme_id,
        status=TranscriptStatus.FAILED,
        actor_used=provider,
        err_msg=error,
    )


def _join_errors(*errors: str | None) -> str:
    return "; ".join(error for error in errors if error)
