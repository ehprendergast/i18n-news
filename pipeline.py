"""AI International News Pipeline.

Generates Economist-style country briefings using multilingual web search
and parallel Claude agents with claim verification.

Usage:
    python pipeline.py <country>       # Generate report for a country
    python pipeline.py --list          # List available countries
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from anthropic import AsyncAnthropic

from assembler import assemble_report
from config_loader import (
    get_country,
    get_or_create_translations,
    load_blocklist,
    load_countries,
    load_translations,
    save_translations,
)
from generator import generate_reports
from searcher import extract_articles, search_country_news
from verifier import verify_reports


BASE_DIR = Path(__file__).parent
DEFAULT_CSV = BASE_DIR / "countries.csv"
DEFAULT_BLOCKLIST = BASE_DIR / "domain_blocklist.txt"
DEFAULT_CACHE = BASE_DIR / "cache" / "translations.json"
DEFAULT_OUTPUT = BASE_DIR / "output"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Economist-style international news briefings"
    )
    parser.add_argument(
        "country",
        nargs="?",
        help="Country to generate report for",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available countries from config",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Lookback period in days (default: 30)",
    )
    parser.add_argument(
        "--agents",
        type=int,
        default=3,
        help="Number of parallel agents (default: 3)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Override output directory",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Path to countries CSV file",
    )
    return parser.parse_args()


async def run_pipeline(args: argparse.Namespace) -> None:
    csv_path = args.csv or str(DEFAULT_CSV)
    countries = load_countries(csv_path)

    # --list mode
    if args.list:
        print("Available countries:")
        for c in countries:
            langs = ", ".join(c["languages"])
            print(f"  {c['country']:20s} Languages: {langs}")
        return

    # Validate country argument
    if not args.country:
        print("Error: country argument required. Use --list to see options.")
        sys.exit(1)

    country_config = get_country(countries, args.country)
    country = country_config["country"]
    languages = country_config["languages"]
    region = country_config["search_regions"]

    print(f"\n{'='*60}")
    print(f"  International Briefing: {country}")
    print(f"  Languages: {', '.join(languages)}")
    print(f"  Region: {region}")
    print(f"  Agents: {args.agents}")
    print(f"  Lookback: {args.days} days")
    print(f"{'='*60}\n")

    # Set up output directory
    today = datetime.now().strftime("%Y_%m_%d")
    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT
    country_dir = output_dir / today / country.lower().replace(" ", "_")
    country_dir.mkdir(parents=True, exist_ok=True)

    # Initialize Anthropic client
    client = AsyncAnthropic()

    # --- Stage 1: Config & Translations ---
    print("[1/6] Loading config and translations...")
    blocklist = load_blocklist(str(DEFAULT_BLOCKLIST))
    cache = load_translations(str(DEFAULT_CACHE))
    translations = await get_or_create_translations(
        country_config, cache, client
    )
    save_translations(str(DEFAULT_CACHE), cache)
    print(f"  Blocklist: {len(blocklist)} domains")
    print(f"  Translations cached for: {list(translations.keys())}")

    # --- Stage 2: Search ---
    print("\n[2/6] Searching for news articles...")
    search_results = search_country_news(
        country,
        languages,
        region,
        blocklist,
        days=args.days,
        translated_queries=translations,
    )
    print(f"  Found {len(search_results)} search results")

    if not search_results:
        print("Error: No search results found. Exiting.")
        sys.exit(1)

    # --- Stage 3: Extract ---
    print("\n[3/6] Extracting article content...")
    articles = await extract_articles(search_results)
    with_content = [a for a in articles if a.get("content")]
    print(f"  Extracted content from {len(with_content)}/{len(articles)} articles")

    if not with_content:
        print("Error: Could not extract content from any articles. Exiting.")
        sys.exit(1)

    # Save sources
    sources_path = country_dir / "sources.json"
    with open(sources_path, "w", encoding="utf-8") as f:
        # Save without full content to keep file manageable
        sources_summary = []
        for a in articles:
            sources_summary.append({
                "url": a["url"],
                "title": a["title"],
                "language": a["language"],
                "topic": a["topic"],
                "has_content": bool(a.get("content")),
                "content_length": len(a.get("content", "")),
            })
        json.dump(sources_summary, f, indent=2, ensure_ascii=False)
    print(f"  Saved sources to {sources_path}")

    # --- Stage 4: Generate ---
    print(f"\n[4/6] Generating {args.agents} independent reports...")
    reports = await generate_reports(
        country, languages, articles, client, num_agents=args.agents
    )
    for i, report in enumerate(reports, 1):
        agent_path = country_dir / f"agent_{i}.md"
        agent_path.write_text(report, encoding="utf-8")
        print(f"  Agent {i}: {len(report)} chars -> {agent_path}")

    # --- Stage 5: Verify ---
    print("\n[5/6] Verifying claims across reports...")
    verification = await verify_reports(reports, articles, client)
    verify_path = country_dir / "verification.json"
    with open(verify_path, "w", encoding="utf-8") as f:
        json.dump(verification, f, indent=2, ensure_ascii=False)
    summary = verification.get("summary", {})
    print(f"  Claims: {summary.get('total_claims', '?')} total")
    print(f"  Verified: {summary.get('verified', '?')}")
    print(f"  Unverified: {summary.get('unverified', '?')}")
    print(f"  US-flagged: {summary.get('us_content_flagged', '?')}")

    # --- Stage 6: Assemble ---
    print("\n[6/6] Assembling final report...")
    final_report = await assemble_report(
        country, verification, reports, articles, client
    )
    report_path = country_dir / "report.md"
    report_path.write_text(final_report, encoding="utf-8")
    print(f"  Final report: {len(final_report)} chars -> {report_path}")

    print(f"\n{'='*60}")
    print(f"  Done! Report saved to:")
    print(f"  {report_path}")
    print(f"{'='*60}\n")


def main():
    args = parse_args()
    asyncio.run(run_pipeline(args))


if __name__ == "__main__":
    main()
