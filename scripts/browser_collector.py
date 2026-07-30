"""Authorized-browser collector for public Douyin creator profiles."""
from __future__ import annotations

import asyncio
import platform
from pathlib import Path
from typing import Any


POSTS_API_URL = "https://www.douyin.com/aweme/v1/web/aweme/post/"


def default_profile_dir() -> Path:
    """Share the explicit profile created by douyin-favorites-to-knowledge."""
    if platform.system() == "Darwin":
        root = Path.home() / "Library" / "Application Support"
    elif platform.system() == "Windows":
        root = Path.home() / "AppData" / "Local"
    else:
        root = Path.home() / ".local" / "state"
    return root / "douyin-favorites-to-knowledge" / "browser-profile"


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
    playwright = await async_playwright().start()
    context = None
    try:
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

        cursor = 0
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
            next_cursor = int(response.get("next_cursor") or 0)
            if not response.get("has_more") or not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
        if not collected:
            raise ValueError("公开主页未返回可用视频；请确认链接、登录状态或稍后重试")
        return {
            "sec_uid": sec_uid,
            "profile_url": profile_url,
            "nickname": creator_author.get("nickname") or "",
            "signature": creator_author.get("signature") or "",
            "followers_count": creator_author.get("follower_count"),
            "heart_count": creator_author.get("total_favorited"),
        }, collected
    finally:
        if context is not None:
            await context.close()
        await playwright.stop()


def collect_public_creator_sync(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return asyncio.run(collect_public_creator(*args, **kwargs))
