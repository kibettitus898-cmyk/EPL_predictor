// src/lib/api.ts
import type { HistoricalMatch, UpcomingFixture, PredictionResponse } from "@/types"

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function apiCall<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const message = body?.detail ?? `API error: ${res.status}`
    const err = new Error(message) as Error & { status: number }
    err.status = res.status
    throw err
  }
  return res.json()
}

export const api = {
  health: () =>
    apiCall<{ status: string }>(`${BASE}/health`),

  getMatches: async (season?: string, limit = 50, offset = 0) => {
  const raw = await apiCall<
    HistoricalMatch[] | { count: number; data: HistoricalMatch[] }
  >(
    `${BASE}/api/v1/matches?limit=${limit}&offset=${offset}${season ? `&season=${season}` : ""}`
  )
  // Backend returns { count, data: [...] } — unwrap to plain array
  return Array.isArray(raw) ? raw : raw.data ?? []
},

  predict: (
    home_team: string,
    away_team: string,
    home_odd?: number,
    draw_odd?: number,
    away_odd?: number
  ) =>
    apiCall<PredictionResponse>(`${BASE}/api/v1/predict`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ home_team, away_team, home_odd, draw_odd, away_odd }),
    }),

  getUpcoming: (limit = 20) =>
    apiCall<UpcomingFixture[]>(
      `${BASE}/api/v1/predict/upcoming?limit=${limit}`
    ),
}
