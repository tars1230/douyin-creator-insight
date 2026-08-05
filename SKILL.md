---
name: douyin-creator-insight
version: 1.3.4
description: 分析公开抖音创作者的视频主题、互动结构和代表内容，并输出 HTML、Markdown、JSON 报告。适用于研究某个抖音博主、拆解选题和内容结构；不用于收藏夹同步、私密账号或绕过平台访问控制。
---

# Douyin Creator Insight

## 使用条件

仅分析公开可访问数据。默认真实抓取使用已授权的本地浏览器 profile，不依赖 Apify key；Apify 仅是显式 fallback。不要在对话、脚本、报告或仓库中输出 token、cookie、浏览器 profile、私人绝对路径或未公开内容。

## 安装与共享配置

`douyin-creator-insight` 可独立安装和运行，`douyin-favorites-to-knowledge`（旧名/旧目录可能是 `douyin-knowledge-base-pipeline`）不是前置依赖。若两者都存在，本 skill 只复用已登录的 persistent browser profile 和 ASR 环境变量，绝不读取收藏记录、修改增量 metadata，或加入收藏 skill 的 23:00 任务。

首次运行先执行 `python3 scripts/setup.py`。它只写非敏感偏好：`cloud`（云端 ASR）/ `local`（Whisper）/ `index`（只索引），以及可选 profile/output 位置；不保存 API key、cookie 或 token。若检测到已安装 `douyin-favorites-to-knowledge`，优先复用其已登录浏览器 profile 和转录偏好，但状态、账本、输出和 23:00 任务仍完全隔离。

**云端 ASR 真相（抖音）**：抖音 CDN（`*.douyinvod.com` 等）带防盗链，**阿里云百炼 URL-ASR 服务端拉不到媒体**，会稳定失败——不是用户 Key 配错。公开 skill 的默认可用路径是：

1. **推荐 `SILICONFLOW_API_KEY`**：本机用浏览器式 `Referer: https://www.douyin.com/` 临时下载 → 抽音频 → 上传 SiliconFlow `FunAudioLLM/SenseVoiceSmall` → 立即清理临时文件。
2. **可选 `DASHSCOPE_API_KEY`**：仅当媒体 URL 是第三方可公网直链时走百炼 URL-ASR；对抖音 CDN **默认跳过**（可用 `DOUYIN_FORCE_DASHSCOPE_URL=1` 强行试）。
3. 至少配置上述之一才允许 `cloud` 真跑；**两者都缺**时停止，不下载、不静默切 Whisper。
4. 云端都失败且用户允许 local fallback 时才进 Whisper；`index` 永不 ASR。

SiliconFlow 控制台：`https://cloud.siliconflow.cn/account/ak`。百炼说明（可选）：`https://help.aliyun.com/zh/model-studio/get-api-key`。Key 放本机环境变量/Secret Manager，不要发聊天或进仓库。skill 自动读 shell、`~/.hermes/.env`、仓库 `.env` / `.env.local`。运行前 `python3 scripts/integration.py`；共享 profile 被占用必须等待。报告写入独立 `<output-root>/creator-insight/`。

> **ASR 费用（默认 SenseVoiceSmall）**：截至 **2026-08-05**，硅基流动[官方价格页](https://siliconflow.cn/pricing)将 `FunAudioLLM/SenseVoiceSmall` 标注为 **免费**（同页 `TeleSpeechASR` 亦免费；TTS 另计）。需要 `SILICONFLOW_API_KEY`。价格会变，**不承诺永久免费**；以价格页与控制台账单为准。可选百炼 `qwen3-asr-flash` 另计费（与 SiliconFlow 账单分离），且对抖音 CDN 常失败。


- **SiliconFlow 注册推荐链接**：[https://cloud.siliconflow.cn/i/1srulim9](https://cloud.siliconflow.cn/i/1srulim9)
- Key 控制台：[https://cloud.siliconflow.cn/account/ak](https://cloud.siliconflow.cn/account/ak)


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
6. `cloud`（默认）对抖音 CDN 媒体：**优先 SiliconFlow 上传 ASR**（Referer 下载 + 抽音频 + 上传 + 清理）；**不把抖音 CDN URL 默认丢给百炼**。非抖音可公网媒体才先试百炼 URL-ASR。云端都失败才进入 `local` Whisper。`douyin-mcp` 不是依赖。再用 `categorizer.py` 分类、`report_builder.py` 输出真实 provider 状态与错误。

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
| 未配置 `SILICONFLOW_API_KEY` 且未配置 `DASHSCOPE_API_KEY` | 停止真实转写；提示 SiliconFlow（抖音推荐）与可选百炼入口；不自动下载或切 Whisper |
| 仅有 `DASHSCOPE_API_KEY`、无 SiliconFlow | 允许启动但告警：抖音 CDN 转写大概率失败 |
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

### ASR 媒体与码率（1.3.4+）
- 优先 `audio_url`，失败回退 `video_url`。
- `DOUYIN_ASR_AUDIO_BITRATE`（默认 64k）、`DOUYIN_ASR_SAMPLE_RATE`（默认 16000）。
- 抖音 `music.play_url` 仅在原创音时采用，商业 BGM 不用。
- 推荐注册：https://cloud.siliconflow.cn/i/1srulim9
