// src/app/results/page.tsx
export const dynamic = "force-dynamic"  // ← add this at the top

import { Suspense } from "react"
import { api } from "@/lib/api"
import { MatchCard } from "@/components/match/MatchCard"
import { AccuracyStats } from "@/components/stats/AccuracyStats"
import { Skeleton } from "@/components/ui/skeleton"
import type { ResultMatch, HistoricalMatch, NormalizedFixture } from "@/types"

// ── Data fetcher ──────────────────────────────────────────────────────────
async function ResultsList() {
  const matches = await api.getMatches(undefined, 50, 0)  // ← now always an array

  if (matches.length === 0) {
    return (
      <p className="text-muted-foreground text-sm py-12 text-center">
        No matches found for this season.
      </p>
    )
  }

  const withPredictions: ResultMatch[] = await Promise.all(
    matches.map(async (m: HistoricalMatch): Promise<ResultMatch> => ({
      ...m,
      prediction: await api
        .predict(m.home_team, m.away_team)
        .catch(() => null),
      actual_result: m.ftr, 
    }))
  )

  // Build NormalizedFixture shape MatchCard expects
  const asFixtures = withPredictions.map((m) => {
    const normalized: NormalizedFixture & {
      prediction: ResultMatch["prediction"]
      actual_result: ResultMatch["ftr"]
    } = {
      id:           m.id,
      date:         m.date,
      home_team:    m.home_team,
      away_team:    m.away_team,
      home_logo:    "",   // no logos from Supabase — ESPN logos only on /upcoming
      away_logo:    "",
      status:       "post",
      home_score:   m.fthg,
      away_score:   m.ftag,
      prediction:   m.prediction,
      actual_result: m.ftr,  // ← v2: ftr is already "H" | "D" | "A"
    }
    return normalized
  })

  return (
    <div className="space-y-6">
      <AccuracyStats results={withPredictions} />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {asFixtures.map((f) => (
          <MatchCard key={f.id} fixture={f} />
        ))}
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────
export default function ResultsPage() {
  return (
    <main className="container max-w-5xl mx-auto px-4 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Past Results</h1>
        <p className="text-muted-foreground text-sm">
          Model predictions vs actual outcomes · 2025–26 season
        </p>
      </div>
      <Suspense fallback={<SkeletonGrid />}>
        <ResultsList />
      </Suspense>
    </main>
  )
}

// ── Skeleton ──────────────────────────────────────────────────────────────
function SkeletonGrid() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-24 rounded-xl" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-48 rounded-xl" />
        ))}
      </div>
    </div>
  )
}
