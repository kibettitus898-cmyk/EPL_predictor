// src/components/match/EVTable.tsx
import { cn } from "@/lib/utils"
import type { OutcomeDetail, Outcome } from "@/types"

const LABEL: Record<Outcome, string> = { H: "Home", D: "Draw", A: "Away" }

interface Props {
  outcomes: OutcomeDetail[]
  homeTeam: string
  awayTeam: string
}

export function EVTable({ outcomes, homeTeam, awayTeam }: Props) {
  const teamLabel = (o: Outcome) =>
    o === "H" ? homeTeam : o === "A" ? awayTeam : "Draw"

  return (
    <div className="rounded-md border border-border overflow-hidden text-xs">
      {/* Header */}
      <div className="grid grid-cols-4 bg-muted px-2 py-1 text-muted-foreground font-medium">
        <span>Outcome</span>
        <span className="text-right">Model%</span>
        <span className="text-right">Odd</span>
        <span className="text-right">EV</span>
      </div>

      {/* Rows */}
      {outcomes.map((o) => (
        <div
          key={o.outcome}
          className={cn(
            "grid grid-cols-4 px-2 py-1.5 border-t border-border",
            o.is_value
              ? "bg-green-50 text-green-800"
              : o.ev < 0
              ? "text-muted-foreground"
              : ""
          )}
        >
          <span className="font-medium truncate">
            {teamLabel(o.outcome)}
            {o.is_value && (
              <span className="ml-1 text-[10px] bg-green-200 text-green-800 rounded px-1">
                ⚡ Value
              </span>
            )}
          </span>
          <span className="text-right tabular-nums">
            {(o.model_prob * 100).toFixed(1)}%
          </span>
          <span className="text-right tabular-nums">{o.decimal_odd}</span>
          <span
            className={cn(
              "text-right tabular-nums font-medium",
              o.ev > 0.05  ? "text-green-700" :
              o.ev > 0     ? "text-foreground" :
                             "text-red-500"
            )}
          >
            {o.ev > 0 ? "+" : ""}
            {(o.ev * 100).toFixed(1)}%
            {/* Kelly badge */}
            {o.kelly_pct > 0 && (
              <span className="ml-1 text-[10px] text-green-600 font-normal">
                Kelly {o.kelly_pct}%
              </span>
            )}
          </span>
        </div>
      ))}
    </div>
  )
}