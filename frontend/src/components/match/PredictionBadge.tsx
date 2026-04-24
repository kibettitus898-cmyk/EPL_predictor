// src/components/match/PredictionBadge.tsx
import { cn } from "@/lib/utils"
import type { Outcome } from "@/types"

interface Props {
  probabilities: { H: number; D: number; A: number }
  predicted?: Outcome
  homeTeam: string
  awayTeam: string
}

const OUTCOME_META: Record<Outcome, { label: string; color: string; bg: string }> = {
  H: { label: "Home",  color: "text-blue-600",   bg: "bg-blue-500"   },
  D: { label: "Draw",  color: "text-yellow-600",  bg: "bg-yellow-400" },
  A: { label: "Away",  color: "text-red-600",     bg: "bg-red-500"    },
}

export function PredictionBadge({ probabilities, predicted, homeTeam, awayTeam }: Props) {
  const outcomes: Outcome[] = ["H", "D", "A"]
  const labels: Record<Outcome, string> = {
    H: homeTeam,
    D: "Draw",
    A: awayTeam,
  }

  return (
    <div className="space-y-1.5 w-full">
      {outcomes.map((o) => {
        const pct = Math.round(probabilities[o] * 100)
        const meta = OUTCOME_META[o]
        const isTop = predicted === o

        return (
          <div key={o} className="flex items-center gap-2 text-xs">
            <span className={cn("w-10 font-medium shrink-0", meta.color)}>
              {meta.label}
            </span>
            <div className="relative flex-1 h-2 rounded-full bg-muted overflow-hidden">
              <div
                className={cn("h-full rounded-full transition-all", meta.bg)}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className={cn("w-8 text-right font-semibold", isTop && meta.color)}>
              {pct}%
            </span>
            {isTop && (
              <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                ▲
              </span>
            )}
          </div>
        )
      })}

      {/* Team name reminders */}
      <div className="flex justify-between text-[10px] text-muted-foreground pt-0.5">
        <span>{homeTeam}</span>
        <span>{awayTeam}</span>
      </div>
    </div>
  )
}