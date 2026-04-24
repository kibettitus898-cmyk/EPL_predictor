import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.transfermarkt_service import ingest_live_injuries
from app.services.squad_availability_service import build_squad_availability_snapshot
import logging
logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    ingest_live_injuries()
    build_squad_availability_snapshot()
    print("✅ Injuries + squad availability refreshed")