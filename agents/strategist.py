"""Agent 2: AI Opportunity Strategist -> 02_ai_opportunities.json"""
from __future__ import annotations

from pathlib import Path

from agents.base import CHALLENGES_JSON, OPPORTUNITIES_JSON, PROFILE_JSON, Agent, as_json
from utils.io import read_model, write_json
from utils.schemas import AIOpportunities, BusinessChallenges, BusinessProfile

MIN_IDEAS, MAX_IDEAS = 5, 7
CATEGORIES = {"revenue_growth", "cost_reduction", "customer_experience", "internal_automation"}


def check_opportunities(result: AIOpportunities, challenge_ids: set[str] | None = None) -> str | None:
    n = len(result.opportunities)
    problems = []
    if challenge_ids:
        for o in result.opportunities:
            unknown = set(o.addresses_challenges) - challenge_ids
            if not o.addresses_challenges:
                problems.append(f"{o.id} must list the challenge ids it solves in addresses_challenges.")
            elif unknown:
                problems.append(f"{o.id} references unknown challenge ids {sorted(unknown)}; use only {sorted(challenge_ids)}.")
            if not o.applies_to.strip():
                problems.append(f"{o.id} needs applies_to: the specific projects, journey stage or operation.")
    if n < MIN_IDEAS:
        problems.append(f"Only {n} opportunities; provide between {MIN_IDEAS} and {MAX_IDEAS}.")
    ids = [o.id for o in result.opportunities]
    if len(set(ids)) != len(ids):
        problems.append(f"Opportunity ids must be unique; got {ids}.")
    missing = CATEGORIES - {o.category for o in result.opportunities}
    if missing and n >= MIN_IDEAS:
        problems.append(f"No idea covers these categories: {sorted(missing)}.")
    return " ".join(problems) or None


class StrategistAgent(Agent):
    stage = 3
    key = "strategist"
    title = "AI Opportunity Strategist"

    def run(self) -> list[Path]:
        ctx = self.ctx
        profile = read_model(ctx.path(PROFILE_JSON), BusinessProfile)
        challenges = read_model(ctx.path(CHALLENGES_JSON), BusinessChallenges)
        challenge_ids = {c.id for c in challenges.challenges}
        ctx.status("mapping AI opportunities to the diagnosed challenges…")
        user = (
            f"<business_profile>\n{as_json(profile)}\n</business_profile>\n\n"
            f"<business_challenges>\n{as_json(challenges)}\n</business_challenges>\n\n"
            f"Propose {MIN_IDEAS}-{MAX_IDEAS} AI opportunities for {profile.business_name}. "
            f"Valid challenge ids: {sorted(challenge_ids)}."
        )
        result = ctx.llm.structured(
            agent=self.key, system=self.prompt("strategist.md"), user=user, schema=AIOpportunities,
            model=ctx.settings.model, effort=ctx.settings.effort,
            check=lambda r: check_opportunities(r, challenge_ids),
        )
        if len(result.opportunities) > MAX_IDEAS:
            result.opportunities = result.opportunities[:MAX_IDEAS]
        result.business_name = profile.business_name
        ctx.note(f"{len(result.opportunities)} opportunities: " + "; ".join(o.title for o in result.opportunities))
        return [write_json(ctx.path(OPPORTUNITIES_JSON), result)]
