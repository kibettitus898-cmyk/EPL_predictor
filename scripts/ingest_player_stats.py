"""
Ingest Kaggle football player stats CSV into Supabase.

Usage:
    python scripts/ingest_player_stats.py
    python scripts/ingest_player_stats.py --csv path/to/players_data-2025_2026.csv
    python scripts/ingest_player_stats.py --season 24/25 --csv path/to/players_data-2024_2025.csv
"""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.player_stats_service import ingest_player_stats
import logging

logging.basicConfig(level=logging.INFO)

DEFAULT_CSV = "data/raw/players_data-2025_2026.csv"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv",    default=DEFAULT_CSV, help="Path to the CSV file")
    parser.add_argument("--season", default="25/26",     help="Season label e.g. 25/26")
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"❌ CSV not found: {args.csv}")
        print(f"   Download from: https://kaggle.com/datasets/hubertsidorowicz/football-players-stats-2025-2026")
        print(f"   Then place it at: {DEFAULT_CSV}")
        sys.exit(1)

    count = ingest_player_stats(args.csv, args.season)
    print(f"\n✅ Done! {count} EPL player records saved to Supabase player_stats table")