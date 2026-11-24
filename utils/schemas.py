"""Pydantic models for every JSON handoff between agents, plus the final 5-section report.

Schemas the LLM fills in are kept simple (no numeric range constraints) so they work
with both Gemini `response_schema` and OpenAI JSON mode. Ranges such as "score is
1-10" are enforced in Python after validation instead.

Fields added for the assessment spec have defaults, so runs saved before they existed
(e.g. an older outputs/<slug>/01_business_profile.json) still load.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low"]
Category = Literal["revenue_growth", "cost_reduction", "customer_experience", "internal_automation"]
ChallengeCategory = Literal["operational", "sales", "customer_experience"]


# --------------------------------------------------------------------------- Stage 1: Researcher
class ProductOrService(BaseModel):
    name: str
    description: str


class NewsItem(BaseModel):
    headline: str
    date: Optional[str] = Field(None, description="ISO date or approximate (e.g. '2026-03'); null if unknown")
    summary: str
    source_url: Optional[str] = None


class Bottleneck(BaseModel):
    area: str = Field(description="Operational area, e.g. 'site handover', 'lead follow-up'")
    description: str
    evidence: str = Field(description="What in the evidence points to this, or 'inferred from industry norms'")
    confidence: Confidence


class BrandSignals(BaseModel):
    primary_color_hex: Optional[str] = Field(None, description="e.g. '#0F4C81'; null if unknown")
    secondary_color_hex: Optional[str] = None
    tone_of_voice: str = Field(description="e.g. 'premium, understated, trustworthy'")
    tagline: Optional[str] = None


class FieldConfidence(BaseModel):
    field: str
    confidence: Confidence
    note: str


class ScaleInfo(BaseModel):
    revenue: Optional[str] = Field(None, description="Latest revenue / sales bookings with period, e.g. 'FY25 sales bookings ₹8,000 Cr'")
    projects_or_portfolio: Optional[str] = Field(None, description="e.g. '65 projects, 45 mn sq ft delivered, 20 mn sq ft ongoing'")
    employees: Optional[str] = None
    other_metrics: list[str] = Field(default_factory=list, description="Other scale signals: market cap, customers served, land bank")


class Project(BaseModel):
    name: str
    location: Optional[str] = None
    segment: Optional[str] = Field(None, description="e.g. 'luxury residential', 'commercial office', 'plotted development'")
    status: Optional[str] = Field(None, description="e.g. 'launched 2026', 'under construction', 'delivered'")
    details: Optional[str] = Field(None, description="Size, price band, RERA number, notable facts")


class PublicInfoItem(BaseModel):
    category: str = Field(description="e.g. 'RERA / regulatory', 'partnership', 'financials', 'leadership', 'awards', 'legal'")
    detail: str
    source_url: Optional[str] = None


# ---- evidence (Phase 1: every fact has a source and a date) ----
class ExtractedFact(BaseModel):
    """One atomic fact as the cheap extraction model returns it."""
    statement: str = Field(description="One self-contained factual sentence, copied or tightly paraphrased from the document")
    metric: Optional[str] = Field(None, description=(
        "snake_case key when the fact is a metric or a role, e.g. revenue, sales_bookings, collections, net_profit, "
        "net_debt, land_bank, area_delivered, projects_launched, employees, managing_director, ceo, chairman"))
    value: Optional[str] = Field(None, description="The number with unit exactly as written, e.g. '₹6,252 crore'")
    period: Optional[str] = Field(None, description="Period the value refers to, e.g. 'Q1 FY27', 'FY26'")
    as_of: Optional[str] = Field(None, description="ISO date (YYYY-MM-DD) the fact refers to or was stated; null if unclear")


class LeaderStatement(BaseModel):
    speaker: str
    role: str
    quote: str = Field(description="Verbatim words from the document, no paraphrasing")
    topic: str
    date: Optional[str] = None


class DocFacts(BaseModel):
    source_id: str = Field(description="Echo the source_id given for the document")
    document_date: Optional[str] = Field(None, description="ISO date of the document itself, if stated")
    facts: list[ExtractedFact]
    leader_statements: list[LeaderStatement] = Field(default_factory=list)


class FactBatch(BaseModel):
    documents: list[DocFacts]


class Fact(ExtractedFact):
    """A fact with provenance, as stored in 01_business_profile.json (Python fills the ids and dates)."""
    fact_id: str                      # "S3.F7" for documents, "R12" for search snippets
    source_id: str
    as_of_basis: Literal["stated", "published", "retrieved", "unknown"] = "unknown"
    superseded_by: Optional[str] = None


class SourceDoc(BaseModel):
    source_id: str
    url: str
    title: str
    source_type: str                  # filing | investor | rera | news | company | other | snippet
    kind: str                         # pdf | html | snippet
    published: Optional[str] = None
    retrieved: Optional[str] = None


class Leader(BaseModel):
    name: str
    role: str
    evidence: list[str] = Field(description="fact_ids that name this person in this role")


class FieldEvidence(BaseModel):
    field: str = Field(description="Profile field path, e.g. 'scale.revenue', 'major_projects[2]', 'recent_news[0]'")
    evidence: list[str] = Field(description="fact_ids supporting the field")


class BusinessProfileDraft(BaseModel):
    """What the research model writes. Provenance fields are added by Python (see BusinessProfile)."""
    business_name: str
    website: Optional[str] = None
    industry: str
    sub_industry: Optional[str] = None
    headquarters: Optional[str] = None
    company_size_estimate: Optional[str] = Field(None, description="e.g. '2,500 employees', 'single location'")
    business_model: str = Field(description="e.g. 'Residential & commercial real-estate developer', 'D2C e-commerce'")
    description: str = Field(description="What the company does, in 2-4 sentences")
    scale: ScaleInfo = Field(default_factory=ScaleInfo)
    geographic_presence: list[str] = Field(default_factory=list, description="Cities / regions / countries of operation")
    core_products_services: list[ProductOrService]
    major_projects: list[Project] = Field(default_factory=list, description="Flagship and recent projects or product lines")
    target_audience: list[str]
    pricing_model: Optional[str] = Field(None, description="Public pricing info, or null if not public")
    tech_stack_signals: list[str]
    recent_news: list[NewsItem]
    expansion_plans: list[str] = Field(default_factory=list, description="Announced launches, new cities, land acquisitions, capex")
    public_information: list[PublicInfoItem] = Field(default_factory=list, description="RERA launches, partnerships, financials, etc.")
    operational_bottlenecks: list[Bottleneck]
    competitors: list[str]
    brand: BrandSignals
    leaders: list[Leader] = Field(default_factory=list, description="Current leaders, only from cited evidence")
    field_evidence: list[FieldEvidence] = Field(default_factory=list, description="Evidence for every factual field")
    data_quality: Confidence = Field(description="Overall quality of available public information")
    field_confidence: list[FieldConfidence]
    assumptions: list[str] = Field(description="Every inference not directly supported by evidence")


class BusinessProfile(BusinessProfileDraft):
    """Stored profile: the draft plus provenance computed in Python."""
    leadership: list[str] = Field(default_factory=list, description="'Name — Role' for leaders that passed the 12-month evidence rule")
    sources: list[str] = Field(default_factory=list, description="URLs actually used")
    sources_index: list[SourceDoc] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    leader_statements: list[dict] = Field(default_factory=list)
    provenance_warnings: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- Stage 2: Challenge & Reasoning Analyst
class BusinessChallenge(BaseModel):
    id: str = Field(description="Stable id: 'ch-1', 'ch-2', ...")
    category: ChallengeCategory
    title: str
    description: str = Field(description="What the challenge is and how it shows up day to day")
    reasoning: str = Field(description="WHY the research signals point to this challenge: cite the specific signals and the causal logic")
    signals: list[str] = Field(description="The concrete research signals used (news, scale facts, reviews, hiring, regulations)")
    business_impact: str = Field(description="What it costs the business: revenue, margin, time, reputation")
    severity: Literal["high", "medium", "low"]
    confidence: Confidence


class BusinessChallenges(BaseModel):
    business_name: str
    challenges: list[BusinessChallenge]


# --------------------------------------------------------------------------- Stage 3: Strategist + Evaluator
class EffortEstimate(BaseModel):
    level: Literal["low", "medium", "high"]
    timeline_weeks: int = Field(description="Weeks to a working first version")
    team: str = Field(description="e.g. '1 full-stack engineer + vendor API'")


class ImpactEstimate(BaseModel):
    summary: str
    primary_metric: str = Field(description="The KPI this moves, e.g. 'site-visit-to-booking conversion'")
    annual_value_usd_low: Optional[float] = None
    annual_value_usd_high: Optional[float] = None
    basis: str = Field(description="How the value was estimated, with assumptions")


class AIOpportunity(BaseModel):
    id: str = Field(description="Stable id: 'opp-1', 'opp-2', ...")
    title: str
    category: Category
    problem_solved: str
    addresses_challenges: list[str] = Field(default_factory=list, description="Ids of the business challenges this solves, e.g. ['ch-1']")
    applies_to: str = Field("", description="The specific projects, buyer-journey stage, or site/sales operation it plugs into")
    ai_mechanism: str = Field(description="Concretely how the AI works: models, inputs, outputs, workflow")
    why_this_business: str = Field(description="Why this fits this specific business, not businesses in general")
    estimated_effort: EffortEstimate
    estimated_impact: ImpactEstimate
    required_data: list[str]
    risks: list[str]


class AIOpportunities(BaseModel):
    business_name: str
    opportunities: list[AIOpportunity]


class CriterionScore(BaseModel):
    score: int = Field(description="Integer from 1 (worst) to 10 (best)")
    rationale: str


class OpportunityScore(BaseModel):
    opportunity_id: str
    feasibility: CriterionScore
    speed_to_value: CriterionScore
    roi_potential: CriterionScore
    competitive_moat: CriterionScore
    biggest_risk: str


class EvaluationScores(BaseModel):
    scores: list[OpportunityScore]


class Rejection(BaseModel):
    opportunity_id: str
    reason: str


class Phase(BaseModel):
    name: str
    duration_weeks: int
    deliverables: list[str]


class RiskMitigation(BaseModel):
    risk: str
    mitigation: str


class ExecutiveSummary(BaseModel):
    headline: str = Field(description="One sharp sentence")
    executive_summary: str = Field(description="2-3 short paragraphs for a CEO")
    why_it_wins: list[str]
    why_not_the_others: list[Rejection]
    implementation_phases: list[Phase]
    success_metrics: list[str]
    risks_and_mitigations: list[RiskMitigation]


class RankedOpportunity(BaseModel):
    rank: int
    opportunity_id: str
    title: str
    weighted_score: float  # 0-100, computed in Python
    scores: OpportunityScore


class WinningStrategy(BaseModel):
    business_name: str
    rubric_weights: dict[str, float]
    ranking: list[RankedOpportunity]
    winner: AIOpportunity
    winner_weighted_score: float
    summary: ExecutiveSummary


# --------------------------------------------------------------------------- Stage 4: CEO Pitch Builder
class ROIAssumption(BaseModel):
    label: str
    value: str
    source: Literal["public data", "industry benchmark", "assumption"]


class ROILineItem(BaseModel):
    item: str
    calculation: str = Field(description="Show the math, e.g. '1,200 site visits/qtr x 2% uplift x ₹1.2 Cr x 4'")
    annual_value_usd_low: float
    annual_value_usd_high: float


class OpportunityHighlight(BaseModel):
    title: str
    evidence: str = Field(description="The specific fact about the company that makes this an opportunity")


class RecommendedSolution(BaseModel):
    name: str
    what_it_does: str
    maps_to: str = Field(description="The project, buyer-journey stage, or operation it improves")
    expected_impact: str
    timeline: str = Field(description="e.g. '6-week pilot, then rollout'")


class ExecutivePitchDraft(BaseModel):
    recipient_role: str = Field(description="e.g. 'Managing Director & CEO'")
    addressed_to: str = Field("", description="The CEO's name and title if public (e.g. 'Mr. A. Kumar, CEO'), else the title")
    ceo_pitch_title: str = Field("", description="Title line of the one-page pitch")
    why_we_reached_out: str = Field("", description="2-4 sentences grounded in specific, recent facts about the company")
    opportunities_identified: list[OpportunityHighlight] = Field(default_factory=list)
    recommended_solutions: list[RecommendedSolution] = Field(default_factory=list)
    closing: str = Field("", description="Short close with a concrete next step")
    email_subject: str
    email_body: str = Field(description="Plain text, under 180 words, no placeholders except [Your Name]")
    elevator_pitch: str = Field(description="About 150 words, speakable in 60 seconds")
    roi_assumptions: list[ROIAssumption]
    roi_line_items: list[ROILineItem]
    implementation_cost_usd_low: float
    implementation_cost_usd_high: float
    annual_running_cost_usd: float
    caveats: list[str]
    next_step_cta: str


class ROISummary(BaseModel):
    annual_value_usd_low: float
    annual_value_usd_high: float
    net_annual_value_usd_low: float
    net_annual_value_usd_high: float
    payback_months_best: Optional[float]
    payback_months_worst: Optional[float]
    three_year_roi_pct_low: Optional[float]
    three_year_roi_pct_high: Optional[float]


# --------------------------------------------------------------------------- Final 5-section report (built in Python)
class CompanyOverview(BaseModel):
    name: str
    website: Optional[str] = None
    what_they_do: str
    industry: str
    sub_industry: Optional[str] = None
    business_model: str
    headquarters: Optional[str] = None
    scale: ScaleInfo
    company_size: Optional[str] = None
    geographic_presence: list[str]
    leadership: list[str] = Field(default_factory=list)


class KeyBusinessInformation(BaseModel):
    offerings: list[ProductOrService]
    major_projects: list[Project]
    recent_developments: list[NewsItem]
    expansion_plans: list[str]
    public_information: list[PublicInfoItem]
    target_audience: list[str]
    competitors: list[str]


class RubricScore(BaseModel):
    criterion: str          # roi_potential | feasibility | speed_to_value | competitive_moat
    label: str
    score: int              # 1-10
    weight: float           # 0-1, from the rubric weights used for this run
    rationale: str


class ReportOpportunity(BaseModel):
    id: str
    rank: Optional[int] = None
    title: str
    category: str
    problem_solved: str
    addresses_challenges: list[str]
    applies_to: str
    ai_mechanism: str
    expected_impact: str
    primary_metric: str
    effort: str
    weighted_score: Optional[float] = None
    rubric: list[RubricScore] = Field(default_factory=list)
    biggest_risk: Optional[str] = None
    is_recommended: bool = False


class CEOPitch(BaseModel):
    addressed_to: str
    title: str
    why_we_reached_out: str
    opportunities_identified: list[OpportunityHighlight]
    recommended_solutions: list[RecommendedSolution]
    roi_headline: Optional[str] = None
    closing: str
    email_subject: str
    email_body: str
    elevator_pitch: str


class AssessmentReport(BaseModel):
    business_name: str
    slug: str
    generated_at: Optional[str] = None
    data_quality: str
    stages_completed: list[int]
    company_overview: CompanyOverview
    key_business_information: KeyBusinessInformation
    business_challenges: list[BusinessChallenge]
    ai_opportunities: list[ReportOpportunity]
    recommended_opportunity_id: Optional[str] = None
    ceo_pitch: Optional[CEOPitch] = None
    prototype_available: bool = False
    assumptions: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class RunMeta(BaseModel):
    business_name: str
    slug: str
    url: Optional[str] = None
    context: Optional[str] = None
    provider: str
    model: str
    builder_model: str
    from_step: int
    started_at: str
    finished_at: Optional[str] = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: Optional[float] = None
    search_providers_used: list[str] = Field(default_factory=list)
    elapsed_seconds: Optional[float] = None
    stages: dict[str, dict] = Field(default_factory=dict)      # "1": {input, output, calls, seconds}
    research: dict = Field(default_factory=dict)               # pages fetched, facts, gap round, cache hits
