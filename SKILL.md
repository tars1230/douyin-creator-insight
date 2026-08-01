---
name: douyin-creator-insight
description: 分析公开抖音创作者的视频主题、互动结构和代表内容，并输出 HTML、Markdown、JSON 报告。适用于研究某个抖音博主、拆解选题和内容结构；不用于收藏夹同步、私密账号或绕过平台访问控制。
---

# Douyin Creator Insight

## 使用条件

仅分析公开可访问数据。默认真实抓取使用已授权的本地浏览器 profile，不依赖 Apify key；Apify 仅是显式 fallback。不要在对话、脚本、报告或仓库中输出 token、cookie、浏览器 profile、私人绝对路径或未公开内容。

## 安装与共享配置

`douyin-creator-insight` 可独立安装和运行，`douyin-favorites-to-knowledge`（旧名/旧目录可能是 `douyin-knowledge-base-pipeline`）不是前置依赖。若两者都存在，本 skill 只复用已登录的 persistent browser profile 和 ASR 环境变量，绝不读取收藏记录、修改增量 metadata，或加入收藏 skill 的 23:00 任务。

首次运行先执行 `python3 scripts/setup.py`。它只写非敏感偏好：`cloud`（百炼，推荐）/ `local`（Whisper）/ `index`（只索引），以及可选 profile/output 位置；不保存 API key、cookie 或 token。若检测到已安装 `douyin-favorites-to-knowledge`，优先复用其已登录浏览器 profile 和转录偏好，但状态、账本、输出和 23:00 任务仍完全隔离。若选择 `cloud` 且未检测到 `DASHSCOPE_API_KEY`，setup 和真实运行都必须提示阿里云百炼官方 API Key 申请说明 `https://help.aliyun.com/zh/model-studio/get-api-key`，让用户把 Key 放到本机安全环境变量/Secret Manager；在 Key 缺失时不得自动下载视频或静默切本地 Whisper。配置好 `DASHSCOPE_API_KEY` 后，默认把媒体 URL 交给百炼，不下载视频；若百炼拒绝大视频且配置了 `SILICONFLOW_API_KEY`，可临时下载并上传音频到另一个云端 ASR，完成即清理。只有云端已配置但真实调用失败时才回退 `local`；`index` 永不调用 ASR。skill 会自动读取当前 shell、`~/.hermes/.env`、仓库 `.env` / `.env.local` 中的相关配置，Hermes 没透传环境也能继续走 cloud 默认。运行前先执行 `python3 scripts/integration.py`：它只读探测共享 profile、输出布局与占用状态；若 profile 正在被收藏任务使用，必须等待，不能并发打开 Chromium persistent profile。报告写入独立的 `<output-root>/creator-insight/`，不要求配置飞书或 Obsidian。

Actor 的价格、配额、可用性和 schema 会变化。运行前查看当前 Actor 页面；任何费用或耗时只能作为本次运行的实测结果陈述，不能沿用固定承诺。

## 输入

从用户原话提取：

- `creator_query`：优先主页 URL、`sec_uid`，或包含 `v.douyin.com` 的完整分享消息；脚本会提取短链接。
- `max_videos`：默认 1000；用户要求省资源或试跑时降低。超过上限时结果必须标为 `partial`。
- `transcript_count`：未指定时按作品数自动分档；用户显式指定时优先遵从。
- `transcript_max_duration_minutes`：默认 5，用于候选筛选。
- `transcript_mode`：`cloud`（默认）/ `local` / `index`。
- `output_formats`：默认 `html`、`md`、`json`。
- `output_dir`：默认当前任务的专用输出目录。

主页 URL、分享短链接或 `sec_uid` 最稳定。昵称和抖音号只可用于候选确认，不能自动选择同名账号；搜索验证码或模糊结果时要求用户改贴主页/分享链接。

## 流程

