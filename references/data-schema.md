# Data Schema · 字段映射

## Apify profile scraper → 标准化字段

不同 actor 字段名差异（已实测）：

| 标准化字段 | zen-studio | bovi | sian.agency | TOON 解析后 |
|---|---|---|---|---|
| aweme_id | id | aweme_id | videoId | id |
| title | title | (空) | (空) | title |
| desc | text | desc | desc | text |
| create_time | createTime | create_time | timestamp | createTime |
| duration_ms | videoMeta.duration | video.duration | duration | videoMeta.duration |
| cover_url | videoMeta.cover | video.cover | coverUrl | videoMeta.cover |
| share_url | shareUrl | share_url | url | shareUrl |
| hashtags | hashtags[].name | (空) | (空) | hashtags.name |
| series_name | series.name | (空) | (空) | series.name |
| digg_count | statistics.diggCount | aweme_stats.digg_count | stats.like | statistics.diggCount |
| comment_count | statistics.commentCount | aweme_stats.comment_count | stats.comment | statistics.commentCount |
| share_count | statistics.shareCount | aweme_stats.share_count | stats.share | statistics.shareCount |
| collect_count | statistics.collectCount | aweme_stats.collect_count | stats.favorite | statistics.collectCount |
| play_count | statistics.playCount | aweme_stats.play_count | stats.view | statistics.playCount |

## TOON 格式示例

Apify `get_dataset_items` 返回的是 TOON 格式（不是 JSON）：

```toon
items[200]:
  - id: "7600998358588812742"
    text: "进外企真的不难"
    createTime: 1737638400
    statistics:
      diggCount: 42451
      commentCount: 1500
      shareCount: 800
      collectCount: 24647
    videoMeta:
      duration: 240000
      cover: "https://..."
    hashtags:
      - name: "外企"
      - name: "求职"
    authorMeta:
      name: "史蒂文不做牛马"
      signature: "在七种不同国别外企混迹的牛马一枚"
      followersCount: 333000
      heartCount: 2672708
```

## 解析规则

`scripts/parser.py::parse_toon_output` 实现：
1. 用 `items[N]:` 作为块起点
2. 用 `\n  - id:` 作为分隔符切分 item
3. 每行按 4 空格缩进解析 key-value
4. 多层缩进（如 `statistics.diggCount`）用 `.` 合并为路径

## transcripts scraper 输出

zen-studio transcripts 返回格式：

```json
[
  {
    "id": "7575296454722398441",
    "caption": "视频标题",
    "text": "完整转写文本",
    "duration": 812,
    "segments": [
      {"start": 0.0, "end": 5.2, "text": "..."},
      ...
    ],
    "errMsg": null
  }
]
```

## 字段映射实现位置

`scripts/parser.py::_extract_field()` 支持多路径：

```python
_extract_field(item, [
    "statistics.diggCount",  # zen-studio
    "aweme_stats.digg_count",  # bovi
    "stats.diggCount",  # sian.agency
])
```

按顺序尝试，找到第一个非空值。