"""Claude-powered steps: photo condition scoring and the deal write-up.

Both are optional. Without ANTHROPIC_API_KEY the app falls back to the
condition you pick by hand and a plain numeric summary.
"""

from __future__ import annotations

import base64
import mimetypes

import anthropic
from pydantic import BaseModel, Field

from re_agents import config

_client: anthropic.Anthropic | None = None

# Server-side fallback: if the main model declines a request, the API retries it
# on a fallback model chosen by the refusal category. Remove these two lines to opt out.
_FALLBACK_KW = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


class PhotoCondition(BaseModel):
    condition_score: int = Field(description="Appraiser condition rating 1-6 (C1 new, C6 severe damage)")
    renovated: bool = Field(description="True if kitchen/baths look recently updated")
    visible_issues: list[str] = Field(description="Specific problems seen, e.g. water stain on ceiling")
    rooms_seen: list[str]
    summary: str = Field(description="Two sentences on overall condition")


CONDITION_PROMPT = """You are a residential appraiser and rehab estimator.
Rate the property's overall condition from these photos on the appraisal
condition scale:
C1 new or never occupied; C2 no deferred maintenance, recently renovated;
C3 well maintained, minor wear; C4 adequately maintained, some deferred
maintenance, dated finishes; C5 obvious deferred maintenance, needs significant
repairs; C6 substantial damage, unsafe or near uninhabitable.
Judge only from what is visible. If photos show only some rooms, say which
rooms you could see. List concrete visible issues an investor would price in."""


def _image_block(data: bytes, filename: str) -> dict:
    media_type = mimetypes.guess_type(filename)[0] or "image/jpeg"
    if media_type not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        media_type = "image/jpeg"
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": base64.standard_b64encode(data).decode()},
    }


def score_photos(photos: list[tuple[str, bytes]]) -> PhotoCondition:
    """photos: list of (filename, bytes). Up to ~20 images per call."""
    content: list[dict] = [_image_block(data, name) for name, data in photos[:20]]
    content.append({"type": "text", "text": "Rate this property's condition."})
    resp = client().beta.messages.parse(
        model=config.ANTHROPIC_MODEL,
        max_tokens=16000,
        system=CONDITION_PROMPT,
        messages=[{"role": "user", "content": content}],
        output_format=PhotoCondition,
        output_config={"effort": "medium"},
        **_FALLBACK_KW,
    )
    if resp.stop_reason == "refusal" or resp.parsed_output is None:
        raise RuntimeError("Claude could not score these photos. Pick the condition by hand.")
    result = resp.parsed_output
    result.condition_score = min(6, max(1, result.condition_score))
    return result


SUMMARY_PROMPT = """You are an experienced real estate investor and wholesaler
reviewing a deal for a colleague. Write a short, plain-English deal memo:
1. One-line verdict (Strong deal / Workable / Pass) with the main reason.
2. Value: as-is and ARV, how confident, and what could make them wrong.
3. Best exit strategy among wholesale, flip, rental, BRRRR, with the key number.
4. Top 3 risks or things to verify before making an offer.
Use only the numbers given. Do not invent facts about the property or area.
Keep it under 250 words. No legal or tax advice."""


def write_deal_memo(deal_facts: str) -> str:
    resp = client().beta.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=16000,
        system=SUMMARY_PROMPT,
        messages=[{"role": "user", "content": deal_facts}],
        output_config={"effort": "medium"},
        **_FALLBACK_KW,
    )
    if resp.stop_reason == "refusal":
        return "Claude declined to write a memo for this deal."
    return "".join(b.text for b in resp.content if b.type == "text").strip()
