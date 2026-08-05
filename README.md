# Douyin Creator Insight

从公开抖音主页、分享短链接或 `sec_uid` 出发，生成可审计的创作者内容洞察报告。默认使用已登录的本地浏览器 profile 读取公开作品；Apify 是可选 fallback。输出包含 HTML、Markdown 和 JSON。

[![CI](https://github.com/tars1230/douyin-creator-insight/actions/workflows/ci.yml/badge.svg)](https://github.com/tars1230/douyin-creator-insight/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## 能做什么

- 解析主页 URL、`sec_uid` 和完整分享文案中的短链接；昵称或抖音号只用于人工候选确认，不自动选择同名账号。
- 标准化不同数据源的视频字段。
- 按账号规模自动选择转写候选：小账号全量转写，大账号以点赞、收藏和近期作品分层抽样。
- 对解析、视频数量和转写质量执行阻断式质量门。
- 生成 HTML、Markdown、JSON 三种报告。

本项目只处理公开数据，不绕过登录、隐私或平台访问控制。

## 安装与分发入口

- Agent 一键安装：[ClawHub douyin-creator-insight](https://clawhub.ai/tars1230/skills/douyin-creator-insight)
- 国内源码镜像：[Gitee tars123/douyin-creator-insight](https://gitee.com/tars123/douyin-creator-insight)
- 源码与版本发布：[GitHub tars1230/douyin-creator-insight](https://github.com/tars1230/douyin-creator-insight)

## 运行方式

### 独立运行，可选复用收藏 skill

本 skill 可以独立安装。第一次运行先执行 `python3 scripts/setup.py`，明确选择：

- `cloud`：云端 ASR（默认）。**抖音场景推荐配置 `SILICONFLOW_API_KEY`**（本机带 Referer 临时下载 → 上传 SenseVoice → 清理）。
- `local`：本地 Whisper。只有用户明确选择时才临时下载视频，结束后清理。
- `index`：只索引标题、描述、互动数据和链接，不调用 ASR。

### 云端 ASR 重要说明（请先读）

抖音播放地址在 `*.douyinvod.com` 等 CDN 上，带防盗链。**阿里云百炼的 URL-ASR 无法从服务端下载这些地址**，会稳定返回 download 失败——这不是 API Key 坏了，也不是“测通了百炼就等于抖音能转写”。

| Key | 是否抖音刚需 | 作用 |
|---|---|---|
| **`SILICONFLOW_API_KEY`** | **是（推荐）** | 下载（`Referer: https://www.douyin.com/`）+ 上传 `FunAudioLLM/SenseVoiceSmall` |
| `DASHSCOPE_API_KEY` | 否（可选） | 仅对**可公网直链**媒体做 URL-ASR；对抖音 CDN 默认跳过 |

- SiliconFlow 控制台：[创建 API Key](https://cloud.siliconflow.cn/account/ak)
- 百炼说明（可选）：[如何获取 API Key](https://help.aliyun.com/zh/model-studio/get-api-key)

两者都缺时，`cloud` 真跑会安全停止，不下载、不静默切 Whisper。只有 `DASHSCOPE`、没有 SiliconFlow 时会告警。Key 放环境变量/Secret Manager，不要发聊天或进仓库。

skill 会自动读取当前 shell、`~/.hermes/.env`、仓库 `.env` / `.env.local` 中的相关配置，Hermes 没透传环境也能继续走 cloud 默认。

同时安装 `douyin-favorites-to-knowledge` 时，setup 会探测并优先复用它的已登录浏览器 profile 和转录偏好，但状态、输出和调度完全隔离：Creator Insight 默认写入 `./output/creator-insight/`，不读取收藏 metadata，也不加入 23:00 收藏任务。运行前执行 `python3 scripts/integration.py`；若共享 profile 已被占用，等待当前流程结束即可。`douyin-mcp` 是可选诊断工具，不是安装或运行依赖。

### 1. 本地浏览器模式（默认推荐）

首次独立使用时，本 skill 会使用中性的共享浏览器 profile；登录一次抖音即可。若已安装收藏 skill，则自动复用它现有的已登录 profile。之后可直接粘贴主页、`sec_uid`，或包含 `https://v.douyin.com/.../` 的完整分享消息：

```bash
python3 scripts/setup.py
python3 scripts/integration.py
python3 scripts/run_pipeline.py \
  --creator '长按复制此条消息，打开抖音搜索 https://v.douyin.com/xxxx/ ...' \
  --browser --max-videos 50 --output-dir ./output
```

该模式只读取公开作品列表，逐页验证每条作品作者的 `sec_uid`，不复制 cookie、不输出 profile、不绕过验证码。抖音媒体默认走 SiliconFlow 上传 ASR（Referer 下载后清理）；非抖音公网媒体可走百炼 URL ASR；全部云端失败才回退本地 Whisper。

非交互环境可以显式配置：

```bash
# 云端：保存选择；若 Key 尚未配置，真实运行会安全停止并给出申请入口
python3 scripts/setup.py --transcript-mode cloud

# 本地：只有明确选择 local 后，真实运行才允许临时下载视频
python3 scripts/setup.py --transcript-mode local

# 索引：不转录、不下载视频
python3 scripts/setup.py --transcript-mode index
```

首次使用需要可选依赖：

```bash
python3 -m pip install playwright
python3 -m playwright install chromium
```

### 2. 作为 Agent Skill 或 Apify fallback

安装到支持 `SKILL.md` 的 agent 环境后，优先走浏览器模式；没有已授权浏览器或浏览器接口异常时，才使用 Apify MCP 或下述 adapter。真实 token 必须由环境变量或宿主 secret store 提供，不要提交到仓库。

### 3. 作为 CLI adapter

CLI 不会猜测凭据，也不会把“未抓取”伪装成成功。必须显式选择以下一种模式：

```bash
# 非联网检查：只解析输入，不生成真实报告
python3 scripts/run_pipeline.py \
  --creator https://www.douyin.com/user/<sec_uid> \
  --dry-run

# 真实执行：由使用者提供 module:function adapter
PYTHONPATH=/path/to/adapters:$PYTHONPATH \
python3 scripts/run_pipeline.py \
  --creator https://www.douyin.com/user/<sec_uid> \
  --adapter my_adapter:call_actor \
  --max-videos 50 \
  --transcript-count 3 \
  --output-dir ./output
```

Adapter 必须实现以下调用契约：

```python
def call_actor(*, actor: str, input: dict, wait_secs: int):
    """Return a list of dataset items or {'datasetItems': [...]} for profile calls."""
```

昵称或抖音号还需要搜索 adapter：

```bash
python3 scripts/run_pipeline.py \
  --creator <nickname> \
  --adapter my_adapter:call_actor \
  --browser-adapter my_adapter:search_creator
```

`search_creator(*, query: str, max_results: int)` 应返回包含公开主页 URL 的文本、列表或字典。

## 参数

| 参数 | 说明 | 默认值 |
|---|---|---|
| `--creator` | 主页 URL、`sec_uid`、完整分享消息；adapter 模式也可接受抖音号或昵称 | 必填 |
| `--dry-run` | 非联网解析检查 | 与 `--browser`、`--adapter` 三选一 |
| `--browser` | 使用已授权浏览器 profile 采集公开主页 | 与 `--dry-run`、`--adapter` 三选一 |
| `--browser-profile` | 可选的 Playwright persistent profile 目录 | 默认复用 favorites profile |
| `--headed` | 显示浏览器窗口，用于诊断登录/验证码 | 默认隐藏 |
| `--adapter` | Apify 或其他外部真实采集 adapter，`module:function` | 与 `--dry-run`、`--browser` 三选一 |
| `--browser-adapter` | 昵称/抖音号搜索 adapter | 可选 |
| `--max-videos` | 请求的视频上限 | 1000 |
| `--transcript-count` | 请求的转写候选数；指定时覆盖自动分档 | 按账号规模自动选择 |
| `--transcript-mode` | `cloud` 默认 SiliconFlow 上传 ASR（抖音 CDN）+ 可选百炼公网直链 + local fallback；`local` Whisper；`index` 只做信息索引 | setup 选择，未配置时为 `cloud` |
| `--no-local-fallback` | 云端 ASR 全部失败时不回退本地 Whisper | 关闭 |
| `--max-duration` | 选择阶段的时长上限，分钟 | 5 |
| `--output-dir` | Creator Insight 专用报告目录 | `./output/creator-insight` |
| `--format` | `html json md` 的任意组合 | 全部 |

## 本地验证

测试完全使用 fixtures，不调用抖音或 Apify，也不需要 token。

```bash
python3 -m compileall -q scripts tests
python3 -m unittest discover -s tests -v
```

CI 在 Python 3.10 和 3.12 上执行同一套测试。测试覆盖：

- CLI 显式模式契约和退出码；
- dry-run 不写输出；
- 10 条 fixture 视频到三格式报告的端到端链路；
- Skill 元数据、私人绝对路径和常见 secret 模式扫描。

## 数据源与成本

浏览器模式不需要 Apify key，边界是用户已授权浏览器可访问的公开主页。默认 cloud ASR：抖音 CDN 走 SiliconFlow `SenseVoiceSmall`；百炼 `qwen3-asr-flash` 仅公网直链媒体；价格、地域和免费额度会变化，实际扣费以所用平台（SiliconFlow / 百炼）控制台账单为准。默认 actor 和 fallback 见 [references/apify-douyin-actors.md](references/apify-douyin-actors.md)。Actor 的可用性、输入 schema、价格和账户额度会变化；运行前应在对应 Apify Actor 页面核验，并先用小样本测试。仓库不承诺固定耗时、费用或免费额度。

## 输出与示例

| 文件 | 用途 |
|---|---|
| [docs/sample-report.html](docs/sample-report.html) | HTML 报告示例 |
| [docs/sample-report.md](docs/sample-report.md) | Markdown 摘要示例 |
| [docs/sample-report.json](docs/sample-report.json) | 结构化数据示例 |

报告中的互动排序是研究启发式，不代表推荐系统权重，也不构成商业、投资或平台增长保证。

## 已知边界

- 上游字段或 Actor 行为变化可能导致质量门阻断。
- 昵称搜索可能触发验证码，也可能产生同名候选；浏览器模式不会搜索或自动选择，需改贴主页或分享链接。
- 无旁白、纯音乐、未配置云端 Key 或上游转写失败的视频可能没有 transcript。未配置 `SILICONFLOW_API_KEY` 且未配置 `DASHSCOPE_API_KEY` 时真实运行会安全停止并提示官方申请入口，不会自动下载视频。
- 未指定 `--transcript-count` 时：30 条及以下全量转写；31-100 条按点赞前 50；101-300 条选 60 条；301-800 条选 80 条；更大账号最多选 100 条。大账号样本按点赞、收藏与近期作品分层去重，避免只偏向历史爆款。
- 浏览器模式会记录主页声明作品数、实际采集数和分页状态。达到请求上限而尚有下一页时，结果为 `partial`，不能作为全量结论。
- 收藏 skill 是可选共享底座，不是前置依赖；同时安装时先运行 `scripts/integration.py` 探测 profile 占用和输出布局。浏览器模式不会读取或导出 cookie。
- 私密账号、绕过访问控制和未授权批量采集不在支持范围内。

## 安全与贡献

安全问题请按 [SECURITY.md](SECURITY.md) 私下报告。开发与 PR 约定见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## License

[MIT](LICENSE)
