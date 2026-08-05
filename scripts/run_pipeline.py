"""
Douyin Creator Insight - Pipeline 总编排
CLI 入口：python run_pipeline.py --creator <douyin_id_or_sec_uid> --max-videos 200
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Optional, Callable

# 允许脚本独立运行
sys.path.insert(0, str(Path(__file__).parent))

from schemas import CreatorResolution, PipelineReport, Transcript, TranscriptStatus
from resolver import (
    extract_douyin_url,
    parse_input_type,
    resolve_creator_via_apify,
    format_resolution_for_question,
)
from parser import parse_actor_dataset, parse_toon_output
from selector import select_essentials, select_transcript_candidates, rank_top_engagement
from asr import transcribe_videos
from categorizer import categorize_videos, build_categorization_prompt
from report_builder import save_reports, build_html_report
from quality_gate import run_quality_gate
from browser_collector import collect_public_creator_sync
from integration import probe_installation
from runtime_env import ensure_runtime_env
from setup_config import BAILIAN_API_KEY_GUIDE_URL, SILICONFLOW_CONSOLE_URL, load_setup_config


def run_pipeline(
    creator_query: str,
    max_videos: int = 1000,
    transcript_count: Optional[int] = None,
    transcript_max_duration_minutes: float = 5.0,
    output_dir: str = "./output/creator-insight",
    output_formats: list = None,
    apify_caller: Optional[Callable] = None,
    apify_browser: Optional[Callable] = None,
    browser: bool = False,
    browser_profile: Optional[Path] = None,
    headed: bool = False,
    transcript_mode: str = "cloud",
    allow_local_fallback: bool = True,
    cloud_transcriber: Optional[Callable] = None,
    local_transcriber: Optional[Callable] = None,
):
    """
    端到端编排。

    Args:
        apify_caller: 兼容 Apify MCP 语义的调用函数；传 None 时只做 dry-run
        apify_browser: 真实的 Apify rag-web-browser 函数
        browser: 在用户已授权的本地浏览器 profile 内采集公开主页作品。
    """
    if output_formats is None:
        output_formats = ["html", "json", "md"]

    print(f"🚀 开始 douyin-creator-insight pipeline")
    print(f"📌 输入: {creator_query}")
    transcript_label = transcript_count if transcript_count is not None else "adaptive"
    print(f"📊 参数: max_videos={max_videos}, transcript_count={transcript_label}, transcript_mode={transcript_mode}")
    print(f"📁 输出目录: {output_dir}")
    print()

    # Step 1: 解析 creator
    print("━" * 50)
    print("Step 1: 解析博主身份")
    print("━" * 50)
    input_type = parse_input_type(creator_query)
    print(f"   输入类型: {input_type}")

    browser_items = None
    if browser:
        integration = probe_installation(profile=browser_profile, output_dir=Path(output_dir))
        if integration["conflicts"]:
            print("   ❌ 共享配置检查未通过: " + "; ".join(integration["conflicts"]))
            return None
        if input_type == "sec_uid":
            browser_input = f"https://www.douyin.com/user/{creator_query.strip()}"
        elif input_type == "url":
            browser_input = extract_douyin_url(creator_query) or creator_query.strip()
        else:
            print("   ⚠️ 浏览器模式不按昵称或抖音号自动选人，避免同名误抓。")
            print("   → 请粘贴博主页链接，或分享消息中的“查看 TA 的更多作品”短链接。")
            return None

        metadata, browser_items = collect_public_creator_sync(
            browser_input,
            max_videos=max_videos,
            profile_dir=browser_profile,
            headed=headed,
        )
        resolution = CreatorResolution(
            creator_query=creator_query,
            matched=True,
            confidence=0.95,
            sec_uid=metadata["sec_uid"],
            nickname=metadata.get("nickname") or None,
            profile_url=metadata["profile_url"],
            followers_count=metadata.get("followers_count"),
            heart_count=metadata.get("heart_count"),
            aweme_count=metadata.get("aweme_count"),
            signature=metadata.get("signature") or None,
        )
    else:
        resolution = resolve_creator_via_apify(
            creator_query, input_type,
            apify_caller=apify_caller,
            apify_browser=apify_browser,
        )

    if not resolution.matched:
        print(f"   ⚠️ 未匹配（置信度 {resolution.confidence:.0%}）")
        if resolution.candidates:
            print(f"   候选列表：")
            for c in resolution.candidates[:3]:
                print(f"   - {c.nickname} (匹配度 {c.match_score:.0%})")
            print(f"\n   → 请用 AskUserQuestion 让用户确认候选")
        return None

    print(f"   ✅ 匹配成功 (置信度 {resolution.confidence:.0%})")
    print(f"   昵称: {resolution.nickname}")
    print(f"   sec_uid: {resolution.sec_uid}")
    print()

    quality = run_quality_gate("creator", resolution)
    if not quality["passed"]:
        print(f"   ❌ 质量门禁未通过: {quality['message']}")
        return None

    # Step 2: 抓取视频列表
    print("━" * 50)
    print("Step 2: 抓取视频列表")
    print("━" * 50)

    if apify_caller is None and not browser:
        print()
        print("━" * 50)
        print("⚠️  dry-run 模式")
        print("━" * 50)
        print()
        print("📌 未调用外部服务，也不会生成真实调研报告。")
        print()
        print("✅ 后续可选：")
        print()
        print("   ① 用支持 Apify MCP 的 agent 调用本 skill")
        print("      '用 douyin-creator-insight 分析这个抖音主页：<URL>'")
        print("      → agent 按 SKILL.md 编排 MCP 工具")
        print()
        print("   ② 配 Apify MCP 后从 WorkBuddy 调用")
        print("      → 编辑 ~/.workbuddy/mcp.json（参考仓库 mcp.json.example）")
        print("      → 拿 token：https://console.apify.com/account/integrations")
        print()
        print("   ③ 用 --adapter module:function 显式注入 CLI adapter")
        print("      → 详见 README.md '作为 Python 模块' 章节")
        print()
        print("━" * 50)

        return {
            "status": "dry_run",
            "resolution": resolution.to_dict(),
            "next_steps": [
                "1. 配 Apify MCP（参考 mcp.json.example）",
                "2. 用支持 Apify MCP 的 agent 调用本 skill",
                "3. 或通过 --adapter 显式注入 CLI adapter",
            ],
        }

    collection_status = {
        "state": "unknown",
        "declared_count": None,
        "collected_count": None,
        "reconciliation": "unavailable",
        "stop_reason": None,
    }
    if browser:
        raw_result = browser_items
        actor_name = "authorized_browser_public_profile"
        collection_status = {
            "state": "complete" if metadata.get("collection_complete") else "partial",
            "declared_count": metadata.get("aweme_count"),
            "collected_count": metadata.get("collected_count"),
            "next_cursor": metadata.get("next_cursor"),
            "stop_reason": metadata.get("collection_stop_reason"),
            "declared_count_source": metadata.get("declared_count_source"),
            "reconciliation": (
                "verified" if metadata.get("aweme_count") is not None else "unavailable"
            ),
        }
    else:
        raw_result = apify_caller(
            actor="zen-studio/douyin-profile-scraper",
            input={
                "maxPostsPerProfile": max_videos,
                "profileUrls": [resolution.profile_url] if resolution.profile_url else [f"https://www.douyin.com/user/{resolution.sec_uid}"],
            },
            wait_secs=45,
        )
        actor_name = "zen-studio/douyin-profile-scraper"

    # Step 3: 解析视频数据
    print("Step 3: 标准化视频数据")
    if isinstance(raw_result, dict) and "datasetItems" in raw_result:
        videos = parse_actor_dataset(raw_result["datasetItems"], actor_name=actor_name)
    elif isinstance(raw_result, list):
        videos = parse_actor_dataset(raw_result, actor_name=actor_name)
    else:
        print(f"   ❌ 无法解析返回数据")
        return None

    print(f"   ✅ 解析 {len(videos)} 条视频")
    quality = run_quality_gate(
        "videos",
        {
            "videos": videos,
            "declared_count": collection_status.get("declared_count"),
            "collection_complete": collection_status.get("state") == "complete"
            or (
                collection_status.get("declared_count") is not None
                and collection_status.get("collected_count") is not None
                and collection_status.get("collected_count")
                >= collection_status.get("declared_count")
            ),
            "min_count": 10,
        },
    )
    print(f"   质量门禁: {quality['message']}")
    if not quality["passed"]:
        return None
    print()

    # Step 4: 选精华视频
    print("━" * 50)
    print("Step 4: 选精华视频")
    print("━" * 50)
    if transcript_mode == "index":
        essentials = []
        transcript_selection = {
            "mode": "index_only",
            "total_videos": len(videos),
            "target_count": 0,
            "selected_count": 0,
            "segments": [],
        }
    elif transcript_count is None:
        essentials, transcript_selection = select_transcript_candidates(videos)
    else:
        essentials = select_essentials(
            videos,
            top_k=min(transcript_count, len(videos)),
            max_duration_minutes=transcript_max_duration_minutes,
        )
        transcript_selection = {
            "mode": "explicit",
            "total_videos": len(videos),
            "target_count": len(essentials),
            "selected_count": len(essentials),
            "segments": [{"source": "engagement_score", "requested": transcript_count, "selected": len(essentials)}],
        }
    print(f"   选出 {len(essentials)} 条转写候选（{transcript_selection['mode']}）")
    for i, v in enumerate(essentials, 1):
        print(f"   {i}. {v.title or v.desc[:30]} (👍{v.stats.digg_count:,} ⭐{v.stats.collect_count:,})")
    print()

    # Step 5: ASR provider
    print("━" * 50)
    print("Step 5: 抓取语音转写")
    print("━" * 50)
    if transcript_mode == "index":
        transcripts, transcript_source = transcribe_videos(essentials, mode="index")
        transcript_quality = {
            "stage": "transcripts",
            "passed": True,
            "message": "index_only: ASR not requested",
        }
        print("   ✅ index-only：不调用 ASR，不下载视频")
    else:
        # ASR is independent of the collection source. Cloud receives a media
        # URL retained by the parser and never downloads it; local is explicit
        # or a fallback after cloud failure.
        transcripts, transcript_source = transcribe_videos(
            essentials,
            mode=transcript_mode,
            allow_local_fallback=allow_local_fallback,
            cloud_transcriber=cloud_transcriber,
            local_transcriber=local_transcriber,
        )
        transcript_quality = run_quality_gate("transcripts", transcripts)
        print(f"   {transcript_quality['message']}（{transcript_source}）")
    print()

    # Step 6: 内容分类
    print("━" * 50)
    print("Step 6: 内容分类")
    print("━" * 50)
    categories = categorize_videos(videos)
    print(f"   分类数: {len(categories)}")
    for cat, ids in sorted(categories.items(), key=lambda x: -len(x[1]))[:5]:
        print(f"   - {cat}: {len(ids)} 条")
    print()

    # Step 7: 生成报告
    print("━" * 50)
    print("Step 7: 生成报告")
    print("━" * 50)

    top_videos = rank_top_engagement(videos, top_k=40)
    final_report = PipelineReport(
        creator=resolution,
        videos=videos,
        transcripts=transcripts,
        categories=categories,
        engagement_top=top_videos,
        data_source=("用户已授权浏览器中的公开博主页接口" if browser else "Apify zen-studio/douyin-profile-scraper"),
        transcript_source=transcript_source,
        transcript_quality=transcript_quality,
        transcript_selection=transcript_selection,
        collection=collection_status,
    )

    paths = save_reports(final_report, top_videos, output_dir, formats=output_formats)
    print(f"   ✅ 报告已生成:")
    for fmt, path in paths.items():
        print(f"   - {fmt}: {path}")

    status = "partial" if collection_status["state"] == "partial" else (
        "success" if transcript_quality["passed"] else "degraded"
    )
    return {
        "status": status,
        "creator": resolution.nickname or resolution.douyin_id,
        "video_count": len(videos),
        "collection": collection_status,
        "transcript_count": sum(1 for transcript in transcripts if transcript.status == TranscriptStatus.SUCCESS),
        "transcript_candidate_count": len(transcripts),
        "transcript_selection": transcript_selection,
        "transcript_mode": transcript_mode,
        "transcript_source": transcript_source,
        "transcript_quality": transcript_quality,
        "output_paths": paths,
    }


def load_callable(spec: str) -> Callable:
    """Load a `module:function` adapter without guessing global credentials."""
    if ":" not in spec:
        raise ValueError("adapter must use module:function format")
    module_name, function_name = spec.rsplit(":", 1)
    module = importlib.import_module(module_name)
    adapter = getattr(module, function_name, None)
    if not callable(adapter):
        raise ValueError(f"adapter is not callable: {spec}")
    return adapter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Douyin Creator Insight Pipeline")
    parser.add_argument("--creator", required=True, help="抖音号 / 昵称 / 主页 URL")
    parser.add_argument("--max-videos", type=int, default=1000, help="抓取视频条数上限")
    parser.add_argument("--transcript-count", type=int, help="转写视频条数；未指定时按账号规模自动分档")
    parser.add_argument("--max-duration", type=float, default=5.0, help="转写时长上限（分钟）")
    parser.add_argument(
        "--transcript-mode",
        choices=("cloud", "local", "index"),
        default=None,
        help="转写模式：cloud 默认 SiliconFlow 上传 ASR（抖音 CDN）；百炼 URL 仅公网直链；local 使用临时文件 Whisper；index 只做信息索引",
    )
    parser.add_argument(
        "--no-local-fallback",
        action="store_true",
        help="云端 ASR 失败时不回退本地 Whisper",
    )
    parser.add_argument("--output-dir", help="Creator Insight 专用输出目录")
    parser.add_argument("--format", nargs="+", default=["html", "json", "md"], help="输出格式")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="只解析输入并显示后续步骤，不调用外部服务",
    )
    mode.add_argument(
        "--adapter",
        help="真实调用 adapter，格式为 module:function",
    )
    mode.add_argument(
        "--browser",
        action="store_true",
        help="使用已授权本地浏览器 profile 采集公开博主页；仅接受主页/分享链接或 sec_uid",
    )
    parser.add_argument("--browser-profile", type=Path, help="可选：浏览器 profile 目录")
    parser.add_argument("--headed", action="store_true", help="浏览器模式显示窗口，便于诊断登录或验证码")
    parser.add_argument(
        "--browser-adapter",
        help="昵称/抖音号搜索 adapter，格式为 module:function",
    )
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    ensure_runtime_env()
    try:
        setup = load_setup_config()
    except ValueError as exc:
        parser.error(str(exc))
    transcript_mode = args.transcript_mode or setup.get("transcript_mode", "cloud")
    if transcript_mode not in {"cloud", "local", "index"}:
        parser.error(f"invalid configured transcript mode: {transcript_mode}")
    allow_local_fallback = not args.no_local_fallback
    if "allow_local_fallback" in setup and args.transcript_mode is None:
        allow_local_fallback = bool(setup["allow_local_fallback"])

    silicon = bool(os.environ.get("SILICONFLOW_API_KEY"))
    dashscope = bool(os.environ.get("DASHSCOPE_API_KEY"))
    if not args.dry_run and transcript_mode == "cloud" and not (silicon or dashscope):
        print("❌ 云端 ASR 尚未配置：请至少设置 SILICONFLOW_API_KEY（抖音推荐）或 DASHSCOPE_API_KEY。")
        print("   抖音 CDN 媒体必须走 SiliconFlow 上传路径；百炼 URL ASR 拉不到 douyinvod。")
        print(f"   SiliconFlow Key：{SILICONFLOW_CONSOLE_URL}")
        print(f"   百炼申请说明（可选）：{BAILIAN_API_KEY_GUIDE_URL}")
        print("   配置后重启当前 Agent/宿主进程，再运行；或明确选择 --transcript-mode local / index。")
        print("   可先执行：python3 scripts/setup.py --transcript-mode cloud")
        return 2
    if not args.dry_run and transcript_mode == "cloud" and not silicon and dashscope:
        print("⚠️ 仅检测到 DASHSCOPE_API_KEY：对抖音 CDN 转写大概率失败。建议同时配置 SILICONFLOW_API_KEY。")
    output_dir = args.output_dir or setup.get("output_dir", "./output/creator-insight")
    browser_profile = args.browser_profile or (Path(setup["browser_profile"]) if setup.get("browser_profile") else None)

    try:
        apify_caller = load_callable(args.adapter) if args.adapter else None
        apify_browser = load_callable(args.browser_adapter) if args.browser_adapter else None
    except (ImportError, AttributeError, ValueError) as exc:
        parser.error(str(exc))

    result = run_pipeline(
        creator_query=args.creator,
        max_videos=args.max_videos,
        transcript_count=args.transcript_count,
        transcript_max_duration_minutes=args.max_duration,
        output_dir=output_dir,
        output_formats=args.format,
        apify_caller=apify_caller,
        apify_browser=apify_browser,
        browser=args.browser,
        browser_profile=browser_profile,
        headed=args.headed,
        transcript_mode=transcript_mode,
        allow_local_fallback=allow_local_fallback,
    )

    if result is None:
        return 1
    print()
    print("=" * 50)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


# Backward-compatible import for callers that used the v1.0.0 function name.
dry_run_pipeline = run_pipeline


if __name__ == "__main__":
    raise SystemExit(main())
