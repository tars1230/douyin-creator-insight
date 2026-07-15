# Creator Resolution Playbook · 博主识别策略

## 输入类型判定

`resolver.py::parse_input_type` 判定逻辑：

| 类型 | 正则 | 示例 |
|---|---|---|
| douyin_id | `^\d{6,12}$` | `<douyin_id>`（如 `12345678`） |
| sec_uid | `MS4w...` | `MS4wLjABAAA...` |
| url | `https://(www\.)?douyin\.com/user/MS4w...` | `https://www.douyin.com/user/MS4wLjABAAA...` |
| nickname | 含中英文 | `史蒂文不做牛马` |

## 精准 vs 模糊匹配

### 精准匹配（confidence ≥ 0.9）

sec_uid 直接确认，不需问用户。

```
输入: MS4wLjABAAAA...<sec_uid>...   # 抖音内部唯一 ID
→ 解析: sec_uid = MS4w...
→ confidence = 0.95
→ matched = True
→ profile_url = https://www.douyin.com/user/MS4w...
```

### 模糊匹配（confidence < 0.9）

用 `apify--rag-web-browser` 搜索：
- query: `抖音 {creator_query}`
- 解析搜索结果的 markdown
- 提取候选人列表（昵称 + 简介 + 粉丝数）

```
输入: {nickname}                 # 示例：史蒂文不做牛马
→ 搜索: 抖音 {nickname}
→ 候选 1: {nickname} · {signature} · {followers} → confidence 0.95
→ 候选 2: 其他同名账号
→ 选 #1，自动继续
```

## 失败处理

### 找不到任何人

```
输入: 不存在的昵称
→ 搜索: 返回空
→ matched = False
→ AskUserQuestion 让用户重新输入
```

### 找到多个相似

```
输入: 小李
→ 候选 5 个相似账号
→ AskUserQuestion 让用户选
→ 用户选 #3 → 用 sec_uid 继续
```

## 实战经验

### 抖音号和 sec_uid 的区别

- **抖音号**（douyin_id）：纯数字，用户可改，6-12 位
  - 例：`<douyin_id>`（如 `12345678`）
- **sec_uid**：抖音内部唯一 ID，MS4w 开头，不可改
  - 例：`MS4wLjABAAAA...`（约 60 字符长）

**profile scraper 必须用 sec_uid**，不能用抖音号。

### 已知搜不到的输入

- 短链（`v.douyin.com/xxx`）需要先 WebFetch 解析
- 长 URL（带 modal_id 参数）可能是视频 ID
- 纯数字 < 6 位大概率不是抖音号

### 实战踩坑

1. **抖音号搜不到人**：用户可能改了 douyin_id，但 sec_uid 不变。永远用 sec_uid。
2. **同名账号**：很多用户取相似昵称，需要看签名 + 粉丝数判定。
3. **博主已注销**：可能抓不到视频。提示用户确认。

## 关键代码

`scripts/resolver.py`：
- `parse_input_type(user_input)`: 识别输入类型
- `resolve_creator_via_apify(...)`: 主入口
- `_resolve_via_apify_search(...)`: 模糊匹配逻辑
- `format_resolution_for_question(...)`: 转 AskUserQuestion 选项