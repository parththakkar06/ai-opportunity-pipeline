// Mirrors utils/schemas.py (AssessmentReport) and the events emitted by api/index.py.

export type Level = 'high' | 'medium' | 'low'
export type ChallengeCategory = 'operational' | 'sales' | 'customer_experience'

export interface ScaleInfo {
  revenue: string | null
  projects_or_portfolio: string | null
  employees: string | null
  other_metrics: string[]
}

export interface ProductOrService {
  name: string
  description: string
}

export interface Project {
  name: string
  location: string | null
  segment: string | null
  status: string | null
  details: string | null
}

export interface NewsItem {
  headline: string
  date: string | null
  summary: string
  source_url: string | null
}

export interface PublicInfoItem {
  category: string
  detail: string
  source_url: string | null
}

export interface CompanyOverview {
  name: string
  website: string | null
  what_they_do: string
  industry: string
  sub_industry: string | null
  business_model: string
  headquarters: string | null
  scale: ScaleInfo
  company_size: string | null
  geographic_presence: string[]
  leadership: string[]
}

export interface KeyBusinessInformation {
  offerings: ProductOrService[]
  major_projects: Project[]
  recent_developments: NewsItem[]
  expansion_plans: string[]
  public_information: PublicInfoItem[]
  target_audience: string[]
  competitors: string[]
}

export interface BusinessChallenge {
  id: string
  category: ChallengeCategory
  title: string
  description: string
  reasoning: string
  signals: string[]
  business_impact: string
  severity: Level
  confidence: Level
}

export interface RubricScore {
  criterion: 'roi_potential' | 'feasibility' | 'speed_to_value' | 'competitive_moat'
  label: string
  score: number
  weight: number
  rationale: string
}

export interface ReportOpportunity {
  id: string
  rank: number | null
  title: string
  category: string
  problem_solved: string
  addresses_challenges: string[]
  applies_to: string
  ai_mechanism: string
  expected_impact: string
  primary_metric: string
  effort: string
  weighted_score: number | null
  rubric: RubricScore[]
  biggest_risk: string | null
  is_recommended: boolean
}

export interface OpportunityHighlight {
  title: string
  evidence: string
}

export interface RecommendedSolution {
  name: string
  what_it_does: string
  maps_to: string
  expected_impact: string
  timeline: string
}

export interface CEOPitch {
  addressed_to: string
  title: string
  why_we_reached_out: string
  opportunities_identified: OpportunityHighlight[]
  recommended_solutions: RecommendedSolution[]
  roi_headline: string | null
  closing: string
  email_subject: string
  email_body: string
  elevator_pitch: string
}

export interface AssessmentReport {
  business_name: string
  slug: string
  generated_at: string | null
  data_quality: string
  stages_completed: number[]
  company_overview: CompanyOverview
  key_business_information: KeyBusinessInformation
  business_challenges: BusinessChallenge[]
  ai_opportunities: ReportOpportunity[]
  recommended_opportunity_id: string | null
  ceo_pitch: CEOPitch | null
  prototype_available: boolean
  assumptions: string[]
  sources: string[]
}

export interface Usage {
  input_tokens: number
  output_tokens: number
  cost: string
}

export interface ReportPayload {
  report: AssessmentReport
  markdown: string
  pitch_text: string
  prototype_url: string | null
  usage?: Usage
}

export interface SavedRun {
  slug: string
  business_name: string
  input_name: string
  website: string | null
  industry: string
  generated_at: string | null
  stages_completed: number[]
  complete: boolean
  next_stage: number | null
  data_quality: string
  prototype_available: boolean
}

export interface Health {
  status: 'ok' | 'config_error'
  message?: string
  provider?: string
  model?: string
  llm_key_configured?: boolean
  search_provider?: string
}

export interface AnalyzeRequest {
  company_name: string
  url?: string
  include_prototype: boolean
  from_stage?: number
  run_slug?: string
}

export type StageState = 'pending' | 'active' | 'done' | 'skipped' | 'error'

export type StreamEvent =
  | { type: 'accepted'; slug: string }
  | { type: 'start'; business_name: string; slug: string; provider: string; model: string; search_chain: string[] }
  | { type: 'stage'; stage: number; title: string; state: 'active' | 'done' | 'skipped'; seconds?: number }
  | { type: 'status'; stage: number; agent: string; message: string }
  | { type: 'note'; stage: number; message: string }
  | {
      type: 'agent_done'
      stage: number
      agent: string
      seconds: number
      input_tokens: number
      output_tokens: number
      cost: string
      files: string[]
    }
  | ({ type: 'result' } & ReportPayload)
  | { type: 'error'; message: string }
