"""Static site generator for the i18n news pipeline.

Converts markdown reports in output/ to mobile-friendly HTML pages
and builds an index page. Output goes to docs/ for GitHub Pages.

Citations are interactive: clickable links that jump to sources,
with hover tooltips showing source title and domain for quick
verification while reading.
"""

import re
from pathlib import Path
from urllib.parse import urlparse


BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
DOCS_DIR = BASE_DIR / "docs"


# --- Source parsing ---

def _parse_sources(md: str) -> dict[int, dict]:
    """Extract source map from the ## Sources section of a report.

    Returns {1: {"title": "...", "url": "..."}, 2: {...}, ...}
    """
    sources = {}
    # Find the Sources section
    sources_match = re.search(r"^## Sources\s*\n(.*)", md, re.MULTILINE | re.DOTALL)
    if not sources_match:
        return sources

    sources_text = sources_match.group(1)
    # Match lines like: [1] Title text (https://url)
    # or: 1. Title text (https://url)
    for match in re.finditer(
        r"(?:^\[(\d+)\]|^(\d+)\.)\s+(.+?)\s*\(?(https?://[^\s)]+)\)?",
        sources_text,
        re.MULTILINE,
    ):
        num = int(match.group(1) or match.group(2))
        title = match.group(3).rstrip(" —-")
        url = match.group(4)
        domain = urlparse(url).netloc.replace("www.", "")
        sources[num] = {"title": title, "url": url, "domain": domain}

    return sources


# --- Markdown to HTML conversion ---

def md_to_html(md: str) -> str:
    """Convert report markdown to HTML with interactive citations."""
    sources = _parse_sources(md)
    lines = md.split("\n")
    html_parts = []
    in_list = False
    in_sources = False
    source_list_open = False

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
            if source_list_open:
                html_parts.append("</ol>")
                source_list_open = False
            heading_text = stripped[3:]
            in_sources = heading_text.strip().lower() == "sources"
            html_parts.append(
                f'<h2 id="sources">{_inline(heading_text, sources)}</h2>'
                if in_sources
                else f'<h2>{_inline(heading_text, sources)}</h2>'
            )
            if in_sources:
                html_parts.append('<ol class="source-list">')
                source_list_open = True
            continue
        if stripped.startswith("# "):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(f'<h1>{_inline(stripped[2:], sources)}</h1>')
            continue

        # Source list entries: [N] Title (URL) or N. Title (URL)
        if in_sources:
            source_match = re.match(
                r"(?:\[(\d+)\]|(\d+)\.)\s+(.+?)\s*\(?(https?://[^\s)]+)\)?$",
                stripped,
            )
            if source_match:
                num = int(source_match.group(1) or source_match.group(2))
                title = source_match.group(3).rstrip(" —-")
                url = source_match.group(4)
                domain = urlparse(url).netloc.replace("www.", "")
                html_parts.append(
                    f'<li id="source-{num}" value="{num}">'
                    f'<a href="{url}" target="_blank" rel="noopener">{title}</a>'
                    f' <span class="source-domain">({domain})</span>'
                    f'</li>'
                )
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
            html_parts.append(f"<li>{_inline(stripped[2:], sources)}</li>")
            continue

        # Italic line (e.g., *Report date: ...*)
        if stripped.startswith("*") and stripped.endswith("*") and not stripped.startswith("**"):
            html_parts.append(f'<p class="date">{_inline(stripped, sources)}</p>')
            continue

        # Regular paragraph
        html_parts.append(f"<p>{_inline(stripped, sources)}</p>")

    if in_list:
        html_parts.append("</ul>")
    if source_list_open:
        html_parts.append("</ol>")

    return "\n".join(html_parts)


def _inline(text: str, sources: dict[int, dict]) -> str:
    """Handle inline markdown: bold, italic, links, citations with tooltips."""
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # Italic
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    # Markdown links
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r'<a href="\2" target="_blank" rel="noopener">\1</a>',
        text,
    )
    # Citations [N] or [N,M] — make interactive
    def _cite_replace(match):
        nums_str = match.group(1)
        nums = [n.strip() for n in nums_str.split(",")]
        links = []
        for n in nums:
            try:
                num = int(n)
            except ValueError:
                links.append(n)
                continue
            src = sources.get(num)
            if src:
                tooltip = f'{src["title"]} ({src["domain"]})'
                tooltip_escaped = tooltip.replace('"', '&quot;').replace("'", "&#39;")
                links.append(
                    f'<a href="#source-{num}" class="cite" '
                    f'data-tooltip="{tooltip_escaped}" '
                    f'data-url="{src["url"]}">'
                    f'{num}</a>'
                )
            else:
                links.append(f'<a href="#sources" class="cite">{num}</a>')
        return "[" + ",".join(links) + "]"

    text = re.sub(r"\[(\d[\d,\s]*)\]", _cite_replace, text)
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
  --tooltip-bg: #333;
  --tooltip-text: #fff;
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
    --tooltip-bg: #e0d6c8;
    --tooltip-text: #1a1a1a;
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

/* Citation links */
a.cite {{
  color: var(--accent);
  font-size: 0.8em;
  font-family: sans-serif;
  font-weight: 600;
  text-decoration: none;
  position: relative;
  cursor: pointer;
  border-bottom: 1px dotted var(--accent);
  padding: 0 1px;
}}
a.cite:hover {{
  background: var(--accent);
  color: var(--bg);
  border-radius: 2px;
  text-decoration: none;
}}

