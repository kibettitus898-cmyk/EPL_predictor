"""
Validate local CSV files before uploading to Supabase.
Usage: python scripts/validate_csv.py data/raw/seasons/
"""
import sys, os, pandas as pd
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.ingest_service import COLUMN_MAP

def validate(folder: str):
    csvs = list(Path(folder).glob("*.csv"))
    print(f"Found {len(csvs)} CSV files\n")
    for f in sorted(csvs):
        df = pd.read_csv(f, on_bad_lines="skip")
        present = [c for c in COLUMN_MAP if c in df.columns]
        missing = [c for c in COLUMN_MAP if c not in df.columns]
        print(f"  {f.name}: {len(df)} rows | cols: {len(present)}/{len(COLUMN_MAP)} matched")
        if missing:
            print(f"    ⚠️  Missing: {missing}")

if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "data/raw/seasons"
    validate(folder)
