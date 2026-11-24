"""Stage 2: Challenge & Reasoning Analyst -> 02_business_challenges.json"""
from __future__ import annotations

from pathlib import Path

from agents.base import CHALLENGES_JSON, PROFILE_JSON, Agent, as_json, facts_digest, profile_for_prompt
from utils.io import read_model, write_json
from utils.schemas import BusinessChallenges, BusinessProfile

MIN_CHALLENGES, MAX_CHALLENGES = 5, 8
REQUIRED_CATEGORIES = {"operational", "sales", "customer_experience"}
MIN_REASONING_WORDS = 20


def check_challenges(result: BusinessChallenges) -> str | None:
    problems: list[str] = []
    n = len(result.challenges)
    if n < MIN_CHALLENGES:
        problems.append(f"Only {n} challenges; provide {MIN_CHALLENGES}-{MAX_CHALLENGES}.")
    missing = REQUIRED_CATEGORIES - {c.category for c in result.challenges}
    if missing:
        problems.append(f"No challenge in categories {sorted(missing)}; cover operational, sales and customer_experience.")
    ids = [c.id for c in result.challenges]
    if len(set(ids)) != len(ids):
        problems.append(f"Challenge ids must be unique; got {ids}.")
    for c in result.challenges:
        if len(c.reasoning.split()) < MIN_REASONING_WORDS:
            problems.append(f"{c.id} reasoning is too thin; explain the causal chain from the cited signals "
                            f"(at least {MIN_REASONING_WORDS} words).")
        if not c.signals:
            problems.append(f"{c.id} must cite the research signals it is based on.")
    return " ".join(problems) or None


class ChallengeAnalystAgent(Agent):
    stage = 2
    key = "analyst"
    title = "Challenge & Reasoning Analyst"

    def run(self) -> list[Path]:
        ctx = self.ctx
        profile = read_model(ctx.path(PROFILE_JSON), BusinessProfile)
        ctx.status("diagnosing operational, sales and customer-experience challenges…")
        user = (
            f"<business_profile>\n{as_json(profile_for_prompt(profile))}\n</business_profile>\n\n"
            + (f"<evidence_facts>\n{facts_digest(profile)}\n</evidence_facts>\n\n" if profile.facts else "")
            + f"Diagnose {MIN_CHALLENGES}-{MAX_CHALLENGES} business challenges for {profile.business_name}, "
            "each with explicit reasoning from the signals above. Cite fact ids (e.g. S2.F4) in `signals` "
            "when a signal comes from the evidence facts."
        )
        result = ctx.llm.structured(
            agent=self.key, system=self.prompt("challenge_analyst.md"), user=user, schema=BusinessChallenges,
            model=ctx.settings.model, effort=ctx.settings.builder_effort, check=check_challenges,
        )
        result.business_name = profile.business_name
        result.challenges = result.challenges[:MAX_CHALLENGES]
        counts = {cat: sum(c.category == cat for c in result.challenges) for cat in sorted(REQUIRED_CATEGORIES)}
        ctx.note(f"{len(result.challenges)} challenges · " + ", ".join(f"{k} {v}" for k, v in counts.items()))
        return [write_json(ctx.path(CHALLENGES_JSON), result)]
