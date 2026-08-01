"""
Douyin Creator Insight - Quality Gate
各阶段数据质量门禁
"""
from __future__ import annotations

from typing import List, Dict, Any, Tuple
from schemas import Video, Transcript, TranscriptStatus


def check_creator_resolution(resolution) -> Tuple[bool, str]:
    """检查 creator 解析是否通过"""
    if not resolution.matched:
        return False, "creator 未匹配，请确认抖音号/昵称/URL 是否正确"
    if resolution.confidence < 0.7:
        return False, f"creator 置信度过低 ({resolution.confidence:.0%})，请手动确认"
    if not resolution.sec_uid and not resolution.douyin_id:
        return False, "creator 缺少 sec_uid 或 douyin_id，无法继续抓取"
    return True, "OK"


def check_videos(
    videos: List[Video],
    min_count: int = 10,
    declared_count: int | None = None,
    collection_complete: bool | None = None,
) -> Tuple[bool, str]:
    """检查视频列表质量。

    小账号适配：若主页声明作品数 < 默认 min_count，用声明数作门槛；
    若接口已 has_more=false 且采到 ≥ max(3, 声明数*0.7)，允许 partial 通过。
    """
    if not videos:
        return False, "视频列表为空"

    effective_min = min_count
    if declared_count is not None and declared_count > 0:
        effective_min = min(min_count, declared_count)

    n = len(videos)
    if n < effective_min:
        # partial pass for small/incomplete public lists
        floor = max(3, int((declared_count or effective_min) * 0.7))
        if collection_complete and n >= floor:
            return True, (
                f"PARTIAL OK: collected {n}"
                + (f"/{declared_count}" if declared_count else "")
                + f"（低于默认门槛 {min_count}，但接口已结束且达到 partial 底线 {floor}）"
            )
        if declared_count and declared_count < min_count and n >= max(3, declared_count - 2):
            return True, (
                f"PARTIAL OK: small account collected {n}/{declared_count} "
                f"（默认 min_count={min_count} 对小账号过严，已软通过）"
            )
        return False, f"视频数量过少 ({n} < {effective_min})，可能是抓取失败"

    # 检查是否大部分都有基础字段
    no_title = sum(1 for v in videos if not v.title and not v.desc)
    if no_title > len(videos) * 0.5:
        return False, f"超过 50% 视频缺少标题/描述，字段解析可能有问题（{no_title}/{len(videos)}）"
    return True, "OK"


def check_transcripts(transcripts: List[Transcript]) -> Tuple[bool, str]:
    """检查转写质量"""
    if not transcripts:
        return False, "无转写结果"

    success = sum(1 for t in transcripts if t.status == TranscriptStatus.SUCCESS)
    failed = sum(1 for t in transcripts if t.status == TranscriptStatus.FAILED)
    empty = sum(1 for t in transcripts if t.status == TranscriptStatus.EMPTY)

    success_rate = success / len(transcripts)
    if success_rate < 0.4:
        return False, f"转写成功率过低 ({success_rate:.0%})，可能 provider 不可用或视频无旁白"

    return True, f"成功率 {success_rate:.0%}（{success} 成功 / {failed} 失败 / {empty} 无旁白）"


def run_quality_gate(
    stage: str,
    data: Any,
) -> Dict[str, Any]:
    """
    运行指定阶段的质量门禁

    Returns:
        {
            "stage": str,
            "passed": bool,
            "message": str,
            "recommendation": str
        }
    """
    if stage == "creator":
        passed, msg = check_creator_resolution(data)
    elif stage == "videos":
        # data may be List[Video] or dict with videos + collection meta
        if isinstance(data, dict) and "videos" in data:
            passed, msg = check_videos(
                data.get("videos") or [],
                min_count=int(data.get("min_count") or 10),
                declared_count=data.get("declared_count"),
                collection_complete=data.get("collection_complete"),
            )
        else:
            passed, msg = check_videos(data)
    elif stage == "transcripts":
        passed, msg = check_transcripts(data)
    else:
        return {"stage": stage, "passed": False, "message": f"unknown stage: {stage}"}

    return {
        "stage": stage,
        "passed": passed,
        "message": msg,
        "recommendation": _get_recommendation(stage, passed, msg),
    }


def _get_recommendation(stage: str, passed: bool, msg: str) -> str:
    """根据阶段给出建议"""
    if passed:
        if stage == "videos":
            return "数据量充足，可以进入下一阶段"
        if stage == "transcripts":
            return "可以开始内容分析和报告生成"
        return ""

    recommendations = {
        "creator": "请用 AskUserQuestion 让用户确认候选博主，或重新输入抖音号",
        "videos": "检查公开主页链接、登录状态和平台响应，或降低 max_videos 重试",
        "transcripts": "尝试切换备用 actor，或跳过失败的视频用其他精华",
    }
    return recommendations.get(stage, "请检查输入数据或重试")
