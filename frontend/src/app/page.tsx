// src/app/page.tsx
import Link from "next/link"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

export default function HomePage() {
  return (
    <main className="container max-w-5xl mx-auto px-4 py-12 space-y-10">
      {/* Hero */}
      <div className="space-y-3">
        <h1 className="text-3xl font-bold">EPL Match Predictor</h1>
        <p className="text-muted-foreground max-w-xl">
          Machine learning predictions for every Premier League fixture.
          View upcoming games, track past results, or run a manual prediction.
        </p>
      </div>

      {/* Quick nav cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <NavCard
          href="/upcoming"
          title="Upcoming Fixtures"
          description="See model predictions for all scheduled EPL games."
          emoji="📅"
        />
        <NavCard
          href="/results"
          title="Past Results"
          description="Compare predictions vs actual outcomes this season."
          emoji="📊"
        />
        <NavCard
          href="/predict"
          title="Manual Prediction"
          description="Enter any fixture and get an instant prediction with EV analysis."
          emoji="🔮"
        />
      </div>
    </main>
  )
}

function NavCard({
  href, title, description, emoji,
}: {
  href: string; title: string; description: string; emoji: string
}) {
  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="p-6 space-y-3 flex flex-col h-full">
        <span className="text-3xl">{emoji}</span>
        <h2 className="font-semibold text-lg">{title}</h2>
        <p className="text-sm text-muted-foreground flex-1">{description}</p>
        <Button asChild variant="outline" className="w-full mt-2">
          <Link href={href}>Go →</Link>
        </Button>
      </CardContent>
    </Card>
  )
}