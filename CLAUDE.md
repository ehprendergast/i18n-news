# CLAUDE.md — i18n News Pipeline

## Project Overview

Personal Python pipeline that generates Economist-style international news briefings. Searches for news in English and native languages, runs parallel Claude agents to produce independent reports, verifies claims against sources, and assembles a final markdown report with numbered citations. All output is free of US-centric content.

## Quick Start

```bash
# Install dependencies
/usr/bin/python3 -m pip install -r requirements.txt

# List available countries
/usr/bin/python3 pipeline.py --list

# Generate report for a country
/usr/bin/python3 pipeline.py italy

# Options
/usr/bin/python3 pipeline.py italy --days 14 --agents 5
```

Requires `ANTHROPIC_API_KEY` environment variable.

## Pipeline Stages

```
CONFIG -> TRANSLATE -> SEARCH -> EXTRACT -> GENERATE -> VERIFY -> ASSEMBLE -> OUTPUT
```

1. **Config**: Load `countries.csv`, validate, load cached translations
2. **Translate**: Check translation cache; generate missing prompt translations via Claude
3. **Search**: DuckDuckGo search in English + native languages
4. **Extract**: Pull article text from URLs via trafilatura
5. **Generate**: 3 parallel Claude agents produce independent reports
6. **Verify**: Separate Claude agent extracts claims, checks against sources
7. **Assemble**: Final Claude agent combines verified claims into output report
8. **Output**: Write markdown to `output/{date}/{country}/report.md`

## File Structure

| File | Purpose |
|------|---------|
| `pipeline.py` | Main entry point & orchestrator |
| `config_loader.py` | CSV loading, validation, translation cache |
| `searcher.py` | DuckDuckGo search + trafilatura extraction |
| `generator.py` | Parallel Claude report generation |
| `verifier.py` | Claim extraction & cross-reference verification |
| `assembler.py` | Final report assembly |
| `countries.csv` | Country config (name, languages, search regions) |
| `domain_blocklist.txt` | Blocked news domains |
| `prompts/*.txt` | Prompt templates for report, verify, assemble |
| `cache/translations.json` | Cached prompt translations by language |

## Output Structure

```
output/YYYY_MM_DD/{country}/
├── sources.json         # Gathered source articles + URLs
├── agent_1.md           # Raw agent output
├── agent_2.md
├── agent_3.md
├── verification.json    # Claim verification results
└── report.md            # Final assembled report
```

## Key Design Decisions

- **3 agents with prompt variations**: Different category orderings + one agent prioritizing native-language sources
- **US content filter**: Enforced at 3 levels (report prompt, verification agent, assembly agent)
- **Claim verification**: Claims must be source-traceable OR cross-confirmed by 2/3+ agents
- **Translation cache**: Prompt translations stored in `cache/translations.json` to avoid redundant API calls
- **DuckDuckGo rate limiting**: 1-second delay between searches to avoid throttling

## Adding Countries

Edit `countries.csv`:
```csv
country,languages,search_regions
NewCountry,"Language1,Language2",region-code
```

Region codes follow DuckDuckGo format: `{country_code}-{language_code}` (e.g., `it-it`, `jp-ja`).
