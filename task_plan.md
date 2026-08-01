# Creator Insight v1.1 Plan

1. [完成] 新增不依赖 Apify 的公开博主页 collector：解析主页/短链接、在用户已授权浏览器 profile 内分页读取公开视频，并以目标 `sec_uid` 校验每条记录。
2. [完成] 将 `--browser` 作为 CLI 的显式真实模式，保留 `--adapter` 作为 Apify 或其他外部采集 fallback；昵称输入只返回候选确认需求，不自动选择账号。
3. [完成] 复用既有标准化、筛选和报告构建；浏览器模式没有显式转写 provider 时清楚标记为未转写。
4. [完成] 更新 Skill、README、变更日志和 fixtures，覆盖短链接、归属校验、失败边界与无 Apify 使用方式。
5. [完成] 本地测试与真实小样本验证通过。Claude Code 文本复审给出 2 条 `browser_collector.py` 真实问题，已修复并补回归测试；`ultrareview` unavailable 与空回包不计作审核证据。
