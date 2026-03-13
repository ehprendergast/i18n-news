"""Static site generator for the i18n news pipeline.

Converts markdown reports in output/ to mobile-friendly HTML pages
and builds an index page. Output goes to docs/ for GitHub Pages.
"""

import re
import sys
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
DOCS_DIR = BASE_DIR / "docs"


# --- Markdown to HTML conversion (minimal, no dependencies) ---

def md_to_html(md: str) -> str:
    """Convert report markdown to HTML. Handles the subset used by reports."""
    lines = md.split("\n")
    html_parts = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        # Blank line
        if not stripped:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append("")
            continue

        # Headings
        if stripped.startswith("## "):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(f'<h2>{_inline(stripped[3:])}</h2>')
            continue
        if stripped.startswith("# "):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(f'<h1>{_inline(stripped[2:])}</h1>')
            continue

        # Horizontal rule
        if stripped == "---":
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append("<hr>")
            continue

        # Bullet list
        if stripped.startswith("- "):
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            html_parts.append(f"<li>{_inline(stripped[2:])}</li>")
            continue

        # Italic line (e.g., *Report date: ...*)
        if stripped.startswith("*") and stripped.endswith("*") and not stripped.startswith("**"):
            html_parts.append(f'<p class="date">{_inline(stripped)}</p>')
            continue

        # Regular paragraph
        html_parts.append(f"<p>{_inline(stripped)}</p>")

    if in_list:
        html_parts.append("</ul>")

    return "\n".join(html_parts)


def _inline(text: str) -> str:
    """Handle inline markdown: bold, italic, links, citations."""
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # Italic
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    # Links
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    # Citations [N] or [N,M] — style them
    text = re.sub(r"\[(\d[\d,\s]*)\]", r'<span class="cite">[\1]</span>', text)
    return text


# --- HTML Templates ---

PAGE_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{
  --bg: #fdf6e3;
  --text: #1a1a1a;
  --accent: #c0392b;
  --muted: #666;
  --border: #d4c5a9;
  --card-bg: #fff;
  --link: #2c5282;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #1a1a1a;
    --text: #e0d6c8;
    --accent: #e74c3c;
    --muted: #999;
    --border: #333;
    --card-bg: #242424;
    --link: #63b3ed;
  }}
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: Georgia, 'Times New Roman', serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.7;
  padding: 1rem;
  max-width: 42rem;
  margin: 0 auto;
}}
h1 {{
  font-size: 1.6rem;
  border-bottom: 3px solid var(--accent);
  padding-bottom: 0.4rem;
  margin-bottom: 0.5rem;
}}
h2 {{
  font-size: 1.2rem;
  color: var(--accent);
  margin-top: 1.8rem;
  margin-bottom: 0.6rem;
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.2rem;
}}
p {{ margin-bottom: 1rem; }}
p.date {{ color: var(--muted); font-size: 0.9rem; margin-bottom: 1.5rem; }}
ul {{ margin: 0.5rem 0 1rem 1.2rem; }}
li {{ margin-bottom: 0.5rem; }}
hr {{ border: none; border-top: 1px solid var(--border); margin: 1.5rem 0; }}
a {{ color: var(--link); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.cite {{ color: var(--accent); font-size: 0.8em; font-family: sans-serif; }}
.nav {{ font-family: sans-serif; font-size: 0.85rem; margin-bottom: 1.5rem; }}
.nav a {{ margin-right: 1rem; }}
.country-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}}
.country-card {{
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 1rem 1.2rem;
  text-decoration: none;
  color: var(--text);
  transition: border-color 0.2s;
}}
.country-card:hover {{
  border-color: var(--accent);
  text-decoration: none;
}}
.country-card h3 {{
  font-size: 1.1rem;
  margin-bottom: 0.3rem;
}}
.country-card .meta {{
  font-family: sans-serif;
  font-size: 0.8rem;
  color: var(--muted);
}}
.empty {{ color: var(--muted); font-style: italic; margin-top: 2rem; }}
</style>
</head>
<body>
{nav}
{content}
</body>
</html>
"""


def _nav_html(is_index: bool = False) -> str:
    if is_index:
        return '<div class="nav"><strong>i18n News</strong></div>'
    return '<div class="nav"><a href="../index.html">&larr; All Reports</a></div>'


# --- Site building ---

def find_reports() -> list[dict]:
    """Find all generated reports, grouped by date and country."""
    reports = []
    if not OUTPUT_DIR.exists():
        return reports

    for date_dir in sorted(OUTPUT_DIR.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        date_str = date_dir.name  # YYYY_MM_DD
        for country_dir in sorted(date_dir.iterdir()):
            if not country_dir.is_dir():
                continue
            report_file = country_dir / "report.md"
            if report_file.exists():
                md = report_file.read_text(encoding="utf-8")
                # Extract title from first heading
                title_match = re.search(r"^#\s+(.+)", md, re.MULTILINE)
                title = title_match.group(1) if title_match else country_dir.name.title()
                reports.append({
                    "date": date_str,
                    "date_display": date_str.replace("_", "-"),
                    "country": country_dir.name,
                    "country_display": country_dir.name.replace("_", " ").title(),
                    "title": title,
                    "markdown": md,
                    "path": report_file,
                })
    return reports


def build_site() -> None:
    """Build the static site from all reports."""
    reports = find_reports()

    # Clean and recreate docs dir
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    # Build individual report pages
    for report in reports:
        report_dir = DOCS_DIR / report["date"] / report["country"]
        report_dir.mkdir(parents=True, exist_ok=True)

        content = md_to_html(report["markdown"])
        html = PAGE_TEMPLATE.format(
            title=report["title"],
            nav=_nav_html(is_index=False),
            content=content,
        )
        (report_dir / "index.html").write_text(html, encoding="utf-8")

    # Build index page
    if reports:
        # Group by date
        dates = {}
        for r in reports:
            dates.setdefault(r["date"], []).append(r)

        index_content = "<h1>International Briefings</h1>\n"
        index_content += '<p class="date">Economist-style country reports, free of US-centric content</p>\n'

        for date in sorted(dates.keys(), reverse=True):
            display = date.replace("_", "-")
            index_content += f"<h2>{display}</h2>\n"
            index_content += '<div class="country-grid">\n'
            for r in sorted(dates[date], key=lambda x: x["country"]):
                href = f'{r["date"]}/{r["country"]}/index.html'
                index_content += (
                    f'<a class="country-card" href="{href}">\n'
                    f'  <h3>{r["country_display"]}</h3>\n'
                    f'  <div class="meta">{display}</div>\n'
                    f'</a>\n'
                )
            index_content += '</div>\n'
    else:
        index_content = (
            "<h1>International Briefings</h1>\n"
            '<p class="empty">No reports generated yet. Run the pipeline first.</p>\n'
        )

    index_html = PAGE_TEMPLATE.format(
        title="International Briefings",
        nav=_nav_html(is_index=True),
        content=index_content,
    )
    (DOCS_DIR / "index.html").write_text(index_html, encoding="utf-8")

    print(f"Site built: {len(reports)} reports -> {DOCS_DIR}")


if __name__ == "__main__":
    build_site()
