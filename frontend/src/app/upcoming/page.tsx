// src/app/upcoming/page.tsx
export const dynamic = "force-dynamic"  // ← add this at the top

import { Suspense } from "react"
import { api } from "@/lib/api"
import { Skeleton } from "@/components/ui/skeleton"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { OddsRow } from "@/components/match/OddsRow"
import { PredictionBadge } from "@/components/match/PredictionBadge"
import { cn } from "@/lib/utils"
import type { UpcomingFixture, Outcome } from "@/types"

// ── Helpers ───────────────────────────────────────────────────────────────
const OUTCOME_LABEL: Record<Outcome, string> = {
  H: "Home Win", D: "Draw", A: "Away Win",
}
const OUTCOME_COLOR: Record<Outcome, string> = {
  H: "bg-blue-100 text-blue-700 border-blue-300",
  D: "bg-yellow-100 text-yellow-700 border-yellow-300",
  A: "bg-red-100 text-red-700 border-red-300",
}

// ── Single fixture card ───────────────────────────────────────────────────
function UpcomingCard({ fixture }: { fixture: UpcomingFixture }) {
  const {
    home_team, away_team, date,
    probabilities, predicted, confidence,
    b365, ev_analysis,
  } = fixture

  const formatted = new Date(date).toLocaleDateString("en-GB", {
    weekday: "short", day: "numeric", month: "short",
    hour: "2-digit", minute: "2-digit",
  })

  const bestBetLabel =
    ev_analysis?.best_bet?.outcome === "H" ? home_team :
    ev_analysis?.best_bet?.outcome === "A" ? away_team : "Draw"

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="p-4 space-y-3">

        {/* Teams + date */}
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-semibold text-center w-24 leading-tight">
            {home_team}
          </span>
          <div className="flex flex-col items-center flex-1">
            <span className="text-[10px] text-muted-foreground uppercase tracking-wide">
              vs
            </span>
            <span className="text-xs text-muted-foreground text-center mt-0.5">
              {formatted}
            </span>
          </div>
          <span className="text-sm font-semibold text-center w-24 leading-tight text-right">
            {away_team}
          </span>
        </div>

        {/* Probability bars */}
        <PredictionBadge
          probabilities={probabilities}
          predicted={predicted}
          homeTeam={home_team}
          awayTeam={away_team}
        />

        {/* Prediction badge + confidence */}
        <div className="flex items-center justify-between flex-wrap gap-1.5">
          <Badge
            variant="outline"
            className={cn("text-xs", OUTCOME_COLOR[predicted])}
          >
            {OUTCOME_LABEL[predicted]}
          </Badge>
          <span className={cn(
            "text-xs",
            confidence > 0.6 ? "font-bold text-foreground" : "text-muted-foreground"
          )}>
            {Math.round(confidence * 100)}% confidence
          </span>
        </div>

        {/* B365 odds — only when available */}
        {b365 && <OddsRow b365={b365} ev={ev_analysis} />}

        {/* Value bet banner */}
        {ev_analysis?.has_value && ev_analysis.best_bet && (
          <div className="rounded-md bg-green-50 border border-green-200 px-3 py-2 text-xs text-green-700 space-y-0.5">
            <div className="font-semibold">
              🟢 VALUE BET → {bestBetLabel} @ {ev_analysis.best_bet.decimal_odd}
            </div>
            <div className="flex gap-3 text-green-600">
              <span>EV +{(ev_analysis.best_bet.ev * 100).toFixed(1)}%</span>
              {ev_analysis.best_bet.kelly_pct !== undefined && (
                <span>
                  Kelly {Math.min(ev_analysis.best_bet.kelly_pct, 15).toFixed(1)}%
                </span>
              )}
            </div>
          </div>
        )}

      </CardContent>
    </Card>
  )
}

// ── Data fetcher ──────────────────────────────────────────────────────────
async function UpcomingList() {
  let fixtures: UpcomingFixture[]

  try {
    fixtures = await api.getUpcoming()
  } catch (err) {
    return (
      <div className="rounded-md bg-red-50 border border-red-200 p-4 text-sm text-red-700 space-y-1">
        <p className="font-semibold">⚠ Could not load upcoming fixtures</p>
        <p className="text-xs text-red-500">
          {(err as Error).message}
        </p>
        <p className="text-xs text-red-400">
          Make sure the backend is running and{" "}
          <code className="bg-red-100 px-1 rounded">
            GET /api/v1/predict/upcoming
          </code>{" "}
          is implemented.
        </p>
      </div>
    )
  }

  if (!Array.isArray(fixtures) || fixtures.length === 0) {
    return (
      <p className="text-muted-foreground text-sm py-12 text-center">
        No upcoming fixtures found. Check back soon.
      </p>
    )
  }

  // Highlight value bets at the top
  const valueBets    = fixtures.filter(f => f.ev_analysis?.has_value)
  const regularGames = fixtures.filter(f => !f.ev_analysis?.has_value)
  const sorted       = [...valueBets, ...regularGames]

  return (
    <div className="space-y-6">
      {valueBets.length > 0 && (
        <div className="flex items-center gap-2 text-sm font-medium text-green-700">
          🟢 {valueBets.length} value bet{valueBets.length > 1 ? "s" : ""} detected
          this gameweek
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {sorted.map((f) => (
          <UpcomingCard key={f.fixture_id} fixture={f} />
        ))}
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────
export default function UpcomingPage() {
  return (
    <main className="container max-w-5xl mx-auto px-4 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Upcoming Fixtures</h1>
        <p className="text-muted-foreground text-sm">
          Live B365 odds · ensemble model predictions · EV analysis
        </p>
      </div>
      <Suspense fallback={<SkeletonGrid />}>
        <UpcomingList />
      </Suspense>
    </main>
  )
}

// ── Skeleton ──────────────────────────────────────────────────────────────
function SkeletonGrid() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-56 rounded-xl" />
      ))}
    </div>
  )
}
