// src/lib/espn.ts
import type { NormalizedFixture } from "@/types"
import { ESPN_TO_BACKEND } from "./team-map"

const ESPN_URL =
  "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard"

function extractTeamName(raw: string): string {
  return ESPN_TO_BACKEND[raw] ?? raw
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function normalizeEvent(event: any): NormalizedFixture {
  const comp = event.competitions[0]
  const home = comp.competitors.find((c: any) => c.homeAway === "home")
  const away = comp.competitors.find((c: any) => c.homeAway === "away")
  const stateType: string = comp.status?.type?.name ?? "STATUS_SCHEDULED"

  const status: "pre" | "in" | "post" =
    stateType.includes("FINAL") || stateType.includes("POST")
      ? "post"
      : stateType.includes("IN_PROGRESS")
      ? "in"
      : "pre"

  return {
    id: event.id,
    date: event.date,
    home_team: extractTeamName(home.team.displayName),
    away_team: extractTeamName(away.team.displayName),
    home_logo: home.team.logo,
    away_logo: away.team.logo,
    status,
    home_score: status !== "pre" ? Number(home.score) : undefined,
    away_score: status !== "pre" ? Number(away.score) : undefined,
  }
}

export async function fetchEPLFixtures(): Promise<NormalizedFixture[]> {
  const res = await fetch(ESPN_URL, { next: { revalidate: 300 } })
  if (!res.ok) throw new Error(`ESPN fetch failed: ${res.status}`)
  const data = await res.json()
  return (data.events ?? []).map(normalizeEvent)
}