"""Interactive first-run setup for Douyin Creator Insight."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from setup_config import (
    BAILIAN_API_KEY_GUIDE_URL,
    BAILIAN_CONSOLE_URL,
    MODES,
    detect_existing_setup,
    mode_label,
    save_setup_config,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="配置 Douyin Creator Insight 首次运行方案")
    parser.add_argument(
        "--transcript-mode",
        choices=sorted(MODES),
        help="cloud（百炼，默认推荐）/ local（Whisper）/ index（只索引）",
    )
    parser.add_argument("--config", type=Path, help="可选的本地配置路径")
    parser.add_argument("--browser-profile", type=Path, help="可选：已授权抖音浏览器 profile")
    parser.add_argument("--output-dir", type=Path, help="可选：报告输出目录")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出非敏感结果")
    return parser


def _print_cloud_action() -> None:
    print("☁️ 尚未检测到 DASHSCOPE_API_KEY。")
    print(f"申请说明（阿里云官方）：{BAILIAN_API_KEY_GUIDE_URL}")
    print(f"百炼控制台 API Key 页面：{BAILIAN_CONSOLE_URL}")
    print("创建后请把 Key 配置到本机安全环境变量或 Secret Manager，不要发送到聊天中。")
    print("macOS/Linux 示例：export DASHSCOPE_API_KEY='你的 Key'（不要把真实 Key 写进仓库）")
    print("完成后重启 Hermes/WorkBuddy/Codex 等已启动的宿主进程，再运行 check 或 pipeline。")


def _choose_mode(detected: dict) -> str:
    suggested = detected.get("favorites_transcript_mode") or "cloud"
    print("\n首次配置只需选择一次转录方案：")
    if detected["favorites_skill_installed"]:
        reuse = "已发现抖音收藏 Skill"
        if detected["shared_profile_available"]:
            reuse += "，将复用已有登录 profile"
        if detected.get("favorites_transcript_mode"):
            reuse += f"；它当前偏好 {detected['favorites_transcript_mode']}"
        print(f"ℹ️ {reuse}。Creator Insight 的状态、输出和定时任务仍保持独立。")
    if not detected["cloud_asr_configured"]:
        _print_cloud_action()
    print("\n  1. 云端百炼 ASR（推荐）")
    print("  2. 本地 Whisper（明确选择后才下载视频）")
    print("  3. 只做信息索引（不转录）")
    answer = input("请选择 [1]：").strip()
    if not answer:
        return suggested
    choices = {"1": "cloud", "2": "local", "3": "index"}
    if answer in choices:
        return choices[answer]
    if answer in MODES:
        return answer
    raise ValueError("请选择 1/2/3，或输入 cloud/local/index")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    detected = detect_existing_setup()
    mode = args.transcript_mode
    if mode is None:
        if not sys.stdin.isatty():
            raise SystemExit("非交互 setup 必须显式指定 --transcript-mode cloud|local|index")
        mode = _choose_mode(detected)
    profile = args.browser_profile or detected.get("browser_profile")
    config_path = save_setup_config(
        mode,
        path=args.config,
        browser_profile=profile,
        output_dir=args.output_dir,
    )
    result = {
        "status": "ready",
        "transcript_mode": mode,
        "transcript_mode_label": mode_label(mode),
        "config_written": True,
        "config_path": str(config_path),
        "cloud_asr_configured": detected["cloud_asr_configured"],
        "favorites_skill_installed": detected["favorites_skill_installed"],
        "shared_profile_available": detected["shared_profile_available"],
        "profile_source": detected["profile_source"],
        "next_steps": [],
    }
    if mode == "cloud" and not detected["cloud_asr_configured"]:
        result["status"] = "action_required"
        result["next_steps"] = [
            "申请并配置 DASHSCOPE_API_KEY",
            BAILIAN_API_KEY_GUIDE_URL,
            "配置后重启宿主 Agent，再运行真实 pipeline",
        ]
        if not args.json:
            _print_cloud_action()
    elif mode == "local":
        result["next_steps"] = [
            "安装 ffmpeg 和本地 Whisper 依赖",
            "首次真实运行才会下载 Whisper 模型和临时媒体",
        ]
    elif mode == "index":
        result["next_steps"] = ["可直接运行 index 模式；不会调用 ASR 或下载视频"]
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"✅ Creator Insight 配置已保存：{mode_label(mode)}")
        if detected["favorites_skill_installed"]:
            print("✅ 已识别抖音收藏 Skill；共享登录 profile/ASR 配置可复用，状态和日报任务不共享。")
        if detected["shared_profile_available"]:
            print("✅ 已发现可复用的抖音登录 profile；不会复制或输出 Cookie。")
        if mode == "cloud" and detected["cloud_asr_configured"]:
            print("✅ 已检测到云端 ASR 配置；运行时仍会以当前环境为准。")
        elif mode == "index":
            print("✅ 当前选择不会调用 ASR，也不会下载视频。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
