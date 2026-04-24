"""Run this once to load all historical seasons into Supabase."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ingest_service import ingest_all
import logging
logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    ingest_all()
    print("✅ All seasons ingested successfully")
