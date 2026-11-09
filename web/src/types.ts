export type Leaning = 'left' | 'centre' | 'right' | 'unknown'
export interface Source {
  publisher_id?: string | null
  id: string
  name: string
  url: string
  country: string
  language: string
  political_leaning: Leaning
  classification: { reviewer: string; methodology: string; reviewed_at: string } | null
}
export interface Article {
  id: string
  source_id: string
  title: string
  url: string
  summary: string
  published_at: string
  date_estimated: boolean
  language: string
  country: string
  category: string
}
export interface Exposure {
  category: string
  sector: string
  symbols: string[]
  mechanism: string
  positive: string
  negative: string
  horizon: string
  uncertainty: string
  article_ids: string[]
  matches: Record<string, string>
}
export interface Story {
  id: string
  title: string
  overview: string
  title_kind: string
  first_published: string
  updated_at: string
  article_ids: string[]
  publisher_count: number
  article_counts: Record<Leaning, number>
  publisher_counts: Record<Leaning, number>
  category: string
  countries: string[]
  language: string
  common_terms: string[]
  limitations: string[]
  exposures: Exposure[]
  ai: {
    summary: string
    framing: string[]
    common_facts: string[]
    disagreements: string[]
    article_ids: string[]
    provider: string
    generated_at: string
  } | null
}
export interface Instrument {
  symbol: string
  name: string
  exchange: string
  currency: string
  sector: string
  benchmark: string | null
}
export interface Market {
  symbol: string
  currency: string
  exchange: string
  source: string
  fetched_at: string
  adjusted: boolean
  prices: { date: string; close: number }[]
  change_pct: number | null
  benchmark_change_pct: number | null
  excess_return_pct: number | null
  comparison_dates: string[]
}
export interface Status {
  state: string
  attempted_at: string
  last_success_at: string | null
  errors: string[]
  source_results: Record<string, string>
  market_status: string
  ai_status: string
}
export interface Dataset {
  schema_version: 1
  mode: 'demo' | 'live'
  generated_at: string
  refresh_minutes: number
  sources: Source[]
  articles: Article[]
  stories: Story[]
  instruments: Instrument[]
  markets: Market[]
  status: Status
}
export const leanings: Leaning[] = ['left', 'centre', 'right', 'unknown']
