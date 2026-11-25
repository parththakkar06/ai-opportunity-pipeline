// Dev-only worst-case data for the break-ui review (never shipped: App only uses it when import.meta.env.DEV).
// Every value is something a real run can produce: model output has no length limits in utils/schemas.py,
// company names come from user input (max 120 chars, api/index.py AnalyzeRequest), URLs from search results.
import type { ReportPayload } from '@/types'

export type DataMode = 'demo' | 'worst' | 'empty' | 'one'
export const DATA_MODES: DataMode[] = ['demo', 'worst', 'empty', 'one']

export function readDataMode(): DataMode {
  const v = new URLSearchParams(window.location.search).get('data')
  return (DATA_MODES as string[]).includes(v ?? '') ? (v as DataMode) : 'demo'
}

const LONG_URL =
  'https://www.prestigeconstructions.com/sites/default/files/investor-relations/2026/Q2-FY27/Investor-Presentation-Prestige-Estates-Projects-Limited-Q2FY27-final-v3.pdf'

export function applyDataMode(payload: ReportPayload, mode: DataMode): ReportPayload {
  if (mode === 'demo') return payload
  const p = structuredClone(payload)
  const r = p.report
  if (mode === 'empty') {
    r.business_challenges = []
    r.ai_opportunities = []
    r.ceo_pitch = null
    r.key_metrics = []
    r.citations = []
    r.trace = null
    r.verification = null
    r.sensitivity = null
    r.sources = []
    r.assumptions = []
    r.stages_completed = [1]
    r.company_overview.leadership = []
    r.company_overview.geographic_presence = []
    r.company_overview.website = null
    r.key_business_information = {
      offerings: [], major_projects: [], recent_developments: [], expansion_plans: [], public_information: [],
      target_audience: [], competitors: [],
    }
    return p
  }
  if (mode === 'one') {
    r.business_challenges = r.business_challenges.slice(0, 1)
    r.ai_opportunities = r.ai_opportunities.slice(0, 1).map((o) => ({ ...o, rank: 1, is_recommended: true }))
    r.key_metrics = (r.key_metrics ?? []).slice(0, 1)
    r.citations = (r.citations ?? []).slice(0, 1)
    if (r.verification) r.verification = { ...r.verification, supported: 1, checked: 1, pass_rate: 1, estimates: 1, actions: [] }
    return p
  }
  // worst: realistic extremes, spread across rows
  r.business_name = 'Prestige Estates Projects Limited (formerly Prestige Group), Bengaluru'
  r.company_overview.website = 'https://www.prestigeconstructions.com/residential-projects/bengaluru/'
  r.company_overview.industry = 'Real estate development, construction and hospitality'
  r.company_overview.what_they_do =
    'Prestige Estates Projects Limited is one of India’s largest listed real-estate developers, with residential, commercial, retail, hospitality and property-management businesses across Bengaluru, Hyderabad, Chennai, Kochi, Mumbai, Pune, Goa, Mangaluru and the National Capital Region, and a delivered portfolio of more than 300 projects.'
  r.company_overview.leadership = []
  r.company_overview.geographic_presence = ['Bengaluru', 'Hyderabad', 'Chennai', 'Kochi', 'Mumbai Metropolitan Region', 'Pune', 'Goa', 'Mangaluru', 'Delhi NCR', 'Dubai (UAE)']
  r.data_quality = 'low'
  r.stages_completed = [1, 2, 4]
  r.key_metrics = [
    { label: 'Sales bookings, Q2 FY27', value: '₹12,345.67 crore', date: '2026-09-30', facts: ['S1.F1'], citations: [1, 2, 3] },
    { label: 'Residential area under construction across all cities', value: '108.7 mn sq ft', date: '2026-06-30', facts: ['S2.F4'], citations: [12] },
    { label: 'Collections', value: '₹9,999 crore (est.)', date: '2025-03-31', facts: ['S3.F2'], citations: [] },
    { label: 'Managing Director & Chief Executive Officer', value: 'Venkat K. Narayana-Subramaniam', date: '2026-08-14', facts: ['S1.F7'], citations: [1] },
    { label: 'Employees', value: '1', date: null, facts: [], citations: [] },
  ]
  r.citations = Array.from({ length: 14 }, (_, i) => ({
    n: i + 1,
    source_id: i < 6 ? `S${i + 1}` : `R${i + 1}`,
    url: i === 1 ? LONG_URL : `https://economictimes.indiatimes.com/industry/services/property-/-cstruction/story-${1000 + i}.cms`,
    title: i === 1 ? 'Investor Presentation – Prestige Estates Projects Limited – Q2 FY27 (Unaudited, Consolidated) – November 2026' : i === 3 ? '' : `Prestige Group news ${i + 1}`,
    date: i === 4 ? null : '2026-11-0' + ((i % 9) + 1),
    source_type: i < 6 ? 'investor' : 'snippet',
  }))
  if (r.business_challenges[0]) {
    r.business_challenges[0].title =
      'Site-visit-to-booking conversion is falling in the mid-income segment across Bengaluru East launches'
    r.business_challenges[0].signals = [
      LONG_URL,
      'Q2 FY27 investor presentation: “bookings softened in the ₹1–2 crore band despite strong footfall at Prestige Park Grove, Prestige Raintree Park and Prestige Lakeside Habitat”',
    ]
  }
  if (r.business_challenges[1]) r.business_challenges[1].title = 'RERA'
  const o = r.ai_opportunities
  if (o[0]) {
    o[0].title = 'Predictive lead scoring and automated site-visit follow-up for Bengaluru East and North mid-income launches'
    o[0].weighted_score = 100
    if (o[0].build_vs_buy) o[0].build_vs_buy.vendor_refs = [
      { name: 'Salesforce', category: 'crm', url: 'https://www.salesforce.com' },
      { name: 'WhatsApp Business Platform', category: 'messaging', url: 'https://business.whatsapp.com' },
      { name: 'Azure AI Document Intelligence', category: 'document_ai', url: 'https://azure.microsoft.com' },
    ]
  }
  if (o[1]) {
    o[1].why_not =
      'Lower ROI once the value estimate is discounted for assumptions (none of its three value drivers is backed by a sourced figure), and it needs a data-sharing agreement with every channel partner first.'
    o[1].evidence_share = 0
    o[1].weighted_score = 7.5
  }
  if (o[2]) {
    o[2].title = 'IVR'
    o[2].roi_adjusted = null
    o[2].evidence_share = null
    o[2].weighted_score = null
    o[2].rank = null
  }
  if (r.ceo_pitch) r.ceo_pitch.addressed_to = 'Managing Director & Chief Executive Officer'
  if (r.verification) r.verification = { ...r.verification, supported: 0, checked: 7, pass_rate: 0, estimates: 1 }
  r.assumptions = [
    'Managing Director: current holder unknown (no evidence from the last 12 months).',
    ...r.assumptions,
  ]
  return p
}