/* Tooltip */
.cite-tooltip {{
  position: fixed;
  background: var(--tooltip-bg);
  color: var(--tooltip-text);
  font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 0.8rem;
  line-height: 1.4;
  padding: 0.6rem 0.8rem;
  border-radius: 6px;
  max-width: 320px;
  z-index: 1000;
  pointer-events: none;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  opacity: 0;
  transition: opacity 0.15s;
}}
.cite-tooltip.visible {{
  opacity: 1;
  pointer-events: auto;
}}
.cite-tooltip .tt-title {{
  font-weight: 600;
  margin-bottom: 0.2rem;
}}
.cite-tooltip .tt-domain {{
  color: var(--muted);
  font-size: 0.75rem;
}}
.cite-tooltip .tt-link {{
  display: inline-block;
  margin-top: 0.3rem;
  color: var(--link);
  font-size: 0.75rem;
}}

/* Source list */
.source-list {{
  margin: 0.5rem 0 1rem 1.8rem;
  font-size: 0.9rem;
}}
.source-list li {{
  margin-bottom: 0.6rem;
  padding: 0.3rem 0;
  border-bottom: 1px dotted var(--border);
  scroll-margin-top: 1rem;
}}
.source-list li:target {{
  background: color-mix(in srgb, var(--accent) 12%, transparent);
  border-radius: 4px;
  padding: 0.3rem 0.4rem;
  margin-left: -0.4rem;
}}
.source-domain {{
  color: var(--muted);
  font-size: 0.85em;
}}

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
{scripts}
</body>
</html>
"""

TOOLTIP_SCRIPT = """\
<div class="cite-tooltip" id="cite-tooltip">
  <div class="tt-title" id="tt-title"></div>
  <div class="tt-domain" id="tt-domain"></div>
  <a class="tt-link" id="tt-link" target="_blank" rel="noopener">Open source &rarr;</a>
</div>
<script>
(function() {
  var tip = document.getElementById('cite-tooltip');
  var ttTitle = document.getElementById('tt-title');
  var ttDomain = document.getElementById('tt-domain');
  var ttLink = document.getElementById('tt-link');
  var hideTimer = null;

  function showTip(el) {
    var tooltip = el.getAttribute('data-tooltip');
    var url = el.getAttribute('data-url');
    if (!tooltip) return;
    var parts = tooltip.match(/^(.+?)\\s*\\(([^)]+)\\)$/);
    ttTitle.textContent = parts ? parts[1] : tooltip;
    ttDomain.textContent = parts ? parts[2] : '';
    ttLink.href = url || '#';
    ttLink.style.display = url ? '' : 'none';
    tip.classList.add('visible');
    var rect = el.getBoundingClientRect();
    var tipRect = tip.getBoundingClientRect();
    var left = rect.left + rect.width / 2 - tipRect.width / 2;
    if (left < 8) left = 8;
    if (left + tipRect.width > window.innerWidth - 8) left = window.innerWidth - 8 - tipRect.width;
    var top = rect.top - tipRect.height - 8;
    if (top < 8) top = rect.bottom + 8;
    tip.style.left = left + 'px';
    tip.style.top = top + 'px';
  }

  function hideTip() {
    tip.classList.remove('visible');
  }

  // Desktop: hover
  document.addEventListener('mouseover', function(e) {
    var cite = e.target.closest('a.cite');
    if (cite) {
      clearTimeout(hideTimer);
      showTip(cite);
    }
  });
  document.addEventListener('mouseout', function(e) {
    var cite = e.target.closest('a.cite');
    if (cite) hideTimer = setTimeout(hideTip, 200);
  });
  tip.addEventListener('mouseover', function() { clearTimeout(hideTimer); });
  tip.addEventListener('mouseout', function() { hideTimer = setTimeout(hideTip, 200); });

  // Mobile: tap to show, tap elsewhere to hide
  document.addEventListener('click', function(e) {
    var cite = e.target.closest('a.cite');
    if (cite) {
      e.preventDefault();
      if (tip.classList.contains('visible') && ttLink.href === cite.getAttribute('data-url')) {
        // Second tap: navigate to source in the page
        hideTip();
        document.getElementById('source-' + cite.textContent.trim()).scrollIntoView({behavior:'smooth'});
      } else {
        showTip(cite);
      }
    } else if (!e.target.closest('.cite-tooltip')) {
      hideTip();
    }
  });
})();
</script>
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
        date_str = date_dir.name
        for country_dir in sorted(date_dir.iterdir()):
            if not country_dir.is_dir():
                continue
            report_file = country_dir / "report.md"
            if report_file.exists():
                md = report_file.read_text(encoding="utf-8")
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
            scripts=TOOLTIP_SCRIPT,
        )
        (report_dir / "index.html").write_text(html, encoding="utf-8")

    # Build index page
    if reports:
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
        scripts="",
    )
    (DOCS_DIR / "index.html").write_text(index_html, encoding="utf-8")

    print(f"Site built: {len(reports)} reports -> {DOCS_DIR}")


if __name__ == "__main__":
    build_site()
