# Douyin Creator Insight

从一个公开抖音主页、`sec_uid`、抖音号或昵称出发，生成可审计的创作者内容洞察报告。输出包含 HTML、Markdown 和 JSON。

[![CI](https://github.com/tars1230/douyin-creator-insight/actions/workflows/ci.yml/badge.svg)](https://github.com/tars1230/douyin-creator-insight/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## 能做什么

- 解析主页 URL、`sec_uid`、抖音号和昵称；模糊结果要求人工确认。
- 标准化不同数据源的视频字段。
- 按互动信号选择候选精华视频，并获取可用的语音转写。
- 对解析、视频数量和转写质量执行阻断式质量门。
- 生成 HTML、Markdown、JSON 三种报告。

本项目只处理公开数据，不绕过登录、隐私或平台访问控制。

## 两种运行方式

### 1. 作为 Agent Skill

这是主要用法。将仓库安装到支持 `SKILL.md` 的 agent 环境，并配置 Apify MCP。Agent 按 [SKILL.md](SKILL.md) 调用 MCP 工具，再用本仓库脚本完成解析、筛选和报告生成。

```bash
git clone https://github.com/tars1230/douyin-creator-insight.git
cp -R douyin-creator-insight ~/.workbuddy/skills/
```

`mcp.json.example` 展示 MCP 结构。真实 token 必须由环境变量或宿主的 secret store 提供，不要提交到仓库。

### 2. 作为 CLI

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
| `--creator` | 主页 URL、`sec_uid`、抖音号或昵称 | 必填 |
| `--dry-run` | 非联网解析检查 | 与 `--adapter` 二选一 |
| `--adapter` | 真实 actor adapter，`module:function` | 与 `--dry-run` 二选一 |
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

默认 actor 和 fallback 见 [references/apify-douyin-actors.md](references/apify-douyin-actors.md)。Actor 的可用性、输入 schema、价格和账户额度会变化；运行前应在对应 Apify Actor 页面核验，并先用小样本测试。仓库不承诺固定耗时、费用或免费额度。

## 输出与示例

| 文件 | 用途 |
|---|---|
| [docs/sample-report.html](docs/sample-report.html) | HTML 报告示例 |
| [docs/sample-report.md](docs/sample-report.md) | Markdown 摘要示例 |
| [docs/sample-report.json](docs/sample-report.json) | 结构化数据示例 |

报告中的互动排序是研究启发式，不代表推荐系统权重，也不构成商业、投资或平台增长保证。

## 已知边界

- 上游字段或 Actor 行为变化可能导致质量门阻断。
- 昵称搜索可能产生同名候选，低置信度结果必须人工确认。
- 无旁白、纯音乐或上游转写失败的视频可能没有 transcript。
- CLI adapter 是显式扩展点；本仓库不内置 token 读取或浏览器登录态复用。
- 私密账号、绕过访问控制和未授权批量采集不在支持范围内。

## 安全与贡献

安全问题请按 [SECURITY.md](SECURITY.md) 私下报告。开发与 PR 约定见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## License

[MIT](LICENSE)
