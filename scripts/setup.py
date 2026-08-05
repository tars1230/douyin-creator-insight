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
    SILICONFLOW_CONSOLE_URL,
    SILICONFLOW_DOCS_URL,
    SILICONFLOW_PRICING_URL,
    SILICONFLOW_REFERRAL_URL,
    detect_existing_setup,
    mode_label,
    open_siliconflow_signup,
    save_setup_config,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="配置 Douyin Creator Insight 首次运行方案")
    parser.add_argument(
        "--transcript-mode",
        choices=sorted(MODES),
        help="cloud（云端 ASR，默认）/ local（Whisper）/ index（只索引）",
    )
    parser.add_argument("--config", type=Path, help="可选的本地配置路径")
    parser.add_argument("--browser-profile", type=Path, help="可选：已授权抖音浏览器 profile")
    parser.add_argument("--output-dir", type=Path, help="可选：报告输出目录")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出非敏感结果")
    return parser


def _print_cloud_action(detected: dict | None = None, *, offer_open: bool = False) -> None:
    detected = detected or {}
    print("☁️ 云端 ASR 配置（按顺序做，约 2 分钟）：")
    print("  【推荐主路径】SiliconFlow SenseVoiceSmall（抖音 CDN 唯一默认可用）")
    print("  步骤：")
    print(f"    ① 打开推荐注册/登录页（新用户走这里）：{SILICONFLOW_REFERRAL_URL}")
    print(f"    ② 登录后到控制台创建 API Key：{SILICONFLOW_CONSOLE_URL}")
    print("    ③ 本机写入环境变量（不要发聊天、不要写进仓库）：")
    print("       export SILICONFLOW_API_KEY='你的 Key'")
    print("       # 或写入 ~/.hermes/.env / 本仓库 .env.local 后重启 Agent")
    print(f"    ④ 价格参考：{SILICONFLOW_PRICING_URL}（SenseVoiceSmall 页上标注可能为免费，以账单为准）")
    print(f"    ⑤ 接口文档：{SILICONFLOW_DOCS_URL}")
    print("  【可选】DASHSCOPE_API_KEY — 仅第三方可公网直链；抖音 douyinvod 常失败，不替代上面")
    print(f"     申请：{BAILIAN_API_KEY_GUIDE_URL}")
    print(f"     控制台：{BAILIAN_CONSOLE_URL}")
    if detected.get("siliconflow_configured"):
        print("✅ 已检测到 SILICONFLOW_API_KEY")
    else:
        print("❌ 未检测到 SILICONFLOW_API_KEY（选 cloud 模式时必须配）")
        if offer_open:
            opened = open_siliconflow_signup(ask=True)
            if opened:
                print(f"✅ 已尝试打开浏览器：{SILICONFLOW_REFERRAL_URL}")
            else:
                print(f"→ 请手动打开：{SILICONFLOW_REFERRAL_URL}")
    if detected.get("dashscope_configured"):
        print("ℹ️ 已检测到 DASHSCOPE_API_KEY（非抖音公网媒体可用）")
    print("不要把真实 Key 写进仓库或发到聊天。配置后重启已启动的宿主进程。")


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
        _print_cloud_action(detected)
    print("\n  1. 云端 ASR（推荐；抖音用 SiliconFlow）")
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
        "siliconflow_configured": detected.get("siliconflow_configured", False),
        "dashscope_configured": detected.get("dashscope_configured", False),
        "favorites_skill_installed": detected["favorites_skill_installed"],
        "shared_profile_available": detected["shared_profile_available"],
        "profile_source": detected["profile_source"],
        "next_steps": [],
    }
    if mode == "cloud" and not detected["cloud_asr_configured"]:
        result["status"] = "action_required"
        result["next_steps"] = [
            "① 打开推荐注册页（新用户）：" + SILICONFLOW_REFERRAL_URL,
            "② 控制台创建 SILICONFLOW_API_KEY：" + SILICONFLOW_CONSOLE_URL,
            "③ export SILICONFLOW_API_KEY='…' 或写入 ~/.hermes/.env 后重启 Agent",
            "可选：DASHSCOPE_API_KEY（仅非抖音公网媒体 URL ASR） " + BAILIAN_API_KEY_GUIDE_URL,
            "配置后重启宿主 Agent，再运行真实 pipeline",
        ]
        result["siliconflow_referral_url"] = SILICONFLOW_REFERRAL_URL
        result["siliconflow_console_url"] = SILICONFLOW_CONSOLE_URL
        if not args.json:
            _print_cloud_action(detected, offer_open=sys.stdin.isatty())
    elif mode == "cloud" and not detected.get("siliconflow_configured"):
        result["next_steps"] = [
            "已检测到 DASHSCOPE_API_KEY，但抖音 CDN 通常仍需 SILICONFLOW_API_KEY",
            "推荐注册页：" + SILICONFLOW_REFERRAL_URL,
            "控制台建 Key：" + SILICONFLOW_CONSOLE_URL,
        ]
        result["siliconflow_referral_url"] = SILICONFLOW_REFERRAL_URL
        if not args.json:
            print("⚠️ 仅有百炼 Key 时，抖音口播转写大概率失败；请补 SILICONFLOW_API_KEY。")
            _print_cloud_action(detected, offer_open=sys.stdin.isatty())
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
            print("✅ 已检测到至少一种云端 ASR Key；运行时仍以当前环境为准。")
            if detected.get("siliconflow_configured"):
                print("✅ SiliconFlow 已配置（抖音默认可用路径）。")
            if detected.get("dashscope_configured"):
                print("ℹ️ 百炼已配置（仅对可公网直链媒体走 URL ASR）。")
        for step in result["next_steps"]:
            print(f"→ {step}")
    return 0 if result["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
