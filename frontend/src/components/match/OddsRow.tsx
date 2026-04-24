// src/components/match/OddsRow.tsx
import { cn } from "@/lib/utils"
import type { EVAnalysis } from "@/types"

interface Props {
  b365: { h: number; d: number; a: number }
  ev?: EVAnalysis | null
}

function evColor(outcome: string, ev?: EVAnalysis | null) {
  if (!ev) return ""
  const o = ev.all_outcomes.find((x) => x.outcome === outcome)
  if (!o) return ""
  if (o.is_value) return "text-green-600 font-semibold"
  if (o.ev > 0) return "text-orange-500"
  return "text-muted-foreground"
}

export function OddsRow({ b365, ev }: Props) {
  return (
    <div className="flex items-center justify-between rounded-md bg-muted px-3 py-1.5 text-xs">
      <span className={cn("flex flex-col items-center gap-0.5", evColor("H", ev))}>
        <span className="text-[10px] text-muted-foreground uppercase tracking-wide">Home</span>
        <span className="font-mono font-medium">{b365.h.toFixed(2)}</span>
      </span>
      <span className={cn("flex flex-col items-center gap-0.5", evColor("D", ev))}>
        <span className="text-[10px] text-muted-foreground uppercase tracking-wide">Draw</span>
        <span className="font-mono font-medium">{b365.d.toFixed(2)}</span>
      </span>
      <span className={cn("flex flex-col items-center gap-0.5", evColor("A", ev))}>
        <span className="text-[10px] text-muted-foreground uppercase tracking-wide">Away</span>
        <span className="font-mono font-medium">{b365.a.toFixed(2)}</span>
      </span>
    </div>
  )
}