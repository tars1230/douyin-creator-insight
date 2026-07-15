# Report Rubric · 报告标准

## 报告结构

### HTML 报告章节

```
1. Hero（封面）
   - 博主头像 + 昵称 + sec_uid
   - 4 个数据卡片：粉丝/获赞/视频数/转写数
   - 个人简介（signature）

2. 摘要
   - 报告基于 N 条视频 + M 条转写
   - 报告时点

3. 主题分类（如有）
   - 每个分类：名称 + 视频数 + TOP 5 视频列表

4. 精华视频语音转写
   - 每条视频卡片：
     - 创建日期
     - 互动数据（点赞/收藏）
     - 转写状态（success/empty/failed）
     - 标题
     - 完整转写（可折叠）

5. 互动 TOP 视频（表格）
   - 列：# / 标题 / 日期 / 👍 / ⭐ / 💬
   - 默认 TOP 40

6. 数据来源 + 方法
   - Apify actor 列表
   - 互动分公式
   - 报告生成时间
```

### Markdown 报告章节

```
1. # 标题
2. ## 📊 账号概况（表格）
3. ## 🏷️ 主题分类（每类列表）
4. ## 🎙️ 精华视频语音转写（每条）
5. ## 🏆 互动 TOP 视频（表格）
6. ## 📖 数据来源
```

### JSON 数据包结构

```json
{
  "creator": {...},
  "videos": [...],
  "transcripts": [...],
  "categories": {...},
  "top_videos": [...],
  "research_goal": "creator_insight",
  "generated_at": "ISO 8601"
}
```

## 视觉规范

### 配色

| 用途 | 颜色 |
|---|---|
| 主背景 | 渐变 `#f5f7fa → #e8ecf3` |
| 头部 | 渐变 `#1e3a8a → #5b21b6`（深紫蓝） |
| 标题色 | `#1e293b` |
| 强调色 | `#5b21b6` |
| 链接色 | `#3730a3` |
| 警告色 | `#f59e0b` |
| 转写框 | `#fffbeb`（米黄） |
| 点赞数 | `#ef4444`（红） |
| 收藏数 | `#f59e0b`（橙） |

### 字号

| 元素 | 字号 |
|---|---|
| Hero h1 | 32px |
| section h2 | 26px |
| section h3 | 20px |
| section h4 | 17px |
| 正文 | 16px |
| 视频元信息 | 13px |

### 间距

- section padding: 50px 40px
- 卡片 padding: 14-22px
- 段落间距: 12-18px

## 数据准确度标准

### 必须保留的字段

- `aweme_id`（必填）
- `stats.digg_count` / `comment_count` / `share_count` / `collect_count`
- `create_date`（YYYY-MM-DD 格式）
- `duration_seconds`（如可用）

### 应当标注的状态

- 转写状态：`success` / `failed` / `empty_transcript` / `skipped`
- 匹配度：5★ / 4★ / 3★
- 数据来源：zen-studio / apple_yang / bovi 等

## 输出文件命名

```
{nickname}_douyin_insight_{YYYYMMDD_HHMMSS}.html
{nickname}_douyin_insight_{YYYYMMDD_HHMMSS}.md
{nickname}_douyin_insight_{YYYYMMDD_HHMMSS}.json
```

例：`史蒂文不做牛马_douyin_insight_20260709_093200.html`

## 性能基准

- 200 条视频抓取 + 5 条转写：≤ 5 分钟
- HTML 报告生成：< 2 秒
- JSON 数据包：< 1 MB

## 测试用例

参考真实产出：
- 史蒂文不做牛马：200 条视频 + 5 条精华转写 → 73 KB HTML
- TOP 40 视频列表：5.6 KB MD

## 复用模板

`scripts/report_builder.py` 内置 HTML/MD 模板，无需额外 assets/ 依赖。

如果需要自定义样式：
1. 复制 `HTML_TEMPLATE` 到 `assets/report_template.html`
2. 修改后用 `jinja2` 或其他模板引擎渲染
3. 当前实现用纯 Python `str.format()`，无 jinja 依赖