// src/components/layout/Navbar.tsx
"use client"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"

const NAV = [
  { href: "/",         label: "Dashboard" },
  { href: "/upcoming", label: "Upcoming"  },
  { href: "/results",  label: "Results"   },
  { href: "/predict",  label: "Predict"   },
]

export function Navbar() {
  const pathname = usePathname()
  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur">
      <div className="container flex h-14 max-w-5xl mx-auto items-center justify-between px-4">
        <Link href="/" className="font-bold text-lg tracking-tight">
          ⚽ EPL Predictor
        </Link>
        <nav className="flex gap-1">
          {NAV.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                pathname === href
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              )}
            >
              {label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  )
}