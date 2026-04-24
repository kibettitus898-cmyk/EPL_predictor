// src/components/match/MatchCard.tsx
import Image from "next/image"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { PredictionBadge } from "./PredictionBadge"
import { OddsRow } from "./OddsRow"           // ← new import
import { cn } from "@/lib/utils"
import { EVTable } from "./EVTable"
import type { NormalizedFixture, PredictionResponse, Outcome, EVAnalysis } from "@/types"  // ← added EVAnalysis

// ── Props ────────────────────────────────────────────────────────────────
interface Props {
  fixture: NormalizedFixture & {
    prediction?:    PredictionResponse | null
    actual_result?: Outcome | null
    b365?:          { h: number; d: number; a: number } | null   // ← new
    ev_analysis?:   EVAnalysis | null                             // ← new
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────
function resultBadge(predicted?: Outcome, actual?: Outcome | null) {
  if (!predicted || !actual) return null
  const correct = predicted === actual
  return (
    <Badge
      variant="outline"
      className={cn(
        "text-xs",
        correct
          ? "border-green-500 text-green-600 bg-green-50"
          : "border-red-400 text-red-600 bg-red-50"
      )}
    >
      {correct ? "✓ Correct" : "✗ Incorrect"}
    </Badge>
  )
}

const OUTCOME_LABEL: Record<Outcome, string> = { H: "Home Win", D: "Draw", A: "Away Win" }
const OUTCOME_COLOR: Record<Outcome, string> = {
  H: "bg-blue-100 text-blue-700 border-blue-300",
  D: "bg-yellow-100 text-yellow-700 border-yellow-300",
  A: "bg-red-100 text-red-700 border-red-300",
}

// ── Component ─────────────────────────────────────────────────────────────
export function MatchCard({ fixture }: Props) {
  const {
    home_team, away_team, home_logo, away_logo,
    date, status, home_score, away_score,
    prediction, actual_result,
    b365,         // ← destructure new props
    ev_analysis,  // ← destructure new props
  } = fixture

  const isFinished = status === "post"
  const formatted = new Date(date).toLocaleDateString("en-GB", {
    weekday: "short", day: "numeric", month: "short",
    hour: "2-digit", minute: "2-digit",
  })

  // Use card-level ev_analysis if prediction doesn't carry its own
  const activeEV = ev_analysis ?? prediction?.ev_analysis ?? null

  // Resolve the outcome label for the value bet banner
  const bestBetLabel =
    activeEV?.best_bet?.outcome === "H" ? home_team :
    activeEV?.best_bet?.outcome === "A" ? away_team : "Draw"

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="p-4 space-y-3">

        {/* ── Teams row ────────────────────────────────────────────── */}
        <div className="flex items-center justify-between gap-2">
          {/* Home */}
          <div className="flex flex-col items-center gap-1 w-20">
            {home_logo && (
              <Image src={home_logo} alt={home_team} width={36} height={36}
                className="object-contain" unoptimized />
            )}
            <span className="text-xs font-medium text-center leading-tight line-clamp-2">
              {home_team}
            </span>
          </div>

          {/* Score or date */}
          <div className="flex flex-col items-center gap-1 flex-1">
            {isFinished && home_score !== undefined ? (
              <span className="text-2xl font-bold tabular-nums tracking-tight">
                {home_score} – {away_score}
              </span>
            ) : (
              <span className="text-xs text-muted-foreground text-center">{formatted}</span>
            )}
            {isFinished && (
              <span className="text-[10px] text-muted-foreground uppercase tracking-wide">
                Full Time
              </span>
            )}
          </div>

          {/* Away */}
          <div className="flex flex-col items-center gap-1 w-20">
            {away_logo && (
              <Image src={away_logo} alt={away_team} width={36} height={36}
                className="object-contain" unoptimized />
            )}
            <span className="text-xs font-medium text-center leading-tight line-clamp-2">
              {away_team}
            </span>
          </div>
        </div>

        {/* ── Prediction section ───────────────────────────────────── */}
        {prediction && (
          <div className="space-y-2">
            <PredictionBadge
              probabilities={prediction.probabilities}
              predicted={prediction.predicted}
              homeTeam={home_team}
              awayTeam={away_team}
            />
            <div className="flex items-center justify-between flex-wrap gap-1.5">
              <Badge
                variant="outline"
                className={cn("text-xs", OUTCOME_COLOR[prediction.predicted])}
              >
                {OUTCOME_LABEL[prediction.predicted]}
              </Badge>
              <span className={cn(
                "text-xs tabular-nums",
                prediction.confidence >= 0.50 ? "font-bold text-green-700" :
                prediction.confidence >= 0.40 ? "font-bold text-amber-600" :
                                                "text-muted-foreground"
              )}>
                {Math.round(prediction.confidence * 100)}% confidence
              </span>
              {resultBadge(prediction.predicted, actual_result)}
            </div>
            {prediction.ev_analysis?.all_outcomes && (
          <EVTable
            outcomes={prediction.ev_analysis.all_outcomes}
            homeTeam={home_team}
            awayTeam={away_team}
          />
        )}
          </div>
                  )}
        {/* ── B365 odds row (new in v2) ────────────────────────────── */}
        {b365 && (
          <OddsRow b365={b365} ev={activeEV} />
        )}

        {/* ── Value bet banner (updated in v2) ────────────────────── */}
        {activeEV?.has_value && activeEV.best_bet && (
          <div className="rounded-md bg-green-50 border border-green-200 px-3 py-2 text-xs text-green-700 space-y-0.5">
            <div className="flex items-center gap-1.5 font-semibold">
              🟢 VALUE BET → {bestBetLabel} @ {activeEV.best_bet.decimal_odd}
            </div>
            <div className="flex gap-3 text-green-600">
              <span>EV +{(activeEV.best_bet.ev * 100).toFixed(1)}%</span>
              <span>Kelly {Math.min(activeEV.best_bet.kelly_pct, 15).toFixed(1)}%</span>
            </div>
          </div>
        )}
          
      </CardContent>
    </Card>
  )
}