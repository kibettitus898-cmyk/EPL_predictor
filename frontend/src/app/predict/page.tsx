// src/app/predict/page.tsx
"use client"
import { useState } from "react"
import { api } from "@/lib/api"
import { getFriendlyError } from "@/lib/errors"
import type { PredictionResponse, Outcome } from "@/types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PredictionBadge } from "@/components/match/PredictionBadge"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

// ── Constants ─────────────────────────────────────────────────────────────
const OUTCOME_LABEL: Record<Outcome, string> = {
  H: "Home Win", D: "Draw", A: "Away Win",
}
const OUTCOME_COLOR: Record<Outcome, string> = {
  H: "bg-blue-100 text-blue-700 border-blue-300",
  D: "bg-yellow-100 text-yellow-700 border-yellow-300",
  A: "bg-red-100 text-red-700 border-red-300",
}

// ── Form shape ────────────────────────────────────────────────────────────
interface FormState {
  home_team: string
  away_team: string
  home_odd:  string
  draw_odd:  string
  away_odd:  string
}

// ── Page ──────────────────────────────────────────────────────────────────
export default function PredictPage() {
  const [form, setForm] = useState<FormState>({
    home_team: "", away_team: "",
    home_odd: "", draw_odd: "", away_odd: "",
  })
  const [result,   setResult]   = useState<PredictionResponse | null>(null)
  const [error,    setError]    = useState<string | null>(null)
  const [oddsErr,  setOddsErr]  = useState<string | null>(null)
  const [loading,  setLoading]  = useState(false)

  // ── Odds validation ───────────────────────────────────────────────────
  function validateOdds(): boolean {
    const { home_odd, draw_odd, away_odd } = form
    const anyFilled = home_odd || draw_odd || away_odd
    const allFilled = home_odd && draw_odd && away_odd

    if (anyFilled && !allFilled) {
      setOddsErr("Enter all three odds or leave all blank")
      return false
    }
    if (allFilled) {
      for (const [label, val] of [
        ["Home", parseFloat(home_odd)],
        ["Draw", parseFloat(draw_odd)],
        ["Away", parseFloat(away_odd)],
      ] as [string, number][]) {
        if (isNaN(val) || val < 1.01 || val > 100) {
          setOddsErr(`${label} odds must be between 1.01 and 100`)
          return false
        }
      }
    }
    setOddsErr(null)
    return true
  }

  // ── Submit ────────────────────────────────────────────────────────────
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setResult(null)

    if (!validateOdds()) return

    setLoading(true)
    try {
      const { home_team, away_team, home_odd, draw_odd, away_odd } = form

      const res = await api.predict(
        home_team.trim(),
        away_team.trim(),
        home_odd ? parseFloat(home_odd) : undefined,
        draw_odd ? parseFloat(draw_odd) : undefined,
        away_odd ? parseFloat(away_odd) : undefined,
      )
      setResult(res)
    } catch (err) {
      setError(getFriendlyError(err as Error & { status?: number }))
    } finally {
      setLoading(false)
    }
  }

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <main className="container max-w-2xl mx-auto px-4 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Manual Prediction</h1>
        <p className="text-muted-foreground text-sm">
          Enter a fixture and optionally add bookmaker odds for EV analysis
        </p>
      </div>

      {/* ── Form ── */}
      <Card>
        <CardContent className="p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Teams */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="home">Home Team</Label>
                <Input
                  id="home"
                  placeholder="e.g. Arsenal"
                  value={form.home_team}
                  onChange={(e) => setForm({ ...form, home_team: e.target.value })}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="away">Away Team</Label>
                <Input
                  id="away"
                  placeholder="e.g. Liverpool"
                  value={form.away_team}
                  onChange={(e) => setForm({ ...form, away_team: e.target.value })}
                  required
                />
              </div>
            </div>

            {/* Odds */}
            <p className="text-xs text-muted-foreground">
              Optional: add decimal odds to unlock EV analysis
            </p>
            <div className="grid grid-cols-3 gap-3">
              {(["home_odd", "draw_odd", "away_odd"] as const).map((key) => (
                <div key={key} className="space-y-1.5">
                  <Label htmlFor={key}>
                    {key === "home_odd" ? "Home" : key === "draw_odd" ? "Draw" : "Away"} Odds
                  </Label>
                  <Input
                    id={key}
                    type="number"
                    step="0.01"
                    min="1.01"
                    max="100"
                    placeholder="e.g. 2.10"
                    value={form[key]}
                    onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                  />
                </div>
              ))}
            </div>

            {/* Odds error */}
            {oddsErr && (
              <p className="text-xs text-red-600">⚠ {oddsErr}</p>
            )}

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Predicting…" : "Get Prediction"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* ── API error ── */}
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-4 text-sm text-red-700">
            ⚠ {error}
          </CardContent>
        </Card>
      )}

      {/* ── Result ── */}
      {result && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {result.home_team} vs {result.away_team}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {/* Probability bar */}
            <PredictionBadge
              probabilities={result.probabilities}
              predicted={result.predicted}
              homeTeam={result.home_team}
              awayTeam={result.away_team}
            />

            {/* Predicted outcome + confidence */}
            <div className="flex items-center gap-2 flex-wrap">
              <Badge
                variant="outline"
                className={cn("text-xs", OUTCOME_COLOR[result.predicted])}
              >
                {OUTCOME_LABEL[result.predicted]}
              </Badge>
              <span className={cn(
                "text-xs",
                result.confidence >= 0.50 ? "font-bold text-green-700" :
                result.confidence >= 0.40 ? "font-bold text-amber-600" :
                                             "text-muted-foreground"
              )}>
                {Math.round(result.confidence * 100)}% confidence
              </span>
            </div>

            {/* EV Analysis */}
            {result.ev_analysis && (
              <div className="space-y-2 pt-2 border-t">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                    EV Analysis
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Vig: {(result.ev_analysis.bookmaker_vig * 100).toFixed(1)}%
                  </p>
                </div>

                {/* Per-outcome rows */}
                <div className="rounded-md border overflow-hidden text-xs">
                  <div className="grid grid-cols-4 bg-muted px-2 py-1 text-muted-foreground font-medium">
                    <span>Outcome</span>
                    <span className="text-right">Model%</span>
                    <span className="text-right">Odd</span>
                    <span className="text-right">EV</span>
                  </div>
                  {result.ev_analysis.all_outcomes.map((o) => (
                    <div
                      key={o.outcome}
                      className={cn(
                        "grid grid-cols-4 px-2 py-1.5 border-t",
                        o.is_value
                          ? "bg-green-50 text-green-800"
                          : o.ev < 0
                          ? "text-muted-foreground"
                          : ""
                      )}
                    >
                      <span className="font-medium">
                        {o.outcome === "H" ? result.home_team :
                         o.outcome === "A" ? result.away_team : "Draw"}
                        {o.is_value && (
                          <span className="ml-1 bg-green-200 text-green-800 rounded px-1 text-[10px]">
                            ⚡ Value
                          </span>
                        )}
                      </span>
                      <span className="text-right tabular-nums">
                        {(o.model_prob * 100).toFixed(1)}%
                      </span>
                      <span className="text-right tabular-nums">
                        {o.decimal_odd}
                      </span>
                      <span className={cn(
                        "text-right tabular-nums font-medium",
                        o.ev > 0.05  ? "text-green-700" :
                        o.ev > 0     ? "text-foreground" :
                                       "text-red-500"
                      )}>
                        {o.ev > 0 ? "+" : ""}{(o.ev * 100).toFixed(1)}%
                        {o.kelly_pct > 0 && (
                          <span className="ml-1 text-[10px] text-green-600 font-normal">
                            Kelly {o.kelly_pct}%
                          </span>
                        )}
                      </span>
                    </div>
                  ))}
                </div>

                {/* Value bet banner */}
                {result.ev_analysis.has_value && result.ev_analysis.best_bet && (
                  <div className="rounded-md bg-green-50 border border-green-200 px-3 py-2 text-xs text-green-700 space-y-0.5">
                    <div className="font-semibold">
                      🟢 VALUE BET →{" "}
                      {result.ev_analysis.best_bet.outcome === "H"
                        ? result.home_team
                        : result.ev_analysis.best_bet.outcome === "A"
                        ? result.away_team
                        : "Draw"}{" "}
                      @ {result.ev_analysis.best_bet.decimal_odd}
                    </div>
                    <div className="flex gap-3 text-green-600">
                      <span>
                        EV +{(result.ev_analysis.best_bet.ev * 100).toFixed(1)}%
                      </span>
                      {result.ev_analysis.best_bet.kelly_pct > 0 && (
                        <span>
                          Kelly {Math.min(result.ev_analysis.best_bet.kelly_pct, 15).toFixed(1)}%
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </main>
  )
}