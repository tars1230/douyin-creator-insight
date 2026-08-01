"""Authorized-browser collector for public Douyin creator profiles."""
from __future__ import annotations

import asyncio
import os
import platform
from pathlib import Path
from typing import Any
from integration import profile_lock
from runtime_env import ensure_runtime_env


POSTS_API_URL = "https://www.douyin.com/aweme/v1/web/aweme/post/"
PROFILE_API_URL = "https://www.douyin.com/aweme/v1/web/user/profile/other/"


def default_profile_dir() -> Path:
    """Reuse an existing Douyin profile or choose an independent shared path."""
    ensure_runtime_env()
    configured = os.environ.get("DOUYIN_BROWSER_PROFILE")
    if configured:
        return Path(configured).expanduser()
    legacy_candidates = [
        Path.home() / ".openclaw" / "workspace" / "skills" / "douyin-favorites-to-knowledge" / "browser-profile",
        Path.home() / ".openclaw" / "workspace" / ".douyin-pw-profile",
    ]
    if platform.system() == "Darwin":
        root = Path.home() / "Library" / "Application Support"
    elif platform.system() == "Windows":
        root = Path.home() / "AppData" / "Local"
    else:
        root = Path.home() / ".local" / "state"
    legacy_candidates.append(root / "douyin-favorites-to-knowledge" / "browser-profile")
    neutral_profile = root / "douyin-workflows" / "browser-profile"
    for candidate in [*legacy_candidates, neutral_profile]:
        if candidate.exists():
            return candidate
    return neutral_profile


def profile_url_from_resolved_url(url: str) -> tuple[str, str]:
    marker = "/user/"
    if marker not in url:
        raise ValueError("链接未跳转到抖音博主页；请粘贴“查看 TA 的更多作品”链接或博主页链接")
    sec_uid = url.split(marker, 1)[1].split("?", 1)[0].strip("/")
    if not sec_uid.startswith("MS4w"):
        raise ValueError("博主页缺少稳定 sec_uid；请重新复制抖音主页链接")
    return f"https://www.douyin.com/user/{sec_uid}", sec_uid


def normalize_browser_item(item: dict[str, Any]) -> dict[str, Any] | None:
    aweme_id = str(item.get("aweme_id") or "")
    if not aweme_id.isdigit():
        return None
    video = item.get("video") or {}
    stats = item.get("statistics") or {}
    author = item.get("author") or {}
    desc = str(item.get("desc") or "")
    hashtags = [str(tag.get("hashtag_name") or tag.get("name")) for tag in item.get("text_extra") or [] if isinstance(tag, dict) and (tag.get("hashtag_name") or tag.get("name"))]
    return {
        "id": aweme_id,
        "title": desc.splitlines()[0].strip() if desc else "",
        "text": desc,
        "createTime": item.get("create_time"),
        "videoMeta": {"duration": video.get("duration"), "cover": ((video.get("cover") or {}).get("url_list") or [""])[0]},
        "shareUrl": f"https://www.douyin.com/video/{aweme_id}",
        "videoUrl": _first_url(
            (video.get("play_addr") or {}).get("url_list")
            or (video.get("download_addr") or {}).get("url_list")
            or []
        ),
        "audioUrl": _first_url(
            (video.get("audio") or {}).get("url_list")
            or []
        ),
        "mediaSource": "douyin_browser_detail_api",
        "hashtags": hashtags,
        "statistics": {
            "diggCount": stats.get("digg_count"),
            "commentCount": stats.get("comment_count"),
            "shareCount": stats.get("share_count"),
            "collectCount": stats.get("collect_count"),
            "playCount": stats.get("play_count"),
        },
        "authorMeta": {"name": author.get("nickname"), "signature": author.get("signature"), "followersCount": author.get("follower_count"), "heartCount": author.get("total_favorited")},
    }


def _first_url(value: Any) -> str | None:
    if isinstance(value, list):
        return next((str(item) for item in value if item), None)
    return str(value) if value else None


def _has_author_shape(candidate: dict[str, Any]) -> bool:
    return any(
        key in candidate
        for key in ("sec_uid", "uid", "nickname", "aweme_count", "follower_count", "total_favorited", "signature")
    )


def _meaningful_values(author: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in author.items()
        if value is not None and not (isinstance(value, str) and value == "")
    }


def _profile_author(data: dict[str, Any], sec_uid: str) -> dict[str, Any]:
    """Extract profile metadata across known Douyin web response shapes."""
    user_info = data.get("user_info")
    candidates = [data.get("user")]
    if isinstance(user_info, dict):
        candidates.extend([user_info.get("user"), user_info])
    else:
        candidates.append(user_info)
    fallback: dict[str, Any] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict) or not _has_author_shape(candidate):
            continue
        if candidate.get("sec_uid") == sec_uid:
            return candidate
        if candidate.get("sec_uid") is None and not fallback:
            fallback = candidate
    return fallback


def _merge_author_metadata(profile_metadata: dict[str, Any], post_author: dict[str, Any]) -> dict[str, Any]:
    """Prefer profile API metadata while allowing per-post author fields to fill gaps."""
    merged = _meaningful_values(post_author)
    merged.update(_meaningful_values(profile_metadata))
    return merged


