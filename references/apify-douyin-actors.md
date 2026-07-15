# Apify Douyin Actors 对照表

## 三个核心 actor

### 1. `zen-studio/douyin-profile-scraper` ⭐ 主用

**用途**：抓取指定博主的所有视频列表

**输入**：
```json
{
  "maxPostsPerProfile": 200,
  "profileUrls": ["https://www.douyin.com/user/MS4w..."]
}
```

**输出字段**：
```json
[
  {
    "id": "7600998358588812742",
    "text": "视频文案/描述",
    "title": "标题",
    "createTime": 1737638400,
    "createDate": "2025-01-23",
    "statistics": {
      "diggCount": 12345,
      "commentCount": 678,
      "shareCount": 90,
      "collectCount": 234,
      "playCount": 567890
    },
    "videoMeta": {
      "duration": 120000,
      "cover": "https://..."
    },
    "hashtags": [{"name": "..."}],
    "series": {"name": "..."},
    "shareUrl": "https://...",
    "authorMeta": {
      "name": "...",
      "signature": "...",
      "followersCount": 333000,
      "heartCount": 2672708,
      "awemeCount": 200
    }
  }
]
```

**价格**：以 Apify Actor 当前页面为准。公开视频、README 和教程里不要承诺固定成本；第一次建议先小样本验证。

**限制**：maxPostsPerProfile 上限 200

**调用示例**：
```python
apify_caller(
    actor="zen-studio/douyin-profile-scraper",
    input={
        "maxPostsPerProfile": 200,
        "profileUrls": [profile_url]
    },
    wait_secs=45
)
```

### 2. `zen-studio/douyin-transcripts-scraper` ⭐ 主用转写

**用途**：抓取视频语音转写（免费版不限时长）

**输入**：
```json
{
  "targetLanguage": "zh",
  "videoUrls": ["https://www.douyin.com/video/7575296454722398441", ...]
}
```

**输出**：
```json
[
  {
    "id": "7575296454722398441",
    "caption": "...",
    "text": "完整转写文本...",
    "duration": 812,
    "segments": [{"start": 0, "end": 5.2, "text": "..."}, ...]
  }
]
```

**价格**：以 Apify Actor 当前页面为准。

**调用示例**：
```python
apify_caller(
    actor="zen-studio/douyin-transcripts-scraper",
    input={
        "targetLanguage": "zh",
        "videoUrls": [video_url1, video_url2, ...]
    },
    wait_secs=45
)
```

### 3. `apple_yang/douyin-transcripts-scraper` 备选

**用途**：更便宜的转写服务

**输入**：
```json
{
  "videoUrl": "https://www.douyin.com/video/..."
}
```

**输出**：同上

**限制**：免费版仅支持 5 分钟以内视频

**价格**：以 Apify Actor 当前页面为准。

## 备选 actor（不推荐）

### `bovi/douyin-scraper`
- 优点：功能多
- 缺点：`user_videos` 模式 2026 起需要登录 cookies，已验证空结果
- 不推荐

### `sian.agency/douyin-scraper`
- 优点：支持 userVideos
- 缺点：耗时（5+ 分钟），需要登录 cookies
- 不推荐

### `apify--rag-web-browser`
- 用途：网页搜索 + 渲染
- 兜底方案：当 profile scraper 失败时用此搜索主页
- 调用示例：
```python
apify_browser(
    query="https://www.douyin.com/user/MS4w...",
    max_results=1
)
```

## 经验教训

1. **优先用 zen-studio 系列**（不需要登录 cookies，5 分钟内返回）
2. **user_videos 模式 = 需要登录**（2026 现状）→ 慎用 bovi/sian.agency
3. **转写超时**：长视频（> 5 分钟）走付费路径，免费版超时失败
4. **TOON 格式**：Apify 返回的是 TOON 格式，需要手动解析（见 `data-schema.md`）
5. **字段 schema 不稳定**：不同 actor 返回字段名差异大，需要多别名解析（见 `parser.py::_extract_field`）

## 失败兜底顺序

```
zen-studio profile scraper (主)
  ↓ 失败
apify--rag-web-browser 渲染主页
  ↓ 失败
WebSearch + 用户手动提供数据
```

```
zen-studio transcripts scraper (主)
  ↓ 失败
apple_yang transcripts scraper (备，仅 5 分钟)
  ↓ 失败
跳过该视频，继续下一个
```
