"""
Douyin Creator Insight - Creator Resolver
抖音号/昵称/URL → 候选博主
"""
from __future__ import annotations

import json
import re
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse, parse_qs
from schemas import CreatorResolution, CreatorCandidate


# 抖音号 6-12 位数字
DOUYIN_ID_PATTERN = re.compile(r"^\d{6,12}$")

# 抖音 URL 格式
DOUYIN_URL_PATTERNS = [
    re.compile(r"https?://(?:www\.)?douyin\.com/user/([A-Za-z0-9_-]+)"),  # user/MS4w...
    re.compile(r"https?://v\.douyin\.com/([A-Za-z0-9_-]+)"),  # 短链
    re.compile(r"https?://(?:www\.)?douyin\.com/discover\?.*modal_id=(\d+)"),
]
URL_IN_TEXT_PATTERN = re.compile(r"https?://[^\s]+")


def extract_douyin_url(user_input: str) -> Optional[str]:
    """Extract a Douyin URL from a full share message without trusting its other text."""
    for match in URL_IN_TEXT_PATTERN.finditer(user_input):
        candidate = match.group(0).rstrip("，。；;）)]}！？!\"'")
        if any(pattern.match(candidate) for pattern in DOUYIN_URL_PATTERNS):
            return candidate
    return None


def parse_input_type(user_input: str) -> str:
    """
    解析用户输入类型
    返回: douyin_id | sec_uid | nickname | url | unknown
    """
    user_input = user_input.strip()
    url_input = extract_douyin_url(user_input)

    # 1. 完整 URL
    for pattern in DOUYIN_URL_PATTERNS:
        m = pattern.match(url_input or user_input)
        if m:
            captured = m.group(1)
            if captured.isdigit() and len(captured) > 12:
                return "aweme_id"  # 这是视频 URL
            return "url"

    # 2. 抖音号（纯数字）
    if DOUYIN_ID_PATTERN.match(user_input):
        return "douyin_id"

    # 3. sec_uid（MS4w 开头）
    if user_input.startswith("MS4w"):
        return "sec_uid"

    # 4. 包含中文/英文 → 昵称
    if re.search(r"[\u4e00-\u9fa5a-zA-Z]", user_input):
        return "nickname"

    return "unknown"


def extract_sec_uid_from_url(url: str) -> Optional[str]:
    """从 URL 提取 sec_uid"""
    m = re.match(r"https?://(?:www\.)?douyin\.com/user/([A-Za-z0-9_-]+)", url)
    if m:
        return m.group(1)
    return None


def resolve_creator_via_apify(
    user_input: str,
    input_type: str,
    apify_caller=None,
    apify_browser=None,
) -> CreatorResolution:
    """
    通过 Apify MCP 解析博主身份

    apify_caller: 调用 actor 的函数（mock 或真实 MCP）
    apify_browser: 调用 rag-web-browser 的函数
    """
    # 如果是 sec_uid 直接确认
    if input_type == "sec_uid":
        return CreatorResolution(
            creator_query=user_input,
            matched=True,
            confidence=0.95,
            sec_uid=user_input,
            profile_url=f"https://www.douyin.com/user/{user_input}",
        )

    # 抖音号（数字）— 需要通过 apify 搜索确认
    if input_type == "douyin_id":
        return _resolve_via_apify_search(user_input, "douyin_id", apify_browser)

    # URL 提取 sec_uid
    if input_type == "url":
        sec_uid = extract_sec_uid_from_url(user_input)
        if sec_uid:
            return CreatorResolution(
                creator_query=user_input,
                matched=True,
                confidence=0.95,
                sec_uid=sec_uid,
                profile_url=user_input,
            )

    # 昵称 — 模糊搜索
    if input_type == "nickname":
        return _resolve_via_apify_search(user_input, "nickname", apify_browser)

    # 默认兜底：未识别
    return CreatorResolution(
        creator_query=user_input,
        matched=False,
        confidence=0.0,
    )


def _resolve_via_apify_search(
    query: str,
    query_type: str,
    apify_browser=None,
) -> CreatorResolution:
    """
    通过 Apify 搜索博主（mock 友好）
    真实场景下用 apify--rag-web-browser 搜索
    """
    # mock 实现：调用方需要传入 apify_browser
    if apify_browser is None:
        # 没有 browser 工具时返回未匹配，让上层决定
        return CreatorResolution(
            creator_query=query,
            matched=False,
            confidence=0.0,
        )

    # 真实实现：调用 apify--rag-web-browser 搜索
    try:
        result = apify_browser(
            query=f"抖音 {query} 个人主页",
            max_results=5,
        )
        candidates = _parse_search_results(result, query)
        if not candidates:
            return CreatorResolution(
                creator_query=query,
                matched=False,
                confidence=0.0,
            )

        # 取第一条作为最佳匹配
        best = candidates[0]
        if best.match_score >= 0.9:
            return CreatorResolution(
                creator_query=query,
                matched=True,
                confidence=best.match_score,
                sec_uid=best.douyin_id,
                nickname=best.nickname,
                profile_url=best.profile_url,
                followers_count=best.followers_count,
                signature=best.signature,
            )
        else:
            # 模糊匹配 → 返回候选列表
            return CreatorResolution(
                creator_query=query,
                matched=False,
                confidence=best.match_score,
                candidates=candidates,
            )
    except Exception:
        return CreatorResolution(
            creator_query=query,
            matched=False,
            confidence=0.0,
        )


