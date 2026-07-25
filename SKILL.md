---
name: douyin-creator-insight
description: 分析公开抖音创作者的视频主题、互动结构和代表内容，并输出 HTML、Markdown、JSON 报告。适用于研究某个抖音博主、拆解选题和内容结构；不用于收藏夹同步、私密账号或绕过平台访问控制。
agent_created: true
allowed-tools:
  - mcp__apify__call-actor
  - mcp__apify__get-dataset-items
  - mcp__apify__apify--rag-web-browser
  - WebSearch
  - WebFetch
  - Read
  - Write
  - Bash
  - AskUserQuestion
---

# Douyin Creator Insight

## 使用条件

仅分析公开可访问数据。真实抓取需要宿主已经配置 Apify MCP 和有效凭据。不要在对话、脚本、报告或仓库中输出 token、cookie、浏览器 profile、私人绝对路径或未公开内容。

Actor 的价格、配额、可用性和 schema 会变化。运行前查看当前 Actor 页面；任何费用或耗时只能作为本次运行的实测结果陈述，不能沿用固定承诺。

## 输入

从用户原话提取：

- `creator_query`：主页 URL、`sec_uid`、抖音号或昵称。缺失时才询问。
- `max_videos`：默认 200；用户要求省资源或试跑时降低。
- `transcript_count`：默认 5。
- `transcript_max_duration_minutes`：默认 5，用于候选筛选。
- `output_formats`：默认 `html`、`md`、`json`。
- `output_dir`：默认当前任务的专用输出目录。

主页 URL 或 `sec_uid` 最稳定。昵称、抖音号或低置信度解析必须展示候选，并让用户确认后继续。

## 流程

1. 用 `scripts/resolver.py` 判断输入类型。
2. 主页 URL 或 `sec_uid` 可直接形成待验证身份；昵称和抖音号通过 browser/search 工具寻找公开主页。
3. 调用 profile actor 获取视频数据。把原始响应保留在任务输出目录，不写回 Skill。
4. 用 `scripts/parser.py` 标准化字段，再执行 `quality_gate.py`。门禁失败时停止，不生成伪完整报告。
5. 用 `selector.py` 选择转写候选。排序公式只是显式启发式，不声称等同于平台算法。
6. 调用 transcript actor；失败项按 `references/failure-playbook.md` 尝试 fallback，仍失败则保留状态，不编造 transcript。
7. 用 `categorizer.py` 分类，用 `report_builder.py` 生成三种格式。
8. 返回数据源、生成时间、成功/失败计数和输出路径。

## Tool 调用契约

Profile actor 输入：

```json
{
  "maxPostsPerProfile": 50,
  "profileUrls": ["https://www.douyin.com/user/<sec_uid>"]
}
```

Actor ID、输入字段和 fallback 以 [references/apify-douyin-actors.md](references/apify-douyin-actors.md) 为准。不要假设文档中的历史 actor 永久可用；调用失败时先核对 Actor 页面和返回 schema。

## 质量门

- 身份必须 matched，且含 `sec_uid` 或抖音号。
- 视频列表不能为空；少于质量门默认阈值时阻断。
- 超过一半的视频缺少标题与描述时阻断。
- 转写成功率低于门槛时，报告必须明确降级或停止。
- 低置信度身份不得自动选择。

## 运行脚本

Agent 已经完成 MCP 调用后，可直接复用 `scripts/` 中的解析、筛选和报告函数。独立 CLI 只有两种合法模式：

```bash
# 非联网验证
python3 scripts/run_pipeline.py --creator <profile_url> --dry-run

# 使用显式 adapter 真实运行
python3 scripts/run_pipeline.py \
  --creator <profile_url> \
  --adapter my_adapter:call_actor \
  --output-dir ./output
```

没有 `--dry-run` 或 `--adapter` 时，CLI 必须失败；不得把 dry-run 返回当成真实报告。

## 失败处理

| 场景 | 行为 |
|---|---|
| 找不到账号 | 返回候选或要求更稳定的主页 URL |
| Profile actor 失败 | 核对 schema 后使用记录在 reference 中的 fallback |
| 视频不足或字段异常 | 质量门阻断，保留原始响应供排查 |
| Transcript 失败 | fallback；仍失败则标记 `failed` 或 `empty_transcript` |
| 配额不足 | 停止真实调用，建议用户缩小样本或稍后重试 |
| 输出写入失败 | 返回非成功状态和明确路径，不宣称完成 |

## 验证

修改 Skill 或脚本后必须运行：

```bash
python3 -m compileall -q scripts tests
python3 -m unittest discover -s tests -v
```

fixture E2E 通过只证明本地编排契约正确，不证明第三方 Actor 当前可用。真实发布说明必须把两类证据分开。

## 相关文档

- `references/apify-douyin-actors.md`：Actor 与 fallback
- `references/data-schema.md`：字段映射
- `references/creator-resolution-playbook.md`：身份确认
- `references/categorization-taxonomy.md`：分类规则
- `references/report-rubric.md`：报告质量
- `references/failure-playbook.md`：失败恢复
- `SECURITY.md`：凭据与漏洞报告
