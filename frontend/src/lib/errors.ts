// src/lib/errors.ts
export function getFriendlyError(err: Error & { status?: number }): string {
  switch (err.status) {
    case 503: return "Service unavailable — model training may be in progress"
    case 404: return "Team not recognised — check spelling"
    case 422: return "Invalid request — check your inputs"
    case 502: return "Live odds unavailable — try again shortly"
    default:  return err.message ?? "Something went wrong"
  }
}