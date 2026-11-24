from agents.analyst import ChallengeAnalystAgent
from agents.base import STAGE_TITLES
from agents.builder import BuilderAgent
from agents.evaluator import EvaluatorAgent
from agents.researcher import ResearcherAgent
from agents.strategist import StrategistAgent

# The 4 user-facing stages and the agents each one runs, in order.
STAGES: list[tuple[int, str, list[type]]] = [
    (1, STAGE_TITLES[1], [ResearcherAgent]),
    (2, STAGE_TITLES[2], [ChallengeAnalystAgent]),
    (3, STAGE_TITLES[3], [StrategistAgent, EvaluatorAgent]),
    (4, STAGE_TITLES[4], [BuilderAgent]),
]
PIPELINE = [agent for _, _, agents in STAGES for agent in agents]

__all__ = [
    "STAGES", "PIPELINE", "ResearcherAgent", "ChallengeAnalystAgent", "StrategistAgent", "EvaluatorAgent",
    "BuilderAgent",
]
