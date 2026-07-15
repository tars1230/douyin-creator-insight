# Contributing to Douyin Creator Insight

感谢你考虑贡献！🎉

## 🎯 主要欢迎的贡献类型

### 1. 新增 actor 支持

如果你发现更好/更便宜的 Apify actor，能替换现有 profile scraper / transcript / browser 之一，欢迎提 PR。

**修改文件**：
- `scripts/parser.py` —— 加 actor ID 别名 + 字段映射
- `scripts/transcript.py` —— 加 actor ID
- `references/apify-douyin-actors.md` —— 加对比表

### 2. 新的内容分类体系

当前分类主要覆盖：进外企 / 育儿 / 数码 / 美食 / 美妆 等。你可以根据自己研究的领域扩展。

**修改文件**：
- `scripts/categorizer.py` —— 加分类规则
- `references/categorization-taxonomy.md` —— 加分类文档

### 3. 新的报告模板

如果你做的是更专业的领域（财经 / 教育 / 二次元），可以加专属报告模板。

**修改文件**：
- `assets/report_template.html` —— 加新模板
- `assets/report_style.css` —— 加新样式
- `scripts/report_builder.py` —— 加新输出选项

### 4. 失败场景文档化

跑的时候遇到新错误？文档化它能帮后来人少踩坑。

**修改文件**：
- `references/failure-playbook.md` —— 加错误 + 一招解决

### 5. Demo 报告

跑了一个有趣的博主分析？欢迎把脱敏后的报告提交到 `docs/`。

**文件位置**：`docs/sample-report-{你的博主}.html`

**脱敏要求**：
- ❌ 删除真实抖音号 / sec_uid
- ❌ 删除真实微信号 / 手机号
- ❌ 删除可能被识别出博主身份的细节（粉丝数 / 私信记录）
- ✅ 保留：视频标题 / 转写片段 / 互动分 / 内容分类

## 🛠️ 开发流程

### 1. Fork & Clone

```bash
git clone https://github.com/你的用户名/douyin-creator-insight.git
cd douyin-creator-insight
```

### 2. 本地验证

```bash
# 跑基础链路自检（不需要 Apify）
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from schemas import Video, VideoStats
from selector import select_essentials
videos = [Video(aweme_id='1', title='t', stats=VideoStats(digg_count=1000, comment_count=100))]
print('OK:', select_essentials(videos, top_k=1))
"

# 跑端到端（需要 Apify token）
python scripts/run_pipeline.py --creator <sec_uid> --max-videos 50
```

### 3. 跑测试

```bash
# 暂无正式单元测试，先跑 README 里的 "30 秒自检"
python3 -c "import sys; sys.path.insert(0, 'scripts'); from schemas import *; print('✅ import OK')"
```

### 4. 提交 PR

PR 标题格式：
- `feat: 新增 XXX actor 支持`
- `fix: 修复 XXX 报错`
- `docs: 补充 XXX 文档`
- `style: 优化 XXX 文案`

PR 描述必须包含：
- **背景**：为什么改
- **改动**：具体改了什么
- **测试**：本地验证截图/日志
- **关联 issue**：#编号（如有）

## 📋 代码规范

- **Python 3.10+** —— 用 `dataclasses`、`typing.Optional`、`str | None` 等新语法
- **零三方依赖** —— 优先用标准库（`dataclasses` / `json` / `re` / `urllib` / `html`）
- **行宽 ≤ 100 字符**
- **中文注释** OK，函数名/变量名用英文
- **失败兜底必须做** —— 不要假设上游数据完整，加 try/except + 默认值

## 🐛 报告 Bug

[GitHub Issues](https://github.com/tars1230/douyin-creator-insight/issues/new?template=bug_report.md) 用 bug report 模板。

## 💡 提建议

[GitHub Discussions](https://github.com/tars1230/douyin-creator-insight/discussions) 开新讨论。

## 📜 行为准则

- 尊重他人
- 接受建设性批评
- 关注问题本身，不针对人
- 帮助社区新人

## 📄 License

贡献的代码默认采用 MIT License（与项目一致）。