async def collect_public_creator(
    creator_url: str,
    *,
    max_videos: int,
    profile_dir: Path | None = None,
    headed: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Resolve a Douyin share/profile URL and collect public posts through its page context."""
    if not 1 <= max_videos <= 1000:
        raise ValueError("max_videos must be between 1 and 1000")
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise ValueError("浏览器采集需要 playwright；请安装 playwright 并完成一次 douyin-favorites 登录") from exc

    resolved_profile_dir = (profile_dir or default_profile_dir()).expanduser().resolve()
    resolved_profile_dir.mkdir(parents=True, exist_ok=True)
    guard = profile_lock(resolved_profile_dir)
    guard.__enter__()
    playwright = None
    context = None
    try:
        playwright = await async_playwright().start()
        for channel in ("chrome", "msedge", None):
            kwargs: dict[str, Any] = {
                "user_data_dir": str(resolved_profile_dir),
                "headless": not headed,
                "viewport": {"width": 1280, "height": 800},
                "locale": "zh-CN",
            }
            if channel:
                kwargs["channel"] = channel
            try:
                context = await playwright.chromium.launch_persistent_context(**kwargs)
                break
            except Exception:
                context = None
        if context is None:
            raise ValueError("未找到可用浏览器；请安装 Chrome、Edge 或 Playwright Chromium")
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(creator_url, wait_until="domcontentloaded", timeout=45_000)
        await page.wait_for_timeout(700)
        profile_url, sec_uid = profile_url_from_resolved_url(page.url)
        await page.goto(profile_url, wait_until="domcontentloaded", timeout=45_000)

        # The post-list response often omits `user`; fetch profile metadata separately
        # so declared counts can be reconciled instead of inferred from one page.
        profile_metadata: dict[str, Any] = {}
        try:
            profile_response = await page.evaluate(
                r'''async ({apiUrl, secUid}) => {
                  const params = new URLSearchParams({device_platform:'webapp', aid:'6383', sec_user_id:secUid});
                  const reply = await fetch(apiUrl + '?' + params, {credentials:'include'});
                  const data = await reply.json().catch(() => ({}));
                  return {http_status:reply.status, status_code:data.status_code, data};
                }''',
                {"apiUrl": PROFILE_API_URL, "secUid": sec_uid},
            )
            if profile_response.get("http_status") == 200 and profile_response.get("status_code") == 0:
                profile_metadata = _profile_author(profile_response.get("data") or {}, sec_uid)
        except Exception:
            # Collection remains useful when this optional metadata endpoint is blocked.
            profile_metadata = {}

        cursor = 0
        has_more = False
        next_cursor = 0
        seen: set[str] = set()
        collected: list[dict[str, Any]] = []
        creator_author: dict[str, Any] = {}
        while len(collected) < max_videos:
            response = await page.evaluate(
                r'''async ({apiUrl, secUid, cursor, count}) => {
                  const params = new URLSearchParams({device_platform:'webapp', aid:'6383', channel:'channel_pc_web', cookie_enabled:String(navigator.cookieEnabled), browser_language:navigator.language || 'zh-CN', browser_platform:navigator.platform || '', browser_name:'Chrome', sec_user_id:secUid, max_cursor:String(cursor), count:String(count)});
                  const reply = await fetch(apiUrl + '?' + params, {credentials:'include'});
                  const data = await reply.json().catch(() => ({}));
                  return {http_status:reply.status, status_code:data.status_code, has_more:Boolean(data.has_more), next_cursor:Number(data.max_cursor || 0), items:data.aweme_list || []};
                }''',
                {"apiUrl": POSTS_API_URL, "secUid": sec_uid, "cursor": cursor, "count": min(20, max_videos)},
            )
            if response.get("http_status") != 200 or response.get("status_code") != 0:
                raise ValueError("抖音公开视频列表访问失败；请在现有浏览器 profile 中重新登录或稍后重试")
            page_items = response.get("items") or []
            if not page_items:
                break
            for raw in page_items:
                author = raw.get("author") or {}
                if author.get("sec_uid") != sec_uid:
                    raise ValueError("公开视频列表作者与目标博主不一致，已停止入库")
                if not creator_author:
                    creator_author = author
                normalized = normalize_browser_item(raw)
                if normalized and normalized["id"] not in seen:
                    seen.add(normalized["id"])
                    collected.append(normalized)
                    if len(collected) >= max_videos:
                        break
            has_more = bool(response.get("has_more"))
            next_cursor = int(response.get("next_cursor") or 0)
            if len(collected) >= max_videos:
                break
            if not has_more or not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
        if not collected:
            raise ValueError("公开主页未返回可用视频；请确认链接、登录状态或稍后重试")
        creator_author = _merge_author_metadata(profile_metadata, creator_author)
        declared = profile_metadata.get("aweme_count", creator_author.get("aweme_count"))
        try:
            declared_n = int(declared) if declared is not None else None
        except (TypeError, ValueError):
            declared_n = None
        complete = (not has_more) and (
            declared_n is None or len(collected) >= declared_n
        )
        return {
            "sec_uid": sec_uid,
            "profile_url": profile_url,
            "nickname": creator_author.get("nickname") or "",
            "signature": creator_author.get("signature") or "",
            "followers_count": creator_author.get("follower_count"),
            "heart_count": creator_author.get("total_favorited"),
            "aweme_count": declared_n,
            "collected_count": len(collected),
            "collection_complete": complete,
            "next_cursor": next_cursor if has_more else None,
            "collection_stop_reason": (
                "max_videos_reached" if len(collected) >= max_videos else
                "has_more_false" if not has_more else
                "empty_page" if not page_items else "cursor_stalled"
            ),
            "declared_count_source": "profile_api" if profile_metadata.get("aweme_count") is not None else (
                "post_author" if creator_author.get("aweme_count") is not None else None
            ),
        }, collected
    finally:
        if context is not None:
            await context.close()
        if playwright is not None:
            await playwright.stop()
        guard.__exit__(None, None, None)


def collect_public_creator_sync(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return asyncio.run(collect_public_creator(*args, **kwargs))
