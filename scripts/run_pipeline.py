"""
Douyin Creator Insight - Pipeline 总编排
CLI 入口：python run_pipeline.py --creator <douyin_id_or_sec_uid> --max-videos 200
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Optional, Callable

# 允许脚本独立运行
sys.path.insert(0, str(Path(__file__).parent))

from schemas import PipelineReport
from resolver import (
    parse_input_type,
    resolve_creator_via_apify,
    format_resolution_for_question,
)
from parser import parse_actor_dataset, parse_toon_output
from selector import select_essentials, rank_top_engagement
from transcript import fetch_transcripts
from categorizer import categorize_videos, build_categorization_prompt
from report_builder import save_reports, build_html_report
from quality_gate import run_quality_gate


def run_pipeline(
    creator_query: str,
    max_videos: int = 200,
    transcript_count: int = 5,
    transcript_max_duration_minutes: float = 5.0,
    output_dir: str = "./output",
    output_formats: list = None,
    apify_caller: Optional[Callable] = None,
    apify_browser: Optional[Callable] = None,
):
    """
    端到端编排。

    Args:
        apify_caller: 兼容 Apify MCP 语义的调用函数；传 None 时只做 dry-run
        apify_browser: 真实的 Apify rag-web-browser 函数
    """
    if output_formats is None:
        output_formats = ["html", "json", "md"]

    print(f"🚀 开始 douyin-creator-insight pipeline")
    print(f"📌 输入: {creator_query}")
    print(f"📊 参数: max_videos={max_videos}, transcript_count={transcript_count}")
    print(f"📁 输出目录: {output_dir}")
    print()

    # Step 1: 解析 creator
    print("━" * 50)
    print("Step 1: 解析博主身份")
    print("━" * 50)
    input_type = parse_input_type(creator_query)
    print(f"   输入类型: {input_type}")

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

    if apify_caller is None:
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

    # 真实调用 Apify
    raw_result = apify_caller(
        actor="zen-studio/douyin-profile-scraper",
        input={
            "maxPostsPerProfile": max_videos,
            "profileUrls": [resolution.profile_url] if resolution.profile_url else [f"https://www.douyin.com/user/{resolution.sec_uid}"],
        },
        wait_secs=45,
    )

    # Step 3: 解析视频数据
    print("Step 3: 标准化视频数据")
    if isinstance(raw_result, dict) and "datasetItems" in raw_result:
        videos = parse_actor_dataset(raw_result["datasetItems"])
    elif isinstance(raw_result, list):
        videos = parse_actor_dataset(raw_result)
    else:
        print(f"   ❌ 无法解析返回数据")
        return None

    print(f"   ✅ 解析 {len(videos)} 条视频")
    quality = run_quality_gate("videos", videos)
    print(f"   质量门禁: {quality['message']}")
    if not quality["passed"]:
        return None
    print()

    # Step 4: 选精华视频
    print("━" * 50)
    print("Step 4: 选精华视频")
    print("━" * 50)
    essentials = select_essentials(videos, top_k=transcript_count, max_duration_minutes=transcript_max_duration_minutes)
    print(f"   选出 {len(essentials)} 条精华视频")
    for i, v in enumerate(essentials, 1):
        print(f"   {i}. {v.title or v.desc[:30]} (👍{v.stats.digg_count:,} ⭐{v.stats.collect_count:,})")
    print()

    # Step 5: 抓取转写
    print("━" * 50)
    print("Step 5: 抓取语音转写")
    print("━" * 50)
    transcripts = fetch_transcripts(essentials, apify_caller=apify_caller)
    quality = run_quality_gate("transcripts", transcripts)
    print(f"   {quality['message']}")
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
    )

    paths = save_reports(final_report, top_videos, output_dir, formats=output_formats)
    print(f"   ✅ 报告已生成:")
    for fmt, path in paths.items():
        print(f"   - {fmt}: {path}")

    return {
        "status": "success",
        "creator": resolution.nickname or resolution.douyin_id,
        "video_count": len(videos),
        "transcript_count": len(transcripts),
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
    parser.add_argument("--max-videos", type=int, default=200, help="抓取视频条数")
    parser.add_argument("--transcript-count", type=int, default=5, help="转写视频条数")
    parser.add_argument("--max-duration", type=float, default=5.0, help="转写时长上限（分钟）")
    parser.add_argument("--output-dir", default="./output", help="输出目录")
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
    parser.add_argument(
        "--browser-adapter",
        help="昵称/抖音号搜索 adapter，格式为 module:function",
    )
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

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
        output_dir=args.output_dir,
        output_formats=args.format,
        apify_caller=apify_caller,
        apify_browser=apify_browser,
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
