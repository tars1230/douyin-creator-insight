"""
Douyin Creator Insight - Schemas
数据结构定义（用 dataclasses + 简单验证，无外部依赖）
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


@dataclass
class CreatorCandidate:
    """模糊匹配候选博主"""
    nickname: str
    douyin_id: Optional[str] = None
    profile_url: Optional[str] = None
    followers_count: Optional[int] = None
    signature: Optional[str] = None
    match_score: float = 0.0


@dataclass
class CreatorResolution:
    """博主身份解析结果"""
    creator_query: str
    matched: bool = False
    confidence: float = 0.0
    sec_uid: Optional[str] = None
    douyin_id: Optional[str] = None
    nickname: Optional[str] = None
    profile_url: Optional[str] = None
    avatar_url: Optional[str] = None
    followers_count: Optional[int] = None
    heart_count: Optional[int] = None
    aweme_count: Optional[int] = None
    signature: Optional[str] = None
    candidates: List[CreatorCandidate] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "creator_query": self.creator_query,
            "matched": self.matched,
            "confidence": self.confidence,
            "sec_uid": self.sec_uid,
            "douyin_id": self.douyin_id,
            "nickname": self.nickname,
            "profile_url": self.profile_url,
            "avatar_url": self.avatar_url,
            "followers_count": self.followers_count,
            "heart_count": self.heart_count,
            "aweme_count": self.aweme_count,
            "signature": self.signature,
            "candidates": [asdict(c) for c in self.candidates],
        }


@dataclass
class VideoStats:
    """视频互动数据"""
    digg_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    collect_count: int = 0
    play_count: int = 0


@dataclass
class Video:
    """标准化后的视频"""
    aweme_id: str
    title: str = ""
    desc: str = ""
    create_time: Optional[int] = None
    create_date: Optional[str] = None
    duration_ms: Optional[int] = None
    duration_seconds: Optional[float] = None
    cover_url: Optional[str] = None
    share_url: Optional[str] = None
    hashtags: List[str] = field(default_factory=list)
    series_name: Optional[str] = None
    stats: VideoStats = field(default_factory=VideoStats)
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "aweme_id": self.aweme_id,
            "title": self.title,
            "desc": self.desc,
            "create_time": self.create_time,
            "create_date": self.create_date,
            "duration_ms": self.duration_ms,
            "duration_seconds": self.duration_seconds,
            "cover_url": self.cover_url,
            "share_url": self.share_url,
            "hashtags": self.hashtags,
            "series_name": self.series_name,
            "stats": asdict(self.stats),
            "raw": self.raw,
        }


@dataclass
class EngagementScore:
    """视频互动分"""
    aweme_id: str
    score: float
    breakdown: Dict[str, float] = field(default_factory=dict)
    duration_penalty: float = 0.0


class TranscriptStatus(str, Enum):
    """转写状态"""
    SUCCESS = "success"
    FAILED = "failed"
    EMPTY = "empty_transcript"
    SKIPPED = "skipped"


@dataclass
class Transcript:
    """视频语音转写"""
    aweme_id: str
    status: TranscriptStatus = TranscriptStatus.SKIPPED
    text: str = ""
    duration_seconds: Optional[float] = None
    segments: List[Dict[str, Any]] = field(default_factory=list)
    actor_used: Optional[str] = None
    err_msg: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "aweme_id": self.aweme_id,
            "status": self.status.value,
            "text": self.text,
            "duration_seconds": self.duration_seconds,
            "segments": self.segments,
            "actor_used": self.actor_used,
            "err_msg": self.err_msg,
        }


@dataclass
class CategoryTag:
    """内容分类标签"""
    tag: str
    source: str = "rule"
    confidence: Optional[float] = None


@dataclass
class PipelineReport:
    """最终报告"""
    creator: CreatorResolution
    videos: List[Video]
    transcripts: List[Transcript]
    categories: Dict[str, List[str]] = field(default_factory=dict)
    engagement_top: List[Video] = field(default_factory=list)
    data_source: str = "Apify profile actor"
    transcript_source: str = "Apify transcript actor"
    research_goal: str = "creator_insight"
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "creator": self.creator.to_dict(),
            "videos": [v.to_dict() for v in self.videos],
            "transcripts": [t.to_dict() for t in self.transcripts],
            "categories": self.categories,
            "engagement_top": [v.to_dict() for v in self.engagement_top],
            "data_source": self.data_source,
            "transcript_source": self.transcript_source,
            "research_goal": self.research_goal,
            "generated_at": self.generated_at.isoformat(),
        }
