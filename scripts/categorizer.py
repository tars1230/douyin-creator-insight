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
    "职业与教育": ["求职", "面试", "简历", "职场", "学习", "英语", "课程", "考试"],
    "商业与消费": ["创业", "生意", "营销", "品牌", "产品", "价格", "省钱", "测评"],
    "生活方式": ["旅行", "美食", "穿搭", "家居", "健身", "护肤", "日常"],
    "家庭与关系": ["育儿", "宝宝", "妈妈", "亲子", "婚姻", "情感", "宠物"],
    "科技与数码": ["数码", "手机", "电脑", "AI", "软件", "科技", "评测"],
    "观点与成长": ["认知", "成长", "建议", "观点", "思考", "经验", "方法"],
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
