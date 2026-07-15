---
name: douyin-creator-insight
description: "抖音博主调研分析。从一个抖音号/昵称/主页 URL 出发，自动识别博主身份、抓取视频列表、挑选精华做语音转写、生成结构化的内容洞察报告（HTML + Markdown + JSON）。适用：'帮我分析抖音号 xxx 的 200 条视频'、'把史蒂文不做牛马做成洞察报告'、'研究某个抖音博主的爆款结构'、'分析某个抖音创作者'。"
agent_created: true
allowed-tools:
  - mcp__apify__call-actor
  - mcp__apify__get-dataset-items
  - mcp__apify__apify--rag-web-browser
  - WebSearch
  - WebFetch
  - Read
  - Write
  - Edit
  - Bash
  - AskUserQuestion
---

# Douyin Creator Insight

> 输入抖音号/昵称/主页 URL → 自动定位博主 → 抓取最新视频 → 抓取精华语音转写 → 输出结构化洞察报告

## 何时使用

- 用户给一个抖音号/昵称/主页 URL，想做系统内容分析
- 用户想研究某个抖音创作者的选题、爆款结构、内容分类
- 用户想"把这个抖音博主做成 HTML 洞察报告"

不适用于：
- 抓自己/他人的收藏夹（用 `douyin-workflow`）
- 仅抓取单条视频文案
- 抖音直播/带货分析

## 参数收集策略（自然语言优先）

优先从用户自然语言中直接提取参数，不要让用户填写复杂配置。

**必须得到**：
- `creator_query`：用户原始输入（抖音号 / 昵称 / 主页 URL）。如果用户的话里已经有目标账号，就直接使用；只有完全缺少目标时才 AskUserQuestion。

**条件必问**：
- `confirm_creator`：返回 3-5 个候选让用户选

**默认值**（用户未指定就直接采用，不必逐项追问）：
- `max_videos`：抓取视频条数，默认 200
- `transcript_count`：抓取转写条数，默认 5
- `transcript_max_duration_minutes`：转写时长上限（actor 限制），默认 5
- `research_goal`：creator_insight / 选题拆解 / 爆款分析，默认 creator_insight
- `output_formats`：html / json / md / 全部，默认全部
- `output_dir`：默认当前工作目录

当用户强调省额度、先试跑、快速看看时，建议主动降为小样本，例如 `max_videos=50`、`transcript_count=1`。当用户明确说“完整分析”或“默认跑”，使用默认 200 条视频元数据 + 5 条精华转写。

## 核心流程（5 个阶段）

```
用户自然语言输入 creator_query
  ↓
Step 1: resolver.py —— 解析博主身份
   ├─ 识别输入类型：主页 URL / sec_uid / 抖音号（6-12 位数字）/ 昵称
   ├─ 精准匹配 confidence ≥ 0.9 → 自动继续
   └─ 模糊匹配 confidence < 0.9 → AskUserQuestion 让用户选
  ↓
Step 2: parser.py —— 调用 Apify profile scraper
   ├─ 主：zen-studio/douyin-profile-scraper（不需登录）
   ├─ 备：sian.agency/douyin-scraper（需等待，5+ 分钟）
   └─ 兜底：apify--rag-web-browser 渲染主页
  ↓
Step 3: parser.py —— 标准化视频字段
   └─ 多 actor schema 差异 → 统一字段名
  ↓
Step 4: selector.py —— 选精华视频
   ├─ 互动分 = log(点赞)*1 + log(评论)*2.5 + log(分享)*3 + log(收藏)*2
   ├─ 时长过滤：transcript_max_duration_minutes 以内
   └─ 按分数降序取前 transcript_count 条
  ↓
Step 5: transcript.py —— 抓取语音转写
   ├─ 主：zen-studio/douyin-transcripts-scraper（免费版 5 分钟限制）
   ├─ 备：apple_yang/douyin-transcripts-scraper
   └─ 三种状态：success / failed / empty_transcript
  ↓
Step 6: categorizer.py —— 内容分类
   ├─ 规则标签：hashtags.name + series.name
   └─ LLM 主题分类：进外企 / 育儿 / 数码 ...
  ↓
Step 7: report_builder.py —— 输出
   ├─ HTML 报告（可视化）
   ├─ Markdown 摘要（快读）
   └─ JSON 数据包（可二次分析）
```

## 失败兜底（核心场景）

详见 `references/failure-playbook.md`：

| 失败 | 主策略 | 兜底 |
|---|---|---|
| 抖音号找不到人 | profile scraper 搜索 | WebSearch + 返回 3-5 候选 |
| 视频列表抓不到 | 重试 + 减数量 | apify--rag-web-browser 渲染主页 |
| transcript 失败 | 切换备用 actor | 跳过该视频换下一个候选 |
| transcript 为空（无旁白） | 标记 empty_transcript | 用标题+标签+互动数据 |
| Apify 额度耗尽 | 降低数量 | 提示用户上传 raw JSON 离线模式 |
| 字段 schema 变化 | parser 多字段别名 | 保留 raw JSON，不崩溃 |

## scripts/ 目录

| 文件 | 作用 | 输入 | 输出 |
|---|---|---|---|
| `resolver.py` | 抖音号/昵称/URL → 候选博主 | 用户原始输入 | 确认身份 或 候选列表 |
| `parser.py` | 字段标准化 | Apify actor 原始 JSON | `videos.normalized.json` |
| `selector.py` | 精华选择 | 标准化视频列表 | 待转写视频列表 |
| `transcript.py` | 转写标准化 | 待转写视频 + actor 返回 | 标准 transcript JSON |
| `categorizer.py` | 内容分类 | 视频 + 转写 | 分类标签 + LLM 提示词 |
| `report_builder.py` | 报告生成 | 全部数据 | HTML/MD/JSON 报告 |
| `quality_gate.py` | 数据质量门禁 | 各阶段产物 | 校验报告 |
| `schemas.py` | Pydantic 数据结构 | — | — |
| `run_pipeline.py` | 总编排 | 用户输入 | 端到端执行 |

每个脚本都可独立 dry-run（无 MCP 时走 mock 模式），便于本地测试。

## references/ 目录

| 文档 | 用途 |
|---|---|
| `pre-questions.md` | AskUserQuestion 模板和推荐默认值 |
| `apify-douyin-actors.md` | 三个 actor 用法对照（profile scraper / transcript / browser） |
| `data-schema.md` | Apify 返回字段 → 标准字段映射 |
| `creator-resolution-playbook.md` | 模糊匹配的应对策略 |
| `categorization-taxonomy.md` | 内容分类体系 |
| `report-rubric.md` | 报告标准 |
| `failure-playbook.md` | 失败场景详细手册 |

## assets/ 目录

- `report_template.html`：Jinja2 报告骨架（CSS + 章节结构）
- `report_style.css`：报告样式
- `creator_card_template.html`：博主封面卡片模板

## ⚠️ 前置条件（必看，否则跑不动）

| 依赖 | 必需？ | 说明 |
|---|---|---|
| **Apify 账号 + API Token** | ✅ **必需** | 真实抓取要走 Apify 注册：[console.apify.com/account/integrations](https://console.apify.com/account/integrations)（免费层 $5/月 ≈ 1-3 次完整调研） |
| **Apify MCP** | ✅ **必需** | WorkBuddy 客户端要装 Apify MCP，详见 `mcp.json.example` |
| **Python 3.10+** | ✅ 必需 | 用 dataclasses + typing 新语法 |
| **第三方 Python 包** | ❌ 0 依赖 | 全部用标准库实现，`pip install -r requirements.txt` 实际为空 |

**首次安装后跑不通？** 按顺序检查：

1. ✅ Apify token 已生成（[注册地址](https://console.apify.com/sign-up)，新账号 $5 免费额度）？
2. ✅ Apify MCP 已在 WorkBuddy 配置（`~/.workbuddy/mcp.json` 包含 `apify` server）？
3. ✅ Apify token 已配置到 MCP（环境变量 `APIFY_TOKEN` 或 MCP server 的 `env` 字段）？
4. ✅ Python 版本 ≥ 3.10（`python3 --version`）？

任意一步缺失 → 跑 `python run_pipeline.py` 会卡在 dry-run 模式（这是设计，不是 bug）。

## ⚡ 失败兜底速查（5 行版）

| 报错 | 90% 原因 | 一招解决 |
|---|---|---|
| `Monthly usage hard limit exceeded` | Apify 免费额度（$5/月）用完 | 等下个月初刷新 / [升级付费层](https://console.apify.com/billing) |
| `apify_caller is None / dry-run 模式` | 没装 Apify MCP 或没配 token | 装 MCP → 配 token → 重新调用 |
| `抖音号找不到人` confidence<0.9 | 昵称搜索遇到同名 | 用主页 URL 或 sec_uid（最稳）|
| `transcript 为空（empty_transcript）` | 视频本身无旁白（纯配乐） | 不影响其他视频，报告里会标注 |
| `429 Too Many Requests` | Apify 触发限流 | 等 1 分钟重试，或减少 `max_videos` |

完整失败手册：见 `references/failure-playbook.md`。

## 复用方式

### 方式 1: 作为 skill 调用

直接对 WorkBuddy 说自然语言即可，系统会自动加载本 SKILL.md 并按流程执行。

推荐输入主页链接或 `sec_uid`，最稳：

```text
用 douyin-creator-insight 分析这个抖音主页：
https://www.douyin.com/user/MS4w...
```

昵称也支持搜索，但可能遇到同名账号；如果置信度不够，必须让用户从候选里确认。

### 方式 2: 独立脚本调用

```bash
cd douyin-creator-insight
pip install -r requirements.txt

# 一键运行（需要 Apify token + 真抖音号）
python scripts/run_pipeline.py --creator <douyin_id_or_sec_uid> \
    --max-videos 200 --transcript-count 5 \
    --output-dir ./output
```

### 方式 3: 作为子模块

```python
import sys
sys.path.insert(0, 'douyin-creator-insight/scripts')
from resolver import resolve_creator
from parser import parse_videos
from selector import select_essentials
# ...
```

## 已知限制

- `zen-studio/douyin-transcripts-scraper` 免费版仅支持 5 分钟以内视频
- `bovi/douyin-scraper` 和 `sian.agency/douyin-scraper` 的 user_videos 模式需要登录 cookies（已验证 2026-07）
- Apify 抓视频列表有 200 条默认上限（`maxPostsPerProfile`）

## 数据安全

- ❌ 不要在脚本里硬编码任何真实抖音号作为测试数据（用环境变量）
- ❌ 不要在 assets/ 放真实用户的转写文本
- ✅ 用占位符（如 `<creator_query>`、`<aweme_id>`）作为示例

## 测试用例

参考真实的产出物：
- `/tmp/douyin-steven/all_videos.json`：200 条视频元数据
- `/tmp/douyin-steven/essentials_transcripts.json`：5 条精华转写

## 关联资源

- 上游：`douyin-workflow` skill（收藏夹抓取）
- 下游：可对接 `content-output` 生成 PPT/HTML 报告
