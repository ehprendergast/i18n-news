"""Final report assembly for the i18n news pipeline.

Takes verified claims and agent reports, produces a final Economist-style
markdown report with numbered citations.
"""

from pathlib import Path


PROMPT_TEMPLATE_PATH = Path(__file__).parent / "prompts" / "assemble.txt"


def _format_verified_claims(verification: dict) -> str:
    """Format verified claims for the assembly prompt."""
    claims = verification.get("claims", [])
    verified = [c for c in claims if c.get("status") == "verified"]
    if not verified:
        return "(No verified claims available)"

    parts = []
    for i, claim in enumerate(verified, 1):
        sources = claim.get("source_references", [])
        agents = claim.get("agents_supporting", [])
        parts.append(
            f"{i}. {claim.get('claim', '')}\n"
            f"   Sources: {sources}\n"
            f"   Confirmed by agents: {agents}\n"
        )
    return "\n".join(parts)


def _format_source_urls(sources: list[dict]) -> str:
    """Format source URLs for the citation appendix."""
    parts = []
    for i, src in enumerate(sources, 1):
        parts.append(f"[{i}] {src.get('title', 'Untitled')} - {src['url']}")
    return "\n".join(parts)


async def assemble_report(
    country: str,
    verification: dict,
    reports: list[str],
    sources: list[dict],
    client,
) -> str:
    """Compose the final markdown report from verified claims.

    Uses a Claude call to synthesize verified claims into a cohesive
    Economist-style report with numbered citations.
    """
    template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")

    # Format inputs
    claims_text = _format_verified_claims(verification)
    reports_text = ""
    for i, report in enumerate(reports, 1):
        reports_text += f"\n--- AGENT {i} REPORT ---\n{report}\n"

    usable_sources = [s for s in sources if s.get("content")]
    source_urls = _format_source_urls(usable_sources)

    prompt = template.format(
        country=country,
        verified_claims=claims_text,
        agent_reports=reports_text,
        source_urls=source_urls,
    )

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text