1. 用 `scripts/resolver.py` 判断输入类型，并从分享消息提取短链接。
2. 对 URL/短链接/`sec_uid`，优先运行 `scripts/run_pipeline.py --browser`。它在现有 persistent profile 的页面上下文读取公开作品分页，并验证每条返回视频的作者 `sec_uid`。
3. 昵称或抖音号不可自动选人；搜索触发验证码、无候选或多个候选时停止并请求主页/分享链接。
4. 用 `scripts/parser.py` 标准化字段，再执行 `quality_gate.py`。门禁失败时停止，不生成伪完整报告。
5. `index` 模式跳过转写，只保留全量作品信息；其他模式用 `selector.py` 选择候选：30 条及以下全量转写；31-100 条按点赞前 50；更大账号按点赞、收藏和近期作品分层去重抽样（上限 100 条）。
6. `cloud`（默认）先把浏览器接口提供的媒体 URL 发送给百炼兼容 ASR；大文件可走临时音频上传的云端 fallback，随后清理。只有云端都失败才进入 `local` 的 Whisper。`douyin-mcp` 不是依赖；它本身也是“下载临时视频 -> 提取音频 -> 上传云端”，因此不作为本 skill 的正常路径。再用 `categorizer.py` 分类、`report_builder.py` 输出真实 provider 状态与错误。

## Tool 调用契约

Profile actor 输入：

```json
{
  "maxPostsPerProfile": 1000,
  "profileUrls": ["https://www.douyin.com/user/<sec_uid>"]
}
```

浏览器模式默认最多采集 1000 条；Apify 的实际上限、配额和字段以运行时 Actor schema 为准。任何触发上限、分页未完成或声明数无法对账的结果，都必须在报告的 `collection` 字段标为 `partial` 或 `reconciliation: unavailable`，不得写成全量完成。

Actor ID、输入字段和 fallback 以 [references/apify-douyin-actors.md](references/apify-douyin-actors.md) 为准。不要假设文档中的历史 actor 永久可用；调用失败时先核对 Actor 页面和返回 schema。

## 质量门

- 身份必须 matched，且含 `sec_uid` 或抖音号。
- 视频列表不能为空；少于质量门默认阈值时阻断。
- 超过一半的视频缺少标题与描述时阻断。
- 转写成功率低于门槛时，报告必须明确降级或停止。
- 低置信度身份不得自动选择。

## 运行脚本

Agent 已经完成采集后，可直接复用 `scripts/` 中的解析、筛选和报告函数。独立 CLI 必须显式选择一种模式：

```bash
# 非联网验证
python3 scripts/run_pipeline.py --creator <profile_url> --dry-run

# 默认真实路径：已登录浏览器中的公开主页接口
python3 scripts/setup.py
python3 scripts/integration.py
python3 scripts/run_pipeline.py --creator '<share_or_profile_url>' --browser

# 明确选择本地 Whisper 或纯信息索引
python3 scripts/run_pipeline.py --creator '<profile_url>' --browser --transcript-mode local
python3 scripts/run_pipeline.py --creator '<profile_url>' --browser --transcript-mode index

# 使用显式 adapter 真实运行
python3 scripts/run_pipeline.py \
  --creator <profile_url> \
  --adapter my_adapter:call_actor \
  --output-dir ./output
```

没有 `--dry-run`、`--browser` 或 `--adapter` 时，CLI 必须失败；不得把 dry-run 返回当成真实报告。

## 失败处理

| 场景 | 行为 |
|---|---|
| 找不到账号 | 返回候选或要求更稳定的主页 URL |
| 浏览器 profile 未登录、主页接口失败 | 不要求复制 cookie；提示在已有 profile 中恢复登录或稍后重试 |
| 昵称搜索验证码/同名 | 不绕过验证码，不自动选人；要求主页或分享链接 |
| Profile actor 失败 | 核对 schema 后使用记录在 reference 中的 fallback |
| 视频不足或字段异常 | 质量门阻断，保留原始响应供排查 |
| 未配置 `DASHSCOPE_API_KEY` | 停止真实转写，提示百炼 API Key 官方申请入口；不自动下载视频或切本地 Whisper |
| Cloud ASR 失败 | 仅在云端已配置但真实调用失败时记录错误，再回退本地 Whisper；`--no-local-fallback` 时只报告失败 |
| 本地 Whisper 失败 | 清理临时媒体并标记 `failed` 或 `empty_transcript` |
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
