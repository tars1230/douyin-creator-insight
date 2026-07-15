# Assets · 模板文件

本目录存放报告生成所需的静态资源。

## 文件清单

- `README.md`：本说明
- `report_template.html`：HTML 报告模板（参考用）
- `report_style.css`：报告样式（参考用）
- `creator_card_template.html`：博主封面卡片模板（参考用）

## 当前实现

**注意**：当前 `scripts/report_builder.py` 使用内置 Python 字符串模板，**不依赖** assets/ 目录。
assets/ 中的文件仅作为参考 / 自定义起点。

## 自定义指南

如果需要自定义样式：

### 方式 1：直接修改内置模板

编辑 `scripts/report_builder.py::HTML_TEMPLATE`，调整 CSS 部分。

### 方式 2：使用 jinja2 渲染

1. 安装：`pip install jinja2`
2. 把内置 HTML_TEMPLATE 复制到 `assets/report_template.html`
3. 用 jinja2 渲染

```python
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader('assets'))
template = env.get_template('report_template.html')
html = template.render(
    nickname=nickname,
    followers=followers,
    ...
)
```

### 方式 3：完全重写

如果需要差异化设计（如杂志风、暗色模式），可以：

1. 创建新文件 `assets/report_template_magazine.html`
2. 在 `scripts/report_builder.py` 中加 `build_html_report_magazine()`
3. 调用方选择用哪个模板

## 配色参考

| 风格 | 配色 |
|---|---|
| 默认（深紫蓝） | `#1e3a8a → #5b21b6` |
| 杂志风（暖色） | `#b45309 → #d97706` |
| 暗色模式 | `#0f172a → #1e293b` |
| 极简（白底） | `#f8fafc → #f1f5f9` |

## 示例模板

### 默认模板（已在 report_builder.py）

```html
<header class="hero">
    <h1>{{ nickname }} · 抖音内容洞察报告</h1>
    <div class="creator-stats">
        <div class="stat"><span class="num">{{ followers }}</span></div>
        ...
    </div>
</header>
```

### 杂志风模板（待创建）

参考 `guizang-ppt-skill` 的杂志风风格。