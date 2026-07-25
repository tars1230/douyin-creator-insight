"""
Douyin Creator Insight - Transcript
调用 Apify transcripts scraper 抓取视频语音转写
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Callable
from schemas import Video, Transcript, TranscriptStatus


# Actor 配置
TRANSCRIPT_ACTORS = [
    {
        "name": "zen-studio/douyin-transcripts-scraper",
        "max_duration_minutes": None,  # 不限
        "language_param": "targetLanguage",
        "wait_secs": 45,
    },
    {
        "name": "apple_yang/douyin-transcripts-scraper",
        "max_duration_minutes": 5.0,
        "language_param": None,
        "wait_secs": 30,
    },
]


def build_video_url(aweme_id: str) -> str:
    """构造抖音视频分享 URL"""
    return f"https://www.douyin.com/video/{aweme_id}"


def fetch_transcripts(
    videos: List[Video],
    apify_caller: Callable,
    primary_actor: str = "zen-studio/douyin-transcripts-scraper",
    language: str = "zh",
) -> List[Transcript]:
    """
    批量抓取视频转写

    主 actor 失败时切换备用 actor
    """
    transcripts = []

    # 1. 构造 actor 输入
    video_urls = [build_video_url(v.aweme_id) for v in videos]

    # 2. 调用主 actor
    primary_result = _call_transcript_actor(
        apify_caller,
        primary_actor,
        {"targetLanguage": language, "videoUrls": video_urls},
        TRANSCRIPT_ACTORS[0]["wait_secs"],
    )

    # 3. 解析结果
    parsed_primary = _parse_transcript_result(primary_result, primary_actor)

    # 4. 对失败的尝试备用 actor
    failed_ids = {v.aweme_id for v, t in zip(videos, parsed_primary)
                  if t.status != TranscriptStatus.SUCCESS}

    if failed_ids:
        # 过滤出失败的视频
        retry_videos = [v for v in videos if v.aweme_id in failed_ids]
        retry_urls = [build_video_url(v.aweme_id) for v in retry_videos]

        backup_result = _call_transcript_actor(
            apify_caller,
            TRANSCRIPT_ACTORS[1]["name"],
            {"videoUrl": retry_urls[0]} if len(retry_urls) == 1 else {"videoUrl": retry_urls},
            TRANSCRIPT_ACTORS[1]["wait_secs"],
        )

        parsed_backup = _parse_transcript_result(backup_result, TRANSCRIPT_ACTORS[1]["name"])

        # 合并：主 actor 成功的保留，失败的用备用
        by_id_primary = {t.aweme_id: t for t in parsed_primary}
        by_id_backup = {t.aweme_id: t for t in parsed_backup}

        for v in videos:
            if v.aweme_id in by_id_primary and by_id_primary[v.aweme_id].status == TranscriptStatus.SUCCESS:
                transcripts.append(by_id_primary[v.aweme_id])
            elif v.aweme_id in by_id_backup:
                transcripts.append(by_id_backup[v.aweme_id])
            else:
                transcripts.append(Transcript(
                    aweme_id=v.aweme_id,
                    status=TranscriptStatus.FAILED,
                    err_msg="Both primary and backup actors failed",
                ))
    else:
        transcripts = parsed_primary

    return transcripts


def _call_transcript_actor(
    apify_caller: Callable,
    actor: str,
    input_data: Dict[str, Any],
    wait_secs: int,
) -> Any:
    """调用 Apify actor"""
    try:
        result = apify_caller(
            actor=actor,
            input=input_data,
            wait_secs=wait_secs,
        )
        return result
    except Exception as e:
        return {"errMsg": str(e)}


def _parse_transcript_result(
    raw_result: Any,
    actor_name: str,
) -> List[Transcript]:
    """
    解析 actor 返回的结果

    zen-studio 返回格式示例：
    [
      {
        "id": "7575296454722398441",
        "caption": "...",
        "text": "完整转写文本",
        "duration": 812,
        "segments": [{"start": 0, "end": 5.2, "text": "..."}]
      }
    ]
    """
    if isinstance(raw_result, dict) and "errMsg" in raw_result:
        # 全局失败
        return [Transcript(
            aweme_id="",
            status=TranscriptStatus.FAILED,
            err_msg=raw_result["errMsg"],
            actor_used=actor_name,
        )]

    if not isinstance(raw_result, list):
        return []

    transcripts = []
    for item in raw_result:
        if not isinstance(item, dict):
            continue

        aweme_id = str(item.get("id") or item.get("aweme_id") or item.get("videoId") or "")
        if not aweme_id:
            continue

        text = item.get("text") or item.get("transcript") or item.get("caption") or ""
        duration_seconds = item.get("duration")
        if duration_seconds and duration_seconds > 1000:
            duration_seconds = duration_seconds / 1000  # 毫秒 → 秒

        segments = item.get("segments") or []
        if isinstance(segments, str):
            # 如果 segments 是字符串，尝试解析
            segments = []

        # 判断状态
        if not text or len(text) < 10:
            status = TranscriptStatus.EMPTY
        elif text.startswith("[") and "transcript failed" in text.lower():
            status = TranscriptStatus.FAILED
        else:
            status = TranscriptStatus.SUCCESS

        transcripts.append(Transcript(
            aweme_id=aweme_id,
            status=status,
            text=text,
            duration_seconds=duration_seconds,
            segments=segments,
            actor_used=actor_name,
            err_msg=item.get("errMsg"),
        ))
    return transcripts


def merge_transcripts_to_videos(
    videos: List[Video],
    transcripts: List[Transcript],
) -> List[Dict[str, Any]]:
    """把 transcript 合并到 video 列表"""
    transcript_by_id = {t.aweme_id: t for t in transcripts}
    merged = []
    for v in videos:
        t = transcript_by_id.get(v.aweme_id)
        merged.append({
            "video": v,
            "transcript": t.text if t else "",
            "transcript_status": t.status.value if t else "skipped",
        })
    return merged
