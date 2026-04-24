// src/components/stats/AccuracyStats.tsx
import { Card, CardContent } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import type { ResultMatch } from "@/types"

interface Props { results: ResultMatch[] }

export function AccuracyStats({ results }: Props) {
  const evaluated = results.filter(
    (r) => r.prediction && r.actual_result
  )
  const correct = evaluated.filter(
    (r) => r.prediction?.predicted === r.actual_result
  ).length
  const accuracy = evaluated.length
    ? Math.round((correct / evaluated.length) * 100)
    : 0

  const dist = { H: 0, D: 0, A: 0 }
  evaluated.forEach((r) => { if (r.actual_result) dist[r.actual_result]++ })

  return (
    <Card>
      <CardContent className="p-4 flex flex-wrap gap-4 items-center justify-around text-center">
        <Stat label="Accuracy" value={`${accuracy}%`} highlight />
        <Separator orientation="vertical" className="h-10 hidden sm:block" />
        <Stat label="Evaluated" value={evaluated.length} />
        <Separator orientation="vertical" className="h-10 hidden sm:block" />
        <Stat label="Correct" value={correct} />
        <Separator orientation="vertical" className="h-10 hidden sm:block" />
        <div className="text-xs text-muted-foreground space-y-0.5">
          <p className="font-medium text-foreground mb-1">Result Distribution</p>
          <p>Home Wins: {dist.H}</p>
          <p>Draws: {dist.D}</p>
          <p>Away Wins: {dist.A}</p>
        </div>
      </CardContent>
    </Card>
  )
}

function Stat({ label, value, highlight }: {
  label: string; value: string | number; highlight?: boolean
}) {
  return (
    <div>
      <p className={`text-2xl font-bold ${highlight ? "text-primary" : ""}`}>{value}</p>
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  )
}