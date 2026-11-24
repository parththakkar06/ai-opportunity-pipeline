"""Token and cost tracking across all agents."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

# USD per 1M tokens (input, output), keyed by model id (substring match).
# Gemini prices change often and vary by model, so none are hard-coded here.
# Either add your models below, e.g.  "gemini-3.8-flash": (<input $/1M>, <output $/1M>),
# or set PRICE_INPUT_PER_MTOK / PRICE_OUTPUT_PER_MTOK in .env to price every call.
# Without a price, token counts are still tracked and cost shows as "n/a".
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    # OpenAI standard rates, from developers.openai.com/api/docs/pricing (checked 2026-11-24).
    "gpt-6.2-sol": (2.00, 10.00),
    "gpt-6.1-sol": (2.00, 10.00),
    "gpt-6.2-astra": (8.00, 40.00),
}


def price_for(model: str) -> tuple[float, float] | None:
    if model.endswith(":free") or model == "openrouter/free":
        return (0.0, 0.0)
    if model in PRICES_PER_MTOK:
        return PRICES_PER_MTOK[model]
    # Tolerate prefixed or suffixed IDs (e.g. "models/gemini-3.8-flash").
    for known, price in PRICES_PER_MTOK.items():
        if known in model:
            return price
    env_in, env_out = os.getenv("PRICE_INPUT_PER_MTOK"), os.getenv("PRICE_OUTPUT_PER_MTOK")
    if env_in and env_out:
        try:
            return float(env_in), float(env_out)
        except ValueError:
            return None
    return None


@dataclass
class UsageRecord:
    agent: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float | None


@dataclass
class AgentTotals:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = 0.0
    calls: int = 0


@dataclass
class CostTracker:
    records: list[UsageRecord] = field(default_factory=list)

    def add(self, agent: str, model: str, input_tokens: int, output_tokens: int) -> UsageRecord:
        price = price_for(model)
        cost = None
        if price is not None:
            cost = (input_tokens * price[0] + output_tokens * price[1]) / 1_000_000
        record = UsageRecord(agent, model, int(input_tokens or 0), int(output_tokens or 0), cost)
        self.records.append(record)
        return record

    def _sum(self, records: list[UsageRecord]) -> AgentTotals:
        totals = AgentTotals()
        for r in records:
            totals.input_tokens += r.input_tokens
            totals.output_tokens += r.output_tokens
            totals.calls += 1
            if r.cost_usd is None or totals.cost_usd is None:
                totals.cost_usd = None
            else:
                totals.cost_usd += r.cost_usd
        return totals

    def for_agent(self, agent: str) -> AgentTotals:
        return self._sum([r for r in self.records if r.agent == agent])

    def total(self) -> AgentTotals:
        return self._sum(self.records)


def fmt_cost(cost: float | None) -> str:
    return "n/a" if cost is None else f"${cost:,.4f}"
