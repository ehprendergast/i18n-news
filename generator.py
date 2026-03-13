"""Parallel Claude report generation for the i18n news pipeline.

Runs multiple Claude agents concurrently with prompt variations to produce
independent country news reports.
"""

import asyncio
from pathlib import Path


PROMPT_TEMPLATE_PATH = Path(__file__).parent / "prompts" / "report.txt"

CATEGORY_ORDERINGS = {
    1: [
        "1. Domestic politics and governance",
        "2. Economy, trade, and labor",
        "3. Society, culture, and the arts",
        "4. Popular culture, sports, and entertainment",
    ],
    2: [
        "1. Popular culture, sports, and entertainment",
        "2. Society, culture, and the arts",
        "3. Economy, trade, and labor",
        "4. Domestic politics and governance",
    ],
    3: [
        "1. Domestic politics and governance",
        "2. Economy, trade, and labor",
        "3. Society, culture, and the arts",
        "4. Popular culture, sports, and entertainment",
    ],
}

AGENT_INSTRUCTIONS = {
    1: "",
    2: "",
    3: (
        "\nADDITIONAL INSTRUCTION: Prioritize information from "
        "non-English-language sources. When a claim appears in both English "
        "and native-language sources, cite the native-language source.\n"
    ),
}


def _format_sources(sources: list[dict]) -> str:
    """Format source articles for inclusion in the prompt."""
    parts = []
    for i, src in enumerate(sources, 1):
        content = src.get("content", "")
        if not content:
            content = src.get("snippet", "(no content extracted)")
        # Truncate very long articles
        if len(content) > 3000:
            content = content[:3000] + "... [truncated]"
        parts.append(
            f"[{i}] {src['title']}\n"
            f"    URL: {src['url']}\n"
            f"    Language: {src['language']}\n"
            f"    Topic: {src['topic']}\n"
            f"    Content: {content}\n"
        )
    return "\n".join(parts)


def _build_prompt(
    country: str,
    languages: list[str],
    sources: list[dict],
    agent_num: int,
    template: str,
) -> str:
    """Build the full prompt for a given agent number."""
    ordering = "\n".join(CATEGORY_ORDERINGS[agent_num])
    extra = AGENT_INSTRUCTIONS[agent_num]
    sources_text = _format_sources(sources)
    langs = ", ".join(languages)

    prompt = template.format(
        country=country,
        category_ordering=ordering,
        sources=sources_text,
        languages=langs,
    )
    if extra:
        prompt += extra
    return prompt


async def generate_reports(
    country: str,
    languages: list[str],
    sources: list[dict],
    client,
    num_agents: int = 3,
) -> list[str]:
    """Run parallel Claude agents to produce independent reports.

    Each agent gets the same sources but with different prompt variations.
    Returns list of report strings.
    """
    # Load prompt template
    template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")

    # Filter to sources that have content
    usable = [s for s in sources if s.get("content")]
    if not usable:
        raise ValueError("No source articles with extracted content available")

    semaphore = asyncio.Semaphore(3)

    async def run_agent(agent_num: int) -> str:
        async with semaphore:
            prompt = _build_prompt(
                country, languages, usable, agent_num, template
            )
            response = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text

    tasks = [run_agent(n) for n in range(1, num_agents + 1)]
    return await asyncio.gather(*tasks)
