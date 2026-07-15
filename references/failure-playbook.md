# Failure Playbook · 失败场景手册

## 1. 用户输入的抖音号找不到人

**症状**：`resolve_creator_via_apify` 返回 `matched=False`

**主策略**：
- 用 `apify--rag-web-browser` 搜索 "抖音 {creator_query}"
- 解析搜索结果，提取候选人列表

**兜底**：
- AskUserQuestion 列出 3-5 个候选，让用户确认
- 用户确认后用 sec_uid 重新调用

**关键代码位置**：`resolver.py::_resolve_via_apify_search`

## 2. 视频列表抓不到 / 返回 0 条

**症状**：`parse_actor_dataset` 返回空列表

**原因**：
- 用户输入的不是用户主页（可能是视频 URL）
- Apify 账号额度耗尽
- 抖音 API 反爬

**主策略**：
- 检查 `maxPostsPerProfile` 是否过大（> 500 容易失败）
- 重试 + 减小数量

**兜底**：
- 用 `apify--rag-web-browser` 渲染主页，手动解析
- 提示用户上传原始 JSON，走离线模式

**关键代码位置**：`run_pipeline.py` Step 2

## 3. 视频列表字段大量为空

**症状**：parse 后大部分 video.title 或 stats 为空

**原因**：
- actor schema 变化
- 字段别名没覆盖

**主策略**：
- 在 `parser.py::_extract_field` 增加新别名
- 检查 TOON 解析是否有 bug

**兜底**：
- 保留 raw JSON，下次重试时直接复用
- 用 `quality_gate.py::check_videos` 检测

## 4. 语音转写全部失败

**症状**：`fetch_transcripts` 返回空或全部 failed

**主策略**：
- 检查视频时长（> 5 分钟免费版失败）
- 切换备用 actor（apple_yang）

**兜底**：
- 仅用标题 + 描述 + 互动数据分析，不依赖转写
- 报告标注 "transcripts_unavailable"

## 5. 视频没有旁白（音乐/纯画面）

**症状**：transcript 返回空字符串

**判断**：transcript text 长度 < 10 → 标记 `empty_transcript`

**主策略**：
- 跳过该视频的转写
- 改用 title + desc + hashtags 做内容分析

**兜底**：
- 报告里标注"无旁白视频"
- 用 B 站 / YouTube 等替代来源

## 6. Apify 账号额度耗尽

**症状**：所有 actor 调用都返回 4xx 错误

**主策略**：
- 减小 `max_videos` 和 `transcript_count`
- 提示用户充值

**兜底**：
- 完全离线模式：用户上传历史 raw JSON，skill 仅做分析和报告
- WebFetch 直接抓 douyin.com 网页（绕过 API）

## 7. 字段 schema 突然变化

**症状**：解析后大量字段为 None

**主策略**：
- 增加字段别名（参考 `data-schema.md`）
- 保留 raw 字段，下次回放时排查

**兜底**：
- 用 `WebFetch` 抓主页 HTML 作为补充
- 让用户手动提供关键视频 URL

## 8. 时间相关问题

- **createTime 是毫秒还是秒**？不同 actor 不同
  - `parser.py::_format_date` 自动判断：> 10^12 是毫秒
- **时长过滤**：免费版 actor 限 5 分钟
  - `selector.py::apply_duration_penalty` 自动惩罚

## 9. 网络/TLS 错误

**症状**：MCP 调用超时或连接失败

**主策略**：
- 重试（最多 3 次）
- 切换备用 actor

**兜底**：
- WebSearch 抓搜索结果页（`apify--rag-web-browser`）
- 让用户提供手动数据

## 10. 报告生成失败

**症状**：`save_reports` 报错

**主策略**：
- 检查磁盘空间
- 检查文件权限

**兜底**：
- 只生成 JSON 格式（最小输出）
- 用 `cat > output.json` 直接写文件

## 通用诊断流程

```
1. 检查 Apify token 是否有效
2. 检查网络连接（clash verge / proxy）
3. 用 `quality_gate.run_quality_gate` 检测哪阶段失败
4. 查本 playbook 找对应失败场景
5. 实施主策略
6. 如果失败，启用兜底
7. 报告失败原因给用户
```

## 关键代码位置速查

| 失败阶段 | 主要函数 | 兜底函数 |
|---|---|---|
| 解析博主 | `resolver.resolve_creator_via_apify` | `_resolve_via_apify_search` |
| 抓视频 | `parser.parse_actor_dataset` | `apify_browser` |
| 字段解析 | `parser._extract_field` | 保留 raw |
| 选精华 | `selector.select_essentials` | 仅按点赞排序 |
| 转写 | `transcript.fetch_transcripts` | 切换 actor |
| 报告 | `report_builder.save_reports` | 单独保存 |