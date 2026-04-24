import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.xg_service import ingest_all_xg
import logging
logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    ingest_all_xg()
    print("✅ xG data ingested")