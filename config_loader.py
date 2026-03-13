"""Config loader for the i18n news pipeline.

Handles CSV country config, domain blocklist, and prompt translation cache.
"""

import csv
import json
from pathlib import Path


def load_countries(csv_path: str) -> list[dict]:
    """Parse countries.csv, validate required columns, return list of dicts."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Countries CSV not found: {csv_path}")

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"country", "languages", "search_regions"}
        if not required.issubset(set(reader.fieldnames or [])):
            missing = required - set(reader.fieldnames or [])
            raise ValueError(f"Missing required columns: {missing}")

        countries = []
        for row in reader:
            countries.append({
                "country": row["country"].strip(),
                "languages": [
                    lang.strip() for lang in row["languages"].split(",")
                ],
                "search_regions": row["search_regions"].strip(),
            })
    return countries


def get_country(countries: list[dict], name: str) -> dict:
    """Find a country by name (case-insensitive)."""
    name_lower = name.lower()
    for c in countries:
        if c["country"].lower() == name_lower:
            return c
    available = [c["country"] for c in countries]
    raise ValueError(
        f"Country '{name}' not found. Available: {', '.join(available)}"
    )


def load_blocklist(path: str) -> set[str]:
    """Load blocked domains from text file, one per line."""
    blocklist_path = Path(path)
    if not blocklist_path.exists():
        return set()
    with open(blocklist_path, encoding="utf-8") as f:
        return {
            line.strip().lower()
            for line in f
            if line.strip() and not line.startswith("#")
        }


def load_translations(cache_path: str) -> dict:
    """Load cached prompt translations from JSON."""
    path = Path(cache_path)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_translations(cache_path: str, translations: dict) -> None:
    """Write updated translation cache to JSON."""
    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(translations, f, ensure_ascii=False, indent=2)


async def get_or_create_translations(
    country_config: dict,
    cache: dict,
    client,
) -> dict:
    """Check cache for prompt translations; generate missing ones via Claude.

    Returns dict mapping language -> translated search instruction.
    """
    country = country_config["country"]
    languages = country_config["languages"]
    result = {}

    for lang in languages:
        if lang.lower() == "english":
            result["English"] = None  # no translation needed
            continue

        cache_key = f"{lang}"
        if cache_key in cache:
            result[lang] = cache[cache_key]
            continue

        # Generate translation via Claude
        prompt = (
            f"Translate the following search query instruction into {lang}. "
            f"Return ONLY the translated text, nothing else.\n\n"
            f"Search query: \"Latest news from {country} this month\""
        )
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        translated = response.content[0].text.strip().strip('"')
        cache[cache_key] = translated
        result[lang] = translated

    return result
