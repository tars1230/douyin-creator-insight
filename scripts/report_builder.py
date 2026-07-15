"""
Douyin Creator Insight - Report Builder
生成 HTML / Markdown / JSON 报告
无外部依赖（用纯 Python 字符串格式化）
"""
from __future__ import annotations

import json
import html
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from schemas import PipelineReport, Video


# 内置 HTML 模板
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{nickname} · 抖音内容洞察报告</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
    background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf3 100%);
    color: #1a202c; line-height: 1.7; font-size: 15px;
}}
.container {{ max-width: 920px; margin: 0 auto; background: white; box-shadow: 0 0 30px rgba(0,0,0,.06); }}
header.hero {{
    background: linear-gradient(135deg, #1e3a8a 0%, #5b21b6 100%);
    color: white; padding: 50px 40px 40px;
}}
header h1 {{ font-size: 28px; margin-bottom: 8px; }}
header .subtitle {{ font-size: 14px; opacity: 0.85; margin-bottom: 20px; }}
.creator-stats {{
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px;
    background: rgba(255,255,255,.12); padding: 18px; border-radius: 12px;
}}
.stat .num {{ font-size: 22px; font-weight: 700; display: block; }}
.stat .lbl {{ font-size: 12px; opacity: 0.85; margin-top: 4px; }}
section {{ padding: 40px; border-bottom: 1px solid #e2e8f0; }}
section h2 {{
    font-size: 22px; color: #1e293b; margin-bottom: 14px;
    padding-bottom: 10px; border-bottom: 3px solid #5b21b6; display: inline-block;
}}
section h3 {{ font-size: 17px; color: #1e293b; margin: 20px 0 10px; padding-left: 12px; border-left: 4px solid #5b21b6; }}
.video-card {{
    background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px;
    padding: 14px 18px; margin: 12px 0;
}}
.video-meta {{ display: flex; gap: 12px; font-size: 12px; color: #64748b; margin-bottom: 6px; flex-wrap: wrap; }}
.video-meta .likes {{ color: #ef4444; font-weight: 600; }}
.video-meta .collects {{ color: #f59e0b; font-weight: 600; }}
.transcript-box {{
    background: #fffbeb; border-left: 3px solid #f59e0b;
    padding: 12px 16px; margin-top: 10px; border-radius: 6px;
    font-size: 14px;
}}
.toggle-btn {{
    background: #5b21b6; color: white; border: none;
    padding: 5px 12px; border-radius: 5px; font-size: 12px;
    cursor: pointer; margin-top: 8px;
}}
.tag {{
    display: inline-block; padding: 2px 8px; background: #ede9fe;
    color: #5b21b6; border-radius: 10px; font-size: 11px; margin-right: 4px;
}}
table {{ width: 100%; border-collapse: collapse; margin: 14px 0; font-size: 13px; }}
th {{ background: #1e3a8a; color: white; padding: 9px; text-align: left; font-weight: 600; font-size: 12px; }}
td {{ padding: 8px; border-bottom: 1px solid #e2e8f0; color: #334155; }}
.likes {{ color: #ef4444; font-weight: 600; }}
.collects {{ color: #f59e0b; font-weight: 600; }}
footer {{ background: #0f172a; color: #94a3b8; padding: 28px 40px; text-align: center; font-size: 12px; }}
</style>
</head>
<body>
<div class="container">

<header class="hero">
    <h1>📊 {nickname} · 抖音内容洞察报告</h1>
    <div class="subtitle">{research_goal} · 数据时点 {generated_at}</div>
    <div class="creator-stats">
        <div class="stat"><span class="num">{followers}</span><span class="lbl">粉丝</span></div>
        <div class="stat"><span class="num">{hearts}</span><span class="lbl">累计获赞</span></div>
        <div class="stat"><span class="num">{video_count}</span><span class="lbl">视频数</span></div>
        <div class="stat"><span class="num">{transcript_count}</span><span class="lbl">抓取转写</span></div>
    </div>
    {signature_html}
</header>

<section>
    <h2>📑 摘要</h2>
    <p>本报告基于 <strong>{video_count} 条最新视频</strong> + <strong>{transcript_count} 条精华语音转写</strong>生成。</p>
    <p><strong>采集账号：</strong>{nickname}</p>
    <p><strong>sec_uid：</strong><code>{sec_uid}</code></p>
    <p><strong>报告时点：</strong>{generated_at}</p>
</section>

{categories_section}

{transcripts_section}

{top_videos_section}

<section>
    <h2>📖 数据来源 + 方法</h2>
    <ul>
        <li><strong>数据采集：</strong>Apify <code>zen-studio/douyin-profile-scraper</code></li>
        <li><strong>语音转写：</strong>Apify <code>zen-studio/douyin-transcripts-scraper</code> / <code>apple_yang/douyin-transcripts-scraper</code></li>
        <li><strong>筛选标准：</strong>互动分 = log(点赞)*1 + log(评论)*2.5 + log(分享)*3 + log(收藏)*2</li>
        <li><strong>分类方法：</strong>规则标签 + LLM 主题分类</li>
        <li><strong>报告生成：</strong>{generated_at}</li>
    </ul>
</section>

<footer>
    <p>本报告由 douyin-creator-insight skill 自动生成 · 数据仅供分析参考</p>
</footer>

</div>
</body>
</html>
"""


def _safe(s: str) -> str:
    """HTML 转义"""
    if not s:
        return ""
    return html.escape(str(s))


def _render_categories(categories: Dict[str, List[str]], videos: List[Video]) -> str:
    """渲染分类章节"""
    if not categories:
        return ""

    parts = ['<section><h2>🏷️ 主题分类</h2>']
    video_map = {v.aweme_id: v for v in videos}

    for cat, video_ids in sorted(categories.items(), key=lambda x: -len(x[1])):
        parts.append(f'<h3>{_safe(cat)} <span class="tag">{len(video_ids)} 条</span></h3><ul>')
        for vid in video_ids[:5]:
            v = video_map.get(vid)
            if v:
                title = v.title or v.desc[:50] or "(无标题)"
                parts.append(f'<li>{_safe(title)} · 👍{v.stats.digg_count:,}</li>')
        parts.append('</ul>')
    parts.append('</section>')
    return "\n".join(parts)


def _render_transcripts(transcripts, videos: List[Video]) -> str:
    """渲染精华转写章节"""
    valid = [t for t in transcripts if t.text]
    if not valid:
        return ""

    video_map = {v.aweme_id: v for v in videos}

    parts = ['<section><h2>🎙️ 精华视频语音转写</h2>']
    for t in valid:
        v = video_map.get(t.aweme_id)
        title = v.title if v else t.aweme_id
        create_date = v.create_date if v else "—"
        digg = v.stats.digg_count if v else 0
        collect = v.stats.collect_count if v else 0

        parts.append(f'''<div class="video-card">
            <div class="video-meta">
                <span>📅 {create_date}</span>
                <span class="likes">👍 {digg:,}</span>
                <span class="collects">⭐ {collect:,}</span>
                <span>状态: {t.status.value}</span>
            </div>
            <h4>{_safe(title)}</h4>
            <div class="transcript-box">{_safe(t.text)}</div>
        </div>''')
    parts.append('</section>')
    return "\n".join(parts)


def _render_top_videos(top_videos: List[Video]) -> str:
    """渲染互动 TOP 视频"""
    if not top_videos:
        return ""

    parts = ['<section><h2>🏆 互动 TOP 视频</h2><table><thead><tr><th>#</th><th>标题</th><th>日期</th><th>👍</th><th>⭐</th><th>💬</th></tr></thead><tbody>']
    for i, v in enumerate(top_videos, 1):
        title = v.title or v.desc[:50] or "(无标题)"
        parts.append(f'''<tr>
            <td>{i}</td>
            <td>{_safe(title)}</td>
            <td>{v.create_date or "—"}</td>
            <td class="likes">{v.stats.digg_count:,}</td>
            <td class="collects">{v.stats.collect_count:,}</td>
            <td>{v.stats.comment_count:,}</td>
        </tr>''')
    parts.append('</tbody></table></section>')
    return "\n".join(parts)


def build_html_report(report: PipelineReport, top_videos: List[Video]) -> str:
    """生成 HTML 报告"""
    creator = report.creator
    nickname = creator.nickname or creator.douyin_id or creator.creator_query

    valid_transcripts = [t for t in report.transcripts if t.text]

    signature_html = ""
    if creator.signature:
        signature_html = f'<p style="margin-top:16px;font-size:13px;opacity:0.85;">📝 {_safe(creator.signature)}</p>'

    return HTML_TEMPLATE.format(
        nickname=_safe(nickname),
        research_goal=_safe(report.research_goal),
        generated_at=report.generated_at.strftime("%Y-%m-%d %H:%M:%S"),
        followers=creator.followers_count if creator.followers_count else "—",
        hearts=creator.heart_count if creator.heart_count else "—",
        video_count=len(report.videos),
        transcript_count=len(valid_transcripts),
        signature_html=signature_html,
        sec_uid=_safe(creator.sec_uid or "—"),
        categories_section=_render_categories(report.categories, report.videos),
        transcripts_section=_render_transcripts(valid_transcripts, report.videos),
        top_videos_section=_render_top_videos(top_videos),
    )


def build_md_report(report: PipelineReport, top_videos: List[Video]) -> str:
    """生成 Markdown 报告"""
    creator = report.creator
    nickname = creator.nickname or creator.douyin_id or creator.creator_query
    valid_transcripts = [t for t in report.transcripts if t.text]

    lines = [
        f"# {nickname} · 抖音内容洞察报告",
        "",
        f"**数据时点：** {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**研究目的：** {report.research_goal}",
        "",
        "## 📊 账号概况",
        "",
        "| 指标 | 数值 |",
        "|---|---|",
        f"| 粉丝 | {creator.followers_count or '—'} |",
        f"| 累计获赞 | {creator.heart_count or '—'} |",
        f"| 视频数 | {len(report.videos)} |",
        f"| 抓取转写 | {len(valid_transcripts)} |",
        "",
    ]
    if creator.signature:
        lines.extend([f"> 📝 {creator.signature}", ""])

    # 分类
    if report.categories:
        lines.append("## 🏷️ 主题分类")
        lines.append("")
        video_map = {v.aweme_id: v for v in report.videos}
        for cat, ids in sorted(report.categories.items(), key=lambda x: -len(x[1])):
            lines.append(f"### {cat} ({len(ids)} 条)")
            for vid in ids[:5]:
                v = video_map.get(vid)
                if v:
                    title = v.title or v.desc[:40] or "(无标题)"
                    lines.append(f"- {title}")
            lines.append("")

    # 精华转写
    if valid_transcripts:
        video_map = {v.aweme_id: v for v in report.videos}
        lines.append("## 🎙️ 精华视频语音转写")
        lines.append("")
        for t in valid_transcripts:
            v = video_map.get(t.aweme_id)
            title = v.title if v else t.aweme_id
            lines.append(f"### {title}")
            lines.append("")
            lines.append(f"> 状态：{t.status.value} | 视频 ID：`{t.aweme_id}`")
            lines.append("")
            lines.append(t.text[:1500])  # 限制长度
            lines.append("")

    # TOP 视频
    if top_videos:
        lines.append("## 🏆 互动 TOP 视频")
        lines.append("")
        lines.append("| # | 标题 | 日期 | 👍 | ⭐ |")
        lines.append("|---|---|---|---|---|")
        for i, v in enumerate(top_videos, 1):
            title = v.title or v.desc[:40] or "(无标题)"
            lines.append(f"| {i} | {title} | {v.create_date or '—'} | {v.stats.digg_count:,} | {v.stats.collect_count:,} |")
        lines.append("")

    lines.extend([
        "## 📖 数据来源",
        "",
        "- Apify `zen-studio/douyin-profile-scraper`",
        "- Apify `zen-studio/douyin-transcripts-scraper`",
        "- 互动分公式：`log(点赞)*1 + log(评论)*2.5 + log(分享)*3 + log(收藏)*2`",
        "",
        f"生成时间：{report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
    ])
    return "\n".join(lines)


def build_json_report(report: PipelineReport, top_videos: List[Video]) -> str:
    """生成 JSON 数据包"""
    data = report.to_dict()
    data["top_videos"] = [v.to_dict() for v in top_videos]
    return json.dumps(data, ensure_ascii=False, indent=2)


def save_reports(
    report: PipelineReport,
    top_videos: List[Video],
    output_dir: str,
    formats: List[str] = None,
) -> Dict[str, str]:
    """
    保存报告到本地
    Returns: {format: file_path}
    """
    if formats is None:
        formats = ["html", "json", "md"]

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    creator_name = (report.creator.nickname or report.creator.douyin_id or "creator").replace(" ", "_")[:30]
    timestamp = report.generated_at.strftime("%Y%m%d_%H%M%S")
    base_name = f"{creator_name}_douyin_insight_{timestamp}"

    paths = {}
    if "html" in formats:
        p = out_path / f"{base_name}.html"
        p.write_text(build_html_report(report, top_videos), encoding="utf-8")
        paths["html"] = str(p)
    if "md" in formats:
        p = out_path / f"{base_name}.md"
        p.write_text(build_md_report(report, top_videos), encoding="utf-8")
        paths["md"] = str(p)
    if "json" in formats:
        p = out_path / f"{base_name}.json"
        p.write_text(build_json_report(report, top_videos), encoding="utf-8")
        paths["json"] = str(p)

    return paths