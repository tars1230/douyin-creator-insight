"""
Douyin Creator Insight - Video Parser
Apify profile scraper 字段标准化
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
from schemas import Video, VideoStats


def parse_actor_dataset(
    raw_items: List[Dict[str, Any]],
    actor_name: str = "zen-studio/douyin-profile-scraper",
) -> List[Video]:
    """
    标准化 Apify actor 返回的视频数据

    不同 actor 字段名差异：
    - zen-studio: id, text, statistics.diggCount
    - bovi: aweme_id, desc, aweme_stats.digg_count
    - sian.agency: videoId, desc, stats.like
    """
    videos = []
    for item in raw_items:
        v = _normalize_video_item(item, actor_name)
        if v:
            videos.append(v)
    return videos


def _normalize_video_item(item: Dict[str, Any], actor_name: str) -> Optional[Video]:
    """标准化单个视频 item"""
    # 1. 提取视频 ID
    aweme_id = _extract_field(item, ["id", "aweme_id", "videoId", "awemeId"])
    if not aweme_id:
        return None

    # 2. 提取标题/描述
    title = _extract_field(item, ["title"]) or ""
    desc = _extract_field(item, ["text", "desc", "description", "caption"]) or ""

    # 3. 提取时间戳
    create_time = _extract_field(item, ["createTime", "create_time", "timestamp", "publish_time"])
    create_time = int(create_time) if create_time else None

    # 4. 提取时长
    duration_ms = _extract_field(item, ["videoMeta.duration", "video.duration", "duration"])
    if duration_ms:
        duration_ms = int(duration_ms)
    duration_seconds = duration_ms / 1000.0 if duration_ms else None

    # 5. 提取封面和分享 URL
    cover_url = _extract_field(item, ["videoMeta.cover", "video.cover", "coverUrl", "cover"])
    share_url = _extract_field(item, ["shareUrl", "share_url", "url", "videoUrl"])
    video_url = _extract_field(item, [
        "videoUrl", "video_url", "videoMeta.url", "video.play_addr.url_list.0",
        "video.play_addr.url", "play_addr.url_list.0", "download_url",
    ])
    audio_url = _extract_field(item, [
        "audioUrl", "audio_url", "audio.url", "audioMeta.url",
        "video.audio.url_list.0", "video.audio.url",
    ])
    media_source = _extract_field(item, ["mediaSource", "media_source"])

    # 6. 提取 hashtags
    hashtags = _extract_hashtags(item)

    # 7. 提取合集名
    series_name = _extract_field(item, ["series.name", "seriesName", "collection_name"])

    # 8. 提取统计数据
    stats = _extract_stats(item)

    return Video(
        aweme_id=str(aweme_id),
        title=title,
        desc=desc,
        create_time=create_time,
        create_date=_format_date(create_time),
        duration_ms=duration_ms,
        duration_seconds=duration_seconds,
        cover_url=cover_url,
        share_url=share_url,
        video_url=video_url,
        audio_url=audio_url,
        media_source=media_source,
        hashtags=hashtags,
        series_name=series_name,
        stats=stats,
        raw=item,
    )


def _extract_field(item: Dict[str, Any], paths: List[str]) -> Any:
    """按多个可能的字段路径提取值"""
    for path in paths:
        # 支持点分路径（videoMeta.duration）
        if "." in path:
            keys = path.split(".")
            current = item
            for k in keys:
                if isinstance(current, dict) and k in current:
                    current = current[k]
                elif isinstance(current, list) and k.isdigit() and int(k) < len(current):
                    current = current[int(k)]
                else:
                    current = None
                    break
            if current is not None:
                return current
        else:
            if path in item and item[path] is not None:
                return item[path]
    return None


def _extract_hashtags(item: Dict[str, Any]) -> List[str]:
    """提取 hashtags 列表"""
    # 多种格式：
    # - hashtags: [{"name": "..."}, ...]
    # - hashtags: ["...", "..."]
    # - text/desc 里包含 #话题#
    raw = item.get("hashtags")
    if isinstance(raw, list):
        result = []
        for h in raw:
            if isinstance(h, dict):
                name = h.get("name") or h.get("title") or h.get("text")
                if name:
                    result.append(name)
            elif isinstance(h, str):
                result.append(h)
        return result

    # 从 desc 中解析 #xxx#
    import re
    desc = item.get("text") or item.get("desc") or item.get("description") or ""
    matches = re.findall(r"#([^#\s]+)#?", str(desc))
    return [m for m in matches if m]


def _extract_stats(item: Dict[str, Any]) -> VideoStats:
    """提取互动统计"""
    return VideoStats(
        digg_count=_safe_int(_extract_field(item, [
            "statistics.diggCount", "stats.diggCount", "aweme_stats.digg_count",
            "like", "likes", "diggCount", "likeCount"
        ])),
        comment_count=_safe_int(_extract_field(item, [
            "statistics.commentCount", "stats.commentCount", "aweme_stats.comment_count",
            "comment", "comments", "commentCount"
        ])),
        share_count=_safe_int(_extract_field(item, [
            "statistics.shareCount", "stats.shareCount", "aweme_stats.share_count",
            "share", "shares", "shareCount"
        ])),
        collect_count=_safe_int(_extract_field(item, [
            "statistics.collectCount", "stats.collectCount", "aweme_stats.collect_count",
            "collect", "collects", "favorite", "collectCount"
        ])),
        play_count=_safe_int(_extract_field(item, [
            "statistics.playCount", "stats.playCount", "aweme_stats.play_count",
            "play", "views", "playCount"
        ])),
    )


def _safe_int(val: Any) -> int:
    """安全转 int"""
    if val is None:
        return 0
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def _format_date(timestamp: Optional[int]) -> Optional[str]:
    """Unix 时间戳 → YYYY-MM-DD"""
    if not timestamp:
        return None
    # 处理毫秒和秒
    if timestamp > 10**12:
        timestamp = timestamp / 1000
    from datetime import datetime
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime("%Y-%m-%d")
    except (ValueError, OSError):
        return None


def parse_toon_output(toon_text: str) -> List[Dict[str, Any]]:
    """
    解析 Apify dataset 的 TOON 格式输出
    用于本地 dry-run 测试

    TOON 格式示例：
    items[200]:
      - id: "7600998358588812742"
        text: "..."
        statistics:
          diggCount: 12345
    """
    import re
    items = []
    # 找到 items 块
    m = re.search(r"items\[\d+\]:\s*\n", toon_text)
    if not m:
        return items
    start = m.end()

    # 切分 item（按 \n  - id: 分隔）
    positions = [mm.start() for mm in re.finditer(r"\n  - id:", "\n" + toon_text[start:])]
    pre = "\n" + toon_text[start:]

    for i, pos in enumerate(positions):
        end = positions[i+1] if i+1 < len(positions) else len(pre)
        block = pre[pos+1:end].strip()
        # 去掉开头的 "id: "
        first_nl = block.find("\n")
        first_line = block[:first_nl].strip()
        rest = block[first_nl+1:]

        obj = {}
        # 第一行: - id: "value"
        m_id = re.match(r'-\s*id:\s*"?([^"\s]+)"?\s*$', first_line)
        if m_id:
            obj["id"] = m_id.group(1)

        # 后续行
        current_obj = obj
        current_indent = 0
        path_stack = [obj]

        for line in rest.split("\n"):
            # 4 空格缩进为顶层字段
            m2 = re.match(r"    ([A-Za-z_][A-Za-z0-9_.]*):\s*(.*)", line)
            if m2:
                key, val = m2.group(1), m2.group(2)
                if val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                elif val in ("", "null"):
                    val = None
                elif re.match(r"^-?\d+$", val):
                    val = int(val)
                obj[key] = val
        if obj:
            items.append(obj)
    return items
