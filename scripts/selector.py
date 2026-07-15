"""
Douyin Creator Insight - Engagement Selector
按互动分公式选精华视频
"""
from __future__ import annotations

import math
from typing import List
from schemas import Video, EngagementScore


# 互动分权重（按"进外企"等深度内容的特征调优）
WEIGHTS = {
    "digg": 1.0,      # 点赞
    "comment": 2.5,   # 评论（深度讨论）
    "share": 3.0,     # 分享（外传率高）
    "collect": 2.0,   # 收藏（知识性内容）
}


def score_video(video: Video) -> EngagementScore:
    """
    计算单条视频的互动分

    公式：
    score = log10(点赞+1)*1 + log10(评论+1)*2.5 + log10(分享+1)*3 + log10(收藏+1)*2
          - duration_penalty

    时长惩罚：
    - transcript_max_duration_minutes 以内：惩罚 = 0
    - 超出：每多 1 分钟，扣 0.5 分
    """
    s = video.stats

    score_breakdown = {
        "digg": math.log10(max(1, s.digg_count)) * WEIGHTS["digg"],
        "comment": math.log10(max(1, s.comment_count)) * WEIGHTS["comment"],
        "share": math.log10(max(1, s.share_count)) * WEIGHTS["share"],
        "collect": math.log10(max(1, s.collect_count)) * WEIGHTS["collect"],
    }
    base_score = sum(score_breakdown.values())

    # 时长惩罚（在 selector 调用时根据 max_duration 动态计算）
    duration_penalty = 0.0

    return EngagementScore(
        aweme_id=video.aweme_id,
        score=base_score - duration_penalty,
        breakdown=score_breakdown,
        duration_penalty=duration_penalty,
    )


def apply_duration_penalty(score: EngagementScore, duration_seconds: float, max_minutes: float) -> EngagementScore:
    """应用时长惩罚"""
    if not duration_seconds:
        return score
    max_seconds = max_minutes * 60
    if duration_seconds <= max_seconds:
        return score

    extra_minutes = (duration_seconds - max_seconds) / 60.0
    penalty = extra_minutes * 0.5

    return EngagementScore(
        aweme_id=score.aweme_id,
        score=score.score - penalty,
        breakdown=score.breakdown,
        duration_penalty=penalty,
    )


def select_essentials(
    videos: List[Video],
    top_k: int = 5,
    max_duration_minutes: float = 5.0,
) -> List[Video]:
    """
    选 top_k 条精华视频

    Args:
        videos: 标准化后的视频列表
        top_k: 返回多少条
        max_duration_minutes: 时长上限（转写 actor 限制）

    Returns:
        按分数排序的视频列表
    """
    # 1. 计算每条的分数
    scored = []
    for v in videos:
        score = score_video(v)
        if v.duration_seconds:
            score = apply_duration_penalty(score, v.duration_seconds, max_duration_minutes)
        scored.append((score.score, v, score))

    # 2. 按分数降序排序
    scored.sort(key=lambda x: x[0], reverse=True)

    # 3. 返回 top_k
    return [item[1] for item in scored[:top_k]]


def rank_top_engagement(videos: List[Video], top_k: int = 40) -> List[Video]:
    """
    按互动量排 TOP（用于报告展示）
    不考虑时长惩罚，仅按综合互动
    """
    scored = [(score_video(v).score, v) for v in videos]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [v for _, v in scored[:top_k]]