def _parse_search_results(raw: Any, query: str = "") -> List[CreatorCandidate]:
    """解析搜索 / browser 返回为候选列表。

    WorkBuddy 的 browser 工具可能返回 markdown、dict 或 sources 列表。这里做
    宽松解析：只要能看到 douyin.com/user/<sec_uid> 链接，就把附近文本作为候选。
    """
    text = _raw_search_result_to_text(raw)
    if not text:
        return []

    candidates: List[CreatorCandidate] = []
    seen = set()
    pattern = re.compile(
        r"(?:https?://)?(?:www\.)?douyin\.com/user/([A-Za-z0-9_-]+)"
    )
    for match in pattern.finditer(text):
        sec_uid = match.group(1)
        if sec_uid in seen:
            continue
        seen.add(sec_uid)

        start = max(0, match.start() - 160)
        end = min(len(text), match.end() + 220)
        context = _clean_context(text[start:end])
        nickname = _guess_nickname(context, query)
        followers = _guess_followers_count(context)
        score = _score_candidate(context, query)

        candidates.append(CreatorCandidate(
            nickname=nickname or query or sec_uid,
            douyin_id=sec_uid,
            profile_url=f"https://www.douyin.com/user/{sec_uid}",
            followers_count=followers,
            signature=context[:120],
            match_score=score,
        ))

    candidates.sort(key=lambda c: (c.match_score, c.followers_count or 0), reverse=True)
    return candidates[:5]


def _raw_search_result_to_text(raw: Any) -> str:
    """把 browser/search 结果压成可解析文本。"""
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        return "\n".join(_raw_search_result_to_text(item) for item in raw)
    if isinstance(raw, dict):
        chunks = []
        for key in (
            "answer", "text", "markdown", "content", "title", "description",
            "url", "source", "sources", "items", "results", "datasetItems",
        ):
            value = raw.get(key)
            if value:
                chunks.append(_raw_search_result_to_text(value))
        if chunks:
            return "\n".join(chunks)
        try:
            return json.dumps(raw, ensure_ascii=False)
        except TypeError:
            return str(raw)
    return str(raw)


def _clean_context(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[\[\]\(\)]+", " ", text)
    return text.strip(" -|·\t\n")


def _guess_nickname(context: str, query: str = "") -> Optional[str]:
    if query and query in context:
        return query

    # Markdown 常见形态：[昵称](https://www.douyin.com/user/...)
    m = re.search(r"([#@\u4e00-\u9fa5A-Za-z0-9_.·\- ]{2,40})\s+https?://", context)
    if m:
        return m.group(1).strip(" #@-·|")

    # 兜底取 URL 前一小段可读文本。
    before = context.split("douyin.com/user/")[0]
    words = re.split(r"[|，。,:：\n]+", before)
    for word in reversed(words):
        word = word.strip(" #@-·")
        if 2 <= len(word) <= 40:
            return word
    return None


def _guess_followers_count(context: str) -> Optional[int]:
    m = re.search(r"粉丝\s*([0-9.]+)\s*([万wW千kK]?)", context)
    if not m:
        return None
    num = float(m.group(1))
    unit = m.group(2).lower()
    if unit in ("万", "w"):
        num *= 10000
    elif unit in ("千", "k"):
        num *= 1000
    return int(num)


def _score_candidate(context: str, query: str = "") -> float:
    if query and query in context:
        return 0.95
    if "douyin.com/user/" in context:
        return 0.72
    return 0.5


def format_resolution_for_question(resolution: CreatorResolution) -> List[Dict[str, str]]:
    """
    把 CreatorResolution 转成 AskUserQuestion 选项
    仅当 candidates 非空时使用
    """
    options = []
    for i, c in enumerate(resolution.candidates[:5]):
        label = c.nickname[:50]
        desc = c.signature[:80] if c.signature else f"匹配度 {c.match_score:.0%}"
        if c.followers_count:
            desc += f" · 粉丝 {c.followers_count:,}"
        options.append({"label": label, "description": desc})
    return options
