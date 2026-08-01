# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Adaptive transcript selection: accounts with 30 or fewer videos use all-video transcription; larger accounts use bounded, deduplicated layers of likes, saves, and recent posts.
- Selection metadata is included in JSON results and summarized in HTML and Markdown reports.
- Browser collection records declared work count, collected count, and pagination completion; capped collections return `partial`.
- Independent `cloud`, `local`, and `index` transcript modes. Cloud is the default, local Whisper is a final fallback, and index mode never invokes ASR.
- Non-mutating integration probe, neutral browser profile for standalone installs, shared-profile busy detection, and isolated Creator Insight output.

### Fixed
- Profile metadata extraction now prefers exact `sec_uid` matches over sec_uid-less wrapper objects.
- Profile API author metadata now wins over per-post author fields when merging declared counts and account stats.
- Timed-out or error-shaped transcript payloads are marked failed and excluded from report text.
- Missing transcript actor results now receive an explicit per-video failure status.
- Transcript quality failures return `degraded` instead of ordinary success, with provider and quality details in the result.

### Changed
- `douyin-knowledge-base-pipeline` and `douyin-mcp` are optional integrations, not installation or runtime dependencies.
- Cloud ASR first attempts DashScope URL recognition, then an optional temporary-audio cloud upload for large media; temporary media is always cleaned.

## [1.1.0] - 2026-07-30

### Added
- Browser-first public creator collection: accepts profile URLs, `sec_uid`, and complete Douyin share messages containing `v.douyin.com` links.
- `--browser`, `--browser-profile`, and `--headed` CLI options. The collector reuses the existing favorites persistent profile, fetches public post pages in browser context, locally caps and deduplicates results, and verifies every item's author `sec_uid`.

### Changed
- Apify is an explicit adapter fallback, not a default dependency for public creator collection.
- Nickname and Douyin-ID searches never auto-select an account; the workflow asks for a stable profile/share link when search is ambiguous or blocked by CAPTCHA.
- Reports state their actual collection and transcript sources. Browser-mode reports explicitly mark transcript candidates as skipped when no transcription provider is configured.

## [1.0.2] - 2026-07-25

### Changed
- Updated official GitHub Actions to their Node 24 releases to remove hosted-runner deprecation warnings.

## [1.0.1] - 2026-07-25

### Fixed
- CLI now requires explicit `--dry-run` or `--adapter module:function`; a real-looking command can no longer silently return a dry-run result.
- Added fixture-based end-to-end tests and subprocess tests for CLI exit behavior.
- Removed unbenchmarked timing, cost, quota, and free-tier promises from current documentation.

### Added
- GitHub Actions on Python 3.10 and 3.12.
- Repository checks for Skill metadata, private absolute paths, and common live-secret patterns.
- Security policy and explicit credential-handling guidance.

## [1.0.0] - 2026-07-15

### Added
- 🎉 **首次公开发布**
- 5 阶段 pipeline：resolver → parser → selector → transcript → categorizer → report_builder
- 9 个核心脚本（schemas / resolver / parser / selector / transcript / categorizer / report_builder / quality_gate / run_pipeline）
- 7 份 references 文档（pre-questions / apify-douyin-actors / data-schema / creator-resolution-playbook / categorization-taxonomy / report-rubric / failure-playbook）
- 3 套 assets 模板（report_template.html / report_style.css / creator_card_template.html）
- 三格式输出：HTML（可视化）+ Markdown（快读）+ JSON（数据分析）
- 智能精华选择：互动分公式 `log(点赞)*1 + log(评论)*2.5 + log(分享)*3 + log(收藏)*2`
- 多 actor 兜底：zen-studio 主用 → sian.agency 备选 → apify--rag-web-browser 渲染
- 模糊匹配候选：置信度 < 0.9 时返回 3-5 个候选让用户确认

### Documentation
- README.md 加 4 大徽章（License / Python 版本 / 零依赖 / Apify 必需）
- 加 demo 报告区（docs/sample-report.{html,md,json}）
- 加初版额度预估表（因缺少可复现实验依据，已在 v1.0.1 删除）
- 加 6 条 FAQ（覆盖 dry-run / 额度 / 输入选择 / empty_transcript / 私密账号 / 与 douyin-workflow 区别）
- 加环境自检脚本
- SKILL.md 加"⚠️ 前置条件"章节（4 步检查清单）
- SKILL.md 加"⚡ 失败兜底速查"表格（5 行版本）

### Notes
- 零 Python 三方依赖（用 dataclasses + 标准库）
- 需要 Apify token + Apify MCP（详见 mcp.json.example）
- 初版包含固定额度估算；v1.0.1 起改为运行前核对 Actor 页面并以本次实测为准
