"""
Douyin Creator Insight - Categorizer
内容分类：规则标签 + LLM 提示词
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional
from schemas import Video, CategoryTag


# 预定义分类关键词
CATEGORY_KEYWORDS = {
    "进外企方法": ["进外企", "如何进入", "外企面试", "外企推荐", "简历", "英文", "雅思", "BEC", "外企 title"],
    "外企清单": ["外企清单", "小而美", "推荐名单", "十大城市", "十个城市", "城市知名", "最佳雇主", "福布斯"],
    "福利揭秘": ["福利", "待遇", "15 天年假", "年假", "加班", "年终奖", "六险一金", "补充医疗"],
    "跳槽/转行": ["跳槽", "转型", "转行", "准备", "实操", "拿下"],
    "英语学习": ["英语", "英文", "口语", "听力", "职场英语", "BEC"],
    "认知/成长": ["认知", "成长", "心法", "建议", "格局"],
    "母婴/育儿": ["母婴", "育儿", "宝宝", "宝贝", "妈妈"],
    "宠物/动物": ["宠物", "猫", "狗", "皇家", "玛氏"],
    "美食/食品": ["美食", "食品", "食谱", "厨房"],
    "数码/3C": ["数码", "3C", "手机", "电脑", "评测"],
}


def rule_based_tags(video: Video) -> List[CategoryTag]:
    """规则标签：基于 hashtags + title + desc"""
    tags = []
    text = (video.title or "") + " " + (video.desc or "") + " " + " ".join(video.hashtags)

    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                tags.append(CategoryTag(tag=category, source="rule"))
                break

    # 合集名也算
    if video.series_name:
        if any(kw in video.series_name for kw in ["英语", "职业", "认知"]):
            tags.append(CategoryTag(tag=f"合集: {video.series_name}", source="series"))
        else:
            tags.append(CategoryTag(tag=f"合集: {video.series_name}", source="series"))

    # 去重
    seen = set()
    unique = []
    for t in tags:
        if t.tag not in seen:
            seen.add(t.tag)
            unique.append(t)
    return unique


def build_categorization_prompt(videos_with_transcripts: List[Dict]) -> str:
    """
    构造 LLM 分类提示词
    给 LLM 调用方使用
    """
    video_summaries = []
    for i, item in enumerate(videos_with_transcripts[:30], 1):
        v: Video = item["video"]
        transcript = item.get("transcript", "")
        summary = (
            f"【视频 {i}】\n"
            f"标题: {v.title or '(无)'}\n"
            f"描述前 200 字: {(v.desc or '')[:200]}\n"
            f"hashtags: {', '.join(v.hashtags[:5]) or '(无)'}\n"
            f"互动: 点赞 {v.stats.digg_count:,} / 评论 {v.stats.comment_count:,} / 收藏 {v.stats.collect_count:,}\n"
            f"转写前 500 字: {transcript[:500]}\n"
        )
        video_summaries.append(summary)

    prompt = f"""你是一个抖音内容分析专家。请基于以下 {len(video_summaries)} 个视频的信息，把它们分到合适的类别。

# 任务
1. 输出主分类（每个视频 1 个）：进外企方法 / 外企清单 / 福利揭秘 / 跳槽转行 / 英语学习 / 母婴/育儿 / 其他
2. 提取关键洞察：
   - 博主主要面向谁（年龄/性别/职业）
   - 3 个核心主题
   - 5 条最有价值的视频标题
   - 选题公式（爆款标题的共同特征）

# 视频列表
{"".join(video_summaries)}

# 输出格式（JSON）
{{
  "main_categories": ["...主分类..."],
  "audience": "...",
  "core_themes": ["...", "...", "..."],
  "top_5_videos": ["视频标题1", "视频标题2", ...],
  "title_formula": "...",
  "insights": "..."
}}
"""
    return prompt


def categorize_videos(videos: List[Video]) -> Dict[str, List[str]]:
    """
    规则分类：返回 {类别: [video_id 列表]}
    """
    result: Dict[str, List[str]] = {}
    for v in videos:
        tags = rule_based_tags(v)
        for tag in tags:
            result.setdefault(tag.tag, []).append(v.aweme_id)
    return result


def keyword_search_videos(
    videos: List[Video],
    keyword: str,
    case_insensitive: bool = True,
) -> List[Video]:
    """按关键词筛选视频"""
    matches = []
    kw = keyword.lower() if case_insensitive else keyword
    for v in videos:
        text = ((v.title or "") + " " + (v.desc or "") + " " + " ".join(v.hashtags)).lower() if case_insensitive else ((v.title or "") + " " + (v.desc or "") + " " + " ".join(v.hashtags))
        if kw in text:
            matches.append(v)
    return matches