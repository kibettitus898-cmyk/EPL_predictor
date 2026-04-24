// src/types/index.ts

export type Outcome = "H" | "D" | "A"

export interface Probabilities {
  H: number
  D: number
  A: number
}

export interface OutcomeDetail {
  outcome:     Outcome
  model_prob:  number
  decimal_odd: number
  ev:          number
  kelly_pct:   number
  is_value:    boolean
}

export interface EVAnalysis {
  bookmaker_vig: number
  has_value:     boolean
  best_bet:      OutcomeDetail | null
  value_bets:    OutcomeDetail[]
  all_outcomes:  OutcomeDetail[]
}

// POST /api/v1/predict response
export interface PredictionResponse {
  home_team:     string
  away_team:     string
  probabilities: Probabilities
  predicted:     Outcome
  label:         string
  confidence:    number
  ev_analysis:   EVAnalysis | null
}

// GET /api/v1/predict/upcoming item
export interface UpcomingFixture {
  fixture_id:    string
  date:          string
  home_team:     string
  away_team:     string
  b365:          { h: number; d: number; a: number }
  probabilities: Probabilities
  predicted:     Outcome
  label:         string
  confidence:    number
  ev_analysis:   EVAnalysis
}

// GET /api/v1/matches item
export interface HistoricalMatch {
  id:        string
  date:      string
  home_team: string
  away_team: string
  fthg:      number
  ftag:      number
  ftr:       Outcome
}

// Shape MatchCard expects (used by /results page)
export interface NormalizedFixture {
  id:         string
  date:       string
  home_team:  string
  away_team:  string
  home_logo:  string
  away_logo:  string
  status:     "pre" | "in" | "post"
  home_score?: number
  away_score?: number
}

// ResultMatch = HistoricalMatch + optional prediction
export interface ResultMatch extends HistoricalMatch {
  prediction?: PredictionResponse | null
  actual_result?: Outcome | null
}
