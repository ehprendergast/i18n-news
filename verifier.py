"""Claim verification for the i18n news pipeline.

Extracts claims from agent reports, cross-references against source articles,
and checks for cross-agent agreement.
"""

import json
from pathlib import Path


PROMPT_TEMPLATE_PATH = Path(__file__).parent / "prompts" / "verify.txt"


def _format_sources_for_verify(sources: list[dict]) -> str:
    """Format sources for the verification prompt."""
    parts = []
    for i, src in enumerate(sources, 1):
        content = src.get("content", src.get("snippet", ""))
        if len(content) > 2000:
            content = content[:2000] + "... [truncated]"
        parts.append(
            f"[{i}] {src['title']}\n"
            f"    URL: {src['url']}\n"
            f"    Content: {content}\n"
        )
    return "\n".join(parts)


async def verify_reports(
    reports: list[str],
    sources: list[dict],
    client,
) -> dict:
    """Extract claims from reports and verify against sources.

    Returns dict with:
      - claims: list of claim objects with status
      - summary: counts of verified/unverified
    """
    template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")

    # Format inputs
    reports_text = ""
    for i, report in enumerate(reports, 1):
        reports_text += f"\n--- AGENT {i} REPORT ---\n{report}\n"

    usable_sources = [s for s in sources if s.get("content")]
    sources_text = _format_sources_for_verify(usable_sources)

    prompt = template.format(
        reports=reports_text,
        sources=sources_text,
    )

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )

    # Parse JSON response
    raw = response.content[0].text
    # Extract JSON from potential markdown code blocks
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0]
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0]

    try:
        result = json.loads(raw.strip())
    except json.JSONDecodeError:
        # If parsing fails, return a minimal structure
        result = {
            "claims": [],
            "raw_response": response.content[0].text,
            "parse_error": True,
        }

    # Add summary counts
    claims = result.get("claims", [])
    verified = sum(1 for c in claims if c.get("status") == "verified")
    unverified = sum(1 for c in claims if c.get("status") == "unverified")
    us_flagged = sum(1 for c in claims if c.get("us_content_flag"))
    result["summary"] = {
        "total_claims": len(claims),
        "verified": verified,
        "unverified": unverified,
        "us_content_flagged": us_flagged,
    }

    return result
