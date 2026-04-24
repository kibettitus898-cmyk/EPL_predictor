import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.espn_service import ingest_possession_season
import logging
logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    # Start with just 2024 to verify it works, then backfill
    for year in [2024, 2023, 2022, 2021, 2020, 2019]:
        ingest_possession_season(year)
    print("✅ ESPN possession ingestion complete")