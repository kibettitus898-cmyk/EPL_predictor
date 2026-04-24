// src/components/match/EVBadge.tsx
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { Outcome } from "@/types"

const LABEL: Record<Outcome, string> = { H: "Home", D: "Draw", A: "Away" }

interface Props {
  outcome: Outcome
  ev: number
  decimal_odd: number
  kelly_pct: number
  is_value: boolean
}

export function EVBadge({ outcome, ev, decimal_odd, kelly_pct, is_value }: Props) {
  const evStr = `${ev >= 0 ? "+" : ""}${(ev * 100).toFixed(1)}%`
  const kelly = Math.min(kelly_pct, 15) // cap at 15%

  return (
    <div
      className={cn(
        "flex items-center justify-between rounded-md px-3 py-2 text-xs border",
        is_value
          ? "bg-green-50 border-green-200 text-green-700"
          : ev > 0
          ? "bg-orange-50 border-orange-200 text-orange-600"
          : "bg-muted border-border text-muted-foreground"
      )}
    >
      <div className="flex items-center gap-2">
        {is_value && (
          <span className="text-[10px] font-bold uppercase tracking-wide text-green-600">
            🟢 Value
          </span>
        )}
        <span className="font-medium">{LABEL[outcome]} @ {decimal_odd}</span>
      </div>
      <div className="flex items-center gap-3">
        <span>EV <span className="font-semibold">{evStr}</span></span>
        <span>Kelly <span className="font-semibold">{kelly.toFixed(1)}%</span></span>
      </div>
    </div>
  )
}