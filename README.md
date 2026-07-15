# Douyin Creator Insight

> 从一个抖音号/昵称/主页 URL 出发，自动定位博主、抓取视频列表、挑选精华做语音转写、生成结构化的内容洞察报告（HTML + Markdown + JSON）。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0-success.svg)](requirements.txt)
[![Apify Required](https://img.shields.io/badge/Apify-token_required-orange.svg)](https://console.apify.com/sign-up)

---

## ⚠️ 前置条件：需要 Apify Token

这个 skill **不依赖** 任何 Python 包，但**依赖** Apify MCP 来抓抖音数据。

**第一次使用前请准备**：

1. **注册 Apify 账号**（[console.apify.com/sign-up](https://console.apify.com/sign-up)）—— 新账号自动获得 **$5 免费额度**，够跑 1-3 次完整调研
2. **拿到 API Token**（[console.apify.com/account/integrations](https://console.apify.com/account/integrations)）—— 点 "Create new token"，复制保存
3. **在 WorkBuddy 配置 Apify MCP**（详见仓库根目录的 `mcp.json.example`）

> 💡 **零 Python 包依赖**：`pip install -r requirements.txt` 实际是空命令，skill 用 Python 标准库实现。

---

## 🎬 Demo 报告（先看产出再决定要不要跑）

| 文件 | 用途 |
|---|---|
| [`docs/sample-report.html`](docs/sample-report.html) | 真实调研产出（史蒂文不做牛马，33.3 万粉外企求职博主）|
| [`docs/sample-report.md`](docs/sample-report.md) | Markdown 摘要版 |
| [`docs/sample-report.json`](docs/sample-report.json) | JSON 数据包 |

**典型场景示例**：

> 输入：抖音主页 URL（`https://www.douyin.com/user/MS4w...`）
> 输出：HTML 报告（含博主画像 / 视频分类 / 互动 Top 40 / 转写精华 5 条）+ MD 摘要 + JSON 数据包

**典型耗时**：200 条视频 + 5 条转写 ≈ 8-15 分钟
**典型费用**：Apify 约 $1.5-2（用免费层 $5 额度够 2-3 次）

---

## ✨ 功能特性

- ✅ **身份解析**：抖音号 / sec_uid / 主页 URL / 昵称，自动判定输入类型
- ✅ **模糊匹配**：找不到人时返回 3-5 个候选让你确认
- ✅ **多 actor 兜底**：`zen-studio/douyin-profile-scraper` 主用，失败时切 `apify--rag-web-browser`
- ✅ **智能选精华**：互动分公式 `log(点赞)*1 + log(评论)*2.5 + log(分享)*3 + log(收藏)*2` + 时长惩罚
- ✅ **转写兜底**：主 `zen-studio/douyin-transcripts-scraper`，备 `apple_yang/douyin-transcripts-scraper`
- ✅ **三格式输出**：HTML（可视化）+ Markdown（快读）+ JSON（数据分析）
- ✅ **零 Python 依赖**：所有逻辑用标准库实现，10 秒配环境

---

## 🚀 快速开始（3 步上手）

### Step 1：装 Skill 到 WorkBuddy

把整个 `douyin-creator-insight/` 目录复制到 `~/.workbuddy/skills/`：

```bash
# 方式 A：从 GitHub 克隆
git clone https://github.com/tars1230/douyin-creator-insight.git
cp -r douyin-creator-insight ~/.workbuddy/skills/

# 方式 B：下载 Release zip
wget https://github.com/tars1230/douyin-creator-insight/releases/download/v1.0.0/douyin-creator-insight.zip
unzip douyin-creator-insight.zip
cp -r douyin-creator-insight ~/.workbuddy/skills/
```

### Step 2：配 Apify MCP

编辑 `~/.workbuddy/mcp.json`，添加：

```json
{
  "mcpServers": {
    "apify": {
      "command": "npx",
      "args": ["-y", "@apify/mcp-server"],
      "env": {
        "APIFY_TOKEN": "apify_api_你的token_在这里"
      }
    }
  }
}
```

→ 没 token？先去 [console.apify.com/account/integrations](https://console.apify.com/account/integrations) 创建一个

### Step 3：自然语言调用

直接在 WorkBuddy 对话里说：

```text
用 douyin-creator-insight 分析这个抖音主页：
https://www.douyin.com/user/MS4wLjABAAAANSMF3CKkdLEx_0eSkhKfkrVZtnkENxEzTSdxjmez4XGknf9tYqbsUuLJlRIEWxio
```

> 💡 推荐用主页链接或 `sec_uid`（最稳）。昵称也支持但可能遇到同名账号，会返回候选让你确认。

---

## 💰 Apify 额度预估（重要，先看再跑）

| 调研规模 | 视频条数 | 转写条数 | 预计耗时 | 预计费用 | 免费层（$5）够跑 |
|---|---|---|---|---|---|
| **小样本试跑** | 50 | 1 | 3-5 分钟 | $0.4-0.6 | 8-12 次 |
| **标准调研** | 100 | 3 | 5-10 分钟 | $0.8-1.2 | 4-6 次 |
| **完整分析** | 200 | 5 | 8-15 分钟 | $1.5-2 | 2-3 次 |
| **深度挖掘** | 200 | 10 | 15-25 分钟 | $2-3 | 1-2 次 |

> 💡 **省钱小贴士**：第一次跑用 "小样本试跑"，确认链路 OK 再跑完整调研

---

## 🧪 验证环境（30 秒自检）

跑通下面这一行 → 你的环境就 OK：

```bash
cd douyin-creator-insight && python3 -c "
import sys; sys.path.insert(0, 'scripts')
from schemas import Video, VideoStats
from selector import select_essentials
from report_builder import save_reports

videos = [Video(aweme_id='1', title='测试', stats=VideoStats(digg_count=1000, comment_count=100, collect_count=500, share_count=50, play_count=10000))]
essentials = select_essentials(videos, top_k=1)
print('✅ 基础链路 OK，能选出精华：', essentials[0].title if essentials else '无')
print('⚠️  下一步：用 WorkBuddy 调用本 skill，注入 Apify MCP 后才能真抓')
"
```

输出：
```
✅ 基础链路 OK，能选出精华：测试
⚠️  下一步：用 WorkBuddy 调用本 skill，注入 Apify MCP 后才能真抓
```

→ 这说明脚本层 OK，剩下的就是 Apify MCP 配通的问题。

---

## 🛠️ 作为 CLI 运行

CLI 主要用于本地自检和开发调试。真实抓取建议从 WorkBuddy 触发，让它注入 Apify MCP 调用。

```bash
python scripts/run_pipeline.py --creator <douyin_id_or_sec_uid> \
    --max-videos 200 \
    --transcript-count 5 \
    --output-dir ./output
```

**参数说明**：
- `--creator`：抖音号 / sec_uid / 主页 URL / 昵称
- `--max-videos`：抓取视频条数（默认 200，免费层建议先用 50）
- `--transcript-count`：转写视频条数（默认 5）
- `--max-duration`：转写时长上限分钟数（默认 5）
- `--output-dir`：输出目录（默认 `./output`）
- `--format`：输出格式 `html json md`，可多选

---

## 📦 作为 Python 模块

```python
import sys
sys.path.insert(0, 'scripts')

from resolver import parse_input_type, resolve_creator_via_apify
from parser import parse_actor_dataset
from selector import select_essentials
from report_builder import save_reports
from schemas import PipelineReport

# Step 1: 解析博主
res = resolve_creator_via_apify(creator_query, parse_input_type(creator_query))

# Step 2: 抓视频（需要传入 apify_caller）
# videos = parse_actor_dataset(...)

# Step 3: 选精华
# essentials = select_essentials(videos, top_k=5)

# Step 4: 生成报告
# save_reports(report, top_videos, output_dir)
```

---

## 📁 项目结构

```
douyin-creator-insight/
├── SKILL.md                  # Skill 入口（YAML frontmatter + 流程说明）
├── README.md                 # 本文件
├── LICENSE                   # MIT 许可证
├── CHANGELOG.md              # 版本变更记录
├── CONTRIBUTING.md           # 贡献指南
├── mcp.json.example          # WorkBuddy MCP 配置示例
├── requirements.txt          # Python 依赖（实际为空，零依赖）
├── docs/
│   ├── sample-report.html    # 示例 HTML 报告
│   ├── sample-report.md      # 示例 Markdown 摘要
│   └── sample-report.json    # 示例 JSON 数据包
├── scripts/                  # 9 个核心脚本
│   ├── schemas.py            # dataclass 数据结构（无 pydantic）
│   ├── resolver.py           # 抖音号/昵称/URL → 候选博主
│   ├── parser.py             # Apify 字段标准化
│   ├── selector.py           # 精华视频选择
│   ├── transcript.py         # 转写结果标准化
│   ├── categorizer.py        # 内容分类
│   ├── report_builder.py     # HTML/MD/JSON 报告
│   ├── quality_gate.py       # 数据质量门禁
│   └── run_pipeline.py       # 总编排 + CLI 入口
├── references/               # 7 份 markdown 文档
│   ├── pre-questions.md
│   ├── apify-douyin-actors.md
│   ├── data-schema.md
│   ├── creator-resolution-playbook.md
│   ├── categorization-taxonomy.md
│   ├── report-rubric.md
│   └── failure-playbook.md
└── assets/                   # 静态资源
    ├── report_template.html
    ├── report_style.css
    └── creator_card_template.html
```

---

## 📊 数据源

| 数据 | 来源 | 价格 |
|---|---|---|
| 视频列表 | Apify `zen-studio/douyin-profile-scraper` | $0.001/启动 + $0.007/结果 |
| 语音转写 | Apify `zen-studio/douyin-transcripts-scraper` | 免费层 5 分钟以内 |
| 网页渲染 | Apify `apify--rag-web-browser` | 按查询收费 |

详见 `references/apify-douyin-actors.md`。

---

## ❓ FAQ

<details>
<summary><b>Q1：跑 python run_pipeline.py 直接报 "dry-run 模式跳过"</b></summary>

这是设计不是 bug。CLI 默认无 Apify MCP 注入，会卡 dry-run。

**正确流程**：用 WorkBuddy 调用本 skill（自然语言），由 WorkBuddy 注入 Apify MCP。

→ 详见 SKILL.md "前置条件"
</details>

<details>
<summary><b>Q2：Apify 免费额度用完了怎么办？</b></summary>

1. **等下个月初刷新**（免费层 $5/月重置）
2. **升级付费层**：[console.apify.com/billing](https://console.apify.com/billing)（按用量付费，$0.01-0.05/视频）
3. **降低规模**：用 `--max-videos 50 --transcript-count 1` 跑小样本
</details>

<details>
<summary><b>Q3：用什么输入最稳？</b></summary>

**主页 URL**（`https://www.douyin.com/user/MS4w...`）最稳。
**sec_uid** 次之。
**抖音号**（纯数字）需要走搜索。
**昵称**最不稳（同名多）。
</details>

<details>
<summary><b>Q4：transcript 为空（empty_transcript）正常吗？</b></summary>

正常。抖音很多视频是纯配乐+字幕，无人声旁白，ASR 抓不到转写。
报告里会标注 `empty_transcript`，跳过这些视频继续下一个。
</details>

<details>
<summary><b>Q5：能抓非公开账号吗？</b></summary>

不能。本 skill 用的 actor 全部基于公开数据（无登录 cookies）。
非公开账号需要登录态，已知风险：抖音反爬严格，账号封禁概率高。
</details>

<details>
<summary><b>Q6：跟 douyin-workflow skill 有什么区别？</b></summary>

| | douyin-creator-insight（这个）| douyin-workflow |
|---|---|---|
| 目标 | 博主维度深度调研 | 个人收藏夹 / 抖音运营管线 |
| 输出 | HTML+MD+JSON 三件套 | 数据库 / 结构化数据 |
| 场景 | 研究某个 KOL 的爆款结构 | 抓自己的收藏/关注列表 |
</details>

---

## 🛡️ 失败兜底

详见 `references/failure-playbook.md`。

主要兜底策略：
- 抖音号找不到人 → 模糊匹配候选
- 视频抓不到 → 切换 `apify--rag-web-browser`
- 转写失败 → 切换备用 actor 或跳过该视频
- 字段 schema 变化 → 多别名解析

---

## 🤝 贡献

详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

主要欢迎的贡献类型：
- 新增 actor 支持（profile / transcript / browser 之外的）
- 新的内容分类体系
- 新的报告模板
- 失败场景文档化

---

## 📝 License

MIT — 详见 [LICENSE](LICENSE)。

---

## 🙏 致谢

基于实战总结。可处理任意抖音号/昵称/主页 URL。

- Apify 平台提供数据抓取能力
- 抖音开放页面提供基础数据
- WorkBuddy 平台提供 skill 运行时