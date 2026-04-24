// src/lib/team-map.ts
export const ESPN_TO_BACKEND: Record<string, string> = {
  "AFC Bournemouth":            "Bournemouth",
  "Arsenal FC":                 "Arsenal",
  "Aston Villa FC":             "Aston Villa",
  "Brentford FC":               "Brentford",
  "Brighton & Hove Albion FC":  "Brighton",
  "Burnley FC":                 "Burnley",
  "Chelsea FC":                 "Chelsea",
  "Crystal Palace FC":          "Crystal Palace",
  "Everton FC":                 "Everton",
  "Fulham FC":                  "Fulham",
  "Ipswich Town FC":            "Ipswich",        // ← changed
  "Leeds United FC":            "Leeds",           // ← changed
  "Leicester City FC":          "Leicester",       // ← changed
  "Liverpool FC":               "Liverpool",
  "Luton Town FC":              "Luton",
  "Manchester City FC":         "Man City",        // ← changed
  "Manchester United FC":       "Man United",      // ← changed
  "Newcastle United FC":        "Newcastle",       // ← changed
  "Nottingham Forest FC":       "Nott'm Forest",   // ← changed
  "Southampton FC":             "Southampton",
  "Sunderland AFC":             "Sunderland",
  "Tottenham Hotspur FC":       "Tottenham",       // ← changed
  "West Ham United FC":         "West Ham",        // ← changed
  "Wolverhampton Wanderers FC": "Wolves",          // ← changed
}

export const normalise = (name: string): string =>
  ESPN_TO_BACKEND[name] ?? name