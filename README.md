# Douyin Creator Insight

从公开抖音主页、分享短链接或 `sec_uid` 出发，生成可审计的创作者内容洞察报告。默认使用已登录的本地浏览器 profile 读取公开作品；Apify 是可选 fallback。输出包含 HTML、Markdown 和 JSON。

[![CI](https://github.com/tars1230/douyin-creator-insight/actions/workflows/ci.yml/badge.svg)](https://github.com/tars1230/douyin-creator-insight/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## 能做什么

- 解析主页 URL、`sec_uid` 和完整分享文案中的短链接；昵称或抖音号只用于人工候选确认，不自动选择同名账号。
- 标准化不同数据源的视频字段。
- 按互动信号选择候选精华视频，并获取可用的语音转写。
- 对解析、视频数量和转写质量执行阻断式质量门。
- 生成 HTML、Markdown、JSON 三种报告。

本项目只处理公开数据，不绕过登录、隐私或平台访问控制。

## 运行方式

### 1. 本地浏览器模式（默认推荐）

先在同一台机器完成一次 `douyin-favorites-to-knowledge login`，然后可直接粘贴主页、`sec_uid`，或包含 `https://v.douyin.com/.../` 的完整分享消息：

```bash
python3 scripts/run_pipeline.py \
  --creator '长按复制此条消息，打开抖音搜索 https://v.douyin.com/xxxx/ ...' \
  --browser --max-videos 50 --output-dir ./output
```

该模式只读取公开作品列表，逐页验证每条作品作者的 `sec_uid`，不复制 cookie、不输出 profile、不绕过验证码。它不自带转写 provider，因此报告会明确标记精华候选为 `skipped`，不会将视频文案伪装为转写。

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
| `--max-videos` | 请求的视频上限 | 200 |
| `--transcript-count` | 请求的转写候选数 | 5 |
| `--max-duration` | 选择阶段的时长上限，分钟 | 5 |
| `--output-dir` | 报告目录 | `./output` |
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

浏览器模式不需要 Apify key，边界是用户已授权浏览器可访问的公开主页。默认 actor 和 fallback 见 [references/apify-douyin-actors.md](references/apify-douyin-actors.md)。Actor 的可用性、输入 schema、价格和账户额度会变化；运行前应在对应 Apify Actor 页面核验，并先用小样本测试。仓库不承诺固定耗时、费用或免费额度。

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
- 无旁白、纯音乐或上游转写失败的视频可能没有 transcript。
- CLI adapter 是显式 fallback；浏览器模式只复用 `douyin-favorites-to-knowledge` 的 persistent profile，不读取或导出其中 cookie。
- 私密账号、绕过访问控制和未授权批量采集不在支持范围内。

## 安全与贡献

安全问题请按 [SECURITY.md](SECURITY.md) 私下报告。开发与 PR 约定见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## License

[MIT](LICENSE